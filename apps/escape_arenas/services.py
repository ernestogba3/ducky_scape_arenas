# TODO: reescribir en Fase 2 con las operaciones transaccionales descritas
# en el documento (sección 11): start_session, submit_puzzle_answer,
# purchase_hint, complete_stage, settle_session.
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    EscapeSettlement,
    Hint,
    HintUsage,
    PuzzleAttempt,
    UserEscapeSession,
    UserRoomProgress,
    UserStageProgress,
)
XP_PER_POINT = 1  # 1 punto de puzzle = 1 XP bruta (placeholder)

MAX_MISTAKES = 5  # Umbral provisional; confirmar con el profesor
# ──────────────────────────────────────────────────────────────
# Temporizador
# ──────────────────────────────────────────────────────────────
def get_deadline(session):
    """Devuelve el instante límite de la sesión."""
    return session.started_at + timedelta(
        minutes=session.escape_room.time_limit_seconds
    )


def get_remaining_seconds(session):
    """Segundos que quedan. 0 si ya caducó."""
    remaining = (get_deadline(session) - timezone.now()).total_seconds()
    return max(0, int(remaining))


def expire_session_if_needed(session):
    """Marca FAILED si ha caducado. Devuelve True si expiró."""
    if session.status != UserEscapeSession.Status.PLAYING:
        return False
    if get_remaining_seconds(session) > 0:
        return False

    with transaction.atomic():
        session.status = UserEscapeSession.Status.FAILED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        settle_session(session, reason=EscapeSettlement.Reason.TIME_EXPIRED)
    return True


# ──────────────────────────────────────────────────────────────
# Validación de respuestas
# ──────────────────────────────────────────────────────────────
def normalize(text):
    """Normalización mínima y predecible. No elimina caracteres arbitrariamente."""
    return text.strip().lower()


def check_stage_answer(*, puzzle, submitted_answer):
    """Compara la respuesta del jugador con la esperada. El servidor decide."""
    expected = normalize(puzzle.solution_hash)
    submitted = normalize(submitted_answer)
    return submitted == expected

# ──────────────────────────────────────────────────────────────
# Inicio
# ──────────────────────────────────────────────────────────────
def start_session(*, user, escape_room):
    """
    Crea una UserEscapeSession en estado PLAYING con:
    - started_at = ahora
    - expires_at = started_at + time_limit_seconds
    - current_room = primera room
    - current_stage = primer stage de esa room
    - rules_snapshot = congelación de las reglas de la EscapeRoom

    Devuelve la sesión creada.
    Lanza ValueError si la aventura no tiene rooms o stages.
    """
    first_room = escape_room.rooms.order_by("order").first()
    if first_room is None:
        raise ValueError("Esta aventura todavía no tiene habitaciones.")

    first_stage = first_room.stages.order_by("order").first()
    if first_stage is None:
        raise ValueError("Esta habitación no tiene pruebas.")

    now = timezone.now()
    expires_at = now + timedelta(seconds=escape_room.time_limit_seconds)

    rules_snapshot = {
        "time_limit_seconds": escape_room.time_limit_seconds,
        "difficulty": escape_room.difficulty,
        "version": escape_room.version,
        "final_solution_hash": escape_room.final_solution_hash,
    }

    with transaction.atomic():
        session = UserEscapeSession.objects.create(
            user=user,
            escape_room=escape_room,
            status=UserEscapeSession.Status.PLAYING,
            started_at=now,
            expires_at=expires_at,
            current_room=first_room,
            current_stage=first_stage,
            rules_snapshot=rules_snapshot,
        )

        # Crear progreso inicial de rooms y stages (LOCKED por defecto)
        for room in escape_room.rooms.order_by("order"):
            UserRoomProgress.objects.create(
                session=session,
                room=room,
                status=UserRoomProgress.Status.LOCKED,
            )
            for stage in room.stages.order_by("order"):
                UserStageProgress.objects.create(
                    session=session,
                    stage=stage,
                    status=UserStageProgress.Status.LOCKED,
                )

        # La primera room y el primer stage pasan a AVAILABLE
        UserRoomProgress.objects.filter(
            session=session, room=first_room
        ).update(status=UserRoomProgress.Status.AVAILABLE)

        UserStageProgress.objects.filter(
            session=session, stage=first_stage
        ).update(status=UserStageProgress.Status.AVAILABLE)

    return session

# ──────────────────────────────────────────────────────────────
# Avance de fase
# ──────────────────────────────────────────────────────────────
def _next_stage_in_room(session, room):
    """Siguiente stage de la room actual, o None si no queda."""
    return (
        room.stages.filter(order__gt=session.current_stage.order)
        .order_by("order")
        .first()
    )


def _first_stage_of_room(room):
    return room.stages.order_by("order").first()


def _next_room(session):
    """Siguiente room en orden, o None si no queda."""
    return (
        session.escape_room.rooms.filter(order__gt=session.current_room.order)
        .order_by("order")
        .first()
    )


def _first_room(session):
    return session.escape_room.rooms.order_by("order").first()


def advance_session(session, puzzle):
    """
    Avanza el puntero del jugador tras un acierto.
    Devuelve True si la sesión se ha completado, False si sigue en curso.
    """
    with transaction.atomic():
        session.score += puzzle.points

        next_stage = _next_stage_in_room(session, puzzle.room)
        if next_stage is not None:
            session.current_stage = next_stage
            session.save(update_fields=["score", "current_stage"])
            return False

        # Se acabaron los stages de esta room → siguiente room
        next_room = _next_room(session)
        if next_room is not None:
            first_stage = _first_stage_of_room(next_room)
            session.current_room = next_room
            session.current_stage = first_stage
            session.save(update_fields=["score", "current_room", "current_stage"])
            return False

        # No quedan rooms → COMPLETED
        session.status = UserEscapeSession.Status.COMPLETED
        session.finished_at = timezone.now()
        session.save(update_fields=["score", "status", "finished_at"])
        settle_session(session, reason=EscapeSettlement.Reason.COMPLETED)
        return True


# ──────────────────────────────────────────────────────────────
# Pistas
# ──────────────────────────────────────────────────────────────
def use_hint(session, hint):
    """
    Aplica una pista como máximo una vez por (session, hint).

    Devuelve True si se ha aplicado, False si ya estaba usada.

    Toda la operación es atómica: o se crea el HintUsage, se actualiza
    el score y se actualiza expires_at, o no se hace nada. Si algo falla
    a mitad, la transacción se revierte y no quedan datos inconsistentes.
    """
    with transaction.atomic():
        # 1. Evitar doble compra en la misma sesión.
        #    select_for_update bloquea la fila del HintUsage existente (si la hay)
        #    para que dos peticiones concurrentes no creen dos usos a la vez.
        existing = (
            HintUsage.objects
            .select_for_update()
            .filter(session=session, hint=hint)
            .first()
        )
        if existing:
            return False

        # 2. Bloquear la sesión para que nadie más la modifique mientras
        #    actualizamos score y expires_at. Sin esto, dos pistas compradas
        #    a la vez podrían pisarse los cambios.
        session = (
            UserEscapeSession.objects
            .select_for_update()
            .get(pk=session.pk)
        )

        # 3. Registrar el uso con copia de las penalizaciones del Hint.
        #    Copiamos los valores para que un cambio futuro del Hint no
        #    reescriba partidas ya jugadas.
        HintUsage.objects.create(
            session=session,
            hint=hint,
            player=session.user,
            score_penalty=hint.penalty_points,
            time_penalty=hint.penalty_seconds,
            coins_charged=hint.coin_price,
        )

        # 4. Aplicar penalización de puntos al score de la sesión.
        #    max(0, ...) evita que el score quede negativo.
        session.score = max(0, session.score - hint.penalty_points)

        # 5. Aplicar penalización de tiempo: restar segundos a expires_at.
        #    Si la sesión no tiene expires_at (no ha empezado), no hacemos nada.
        if hint.penalty_seconds and session.expires_at:
            session.expires_at = (
                session.expires_at - timedelta(seconds=hint.penalty_seconds)
            )

        # 6. Guardar solo los campos que hemos tocado.
        session.save(update_fields=["score", "expires_at", "updated_at"])

        return True


# ──────────────────────────────────────────────────────────────
# Registro de intentos (correcto o incorrecto)
# ──────────────────────────────────────────────────────────────
def register_attempt(*, session, puzzle, answer, is_correct):
    """Registra el intento, actualiza UserStageProgress y, si procede,
    avanza la sesión o la marca como fallida.

    Devuelve un dict con:
        - is_correct: bool
        - completed: bool (la aventura entera se ha completado)
        - failed: bool (la sesión ha fallado por errores)
    """
    with transaction.atomic():
        # 1. Crear el intento en el historial
        attempt_no = (
            session.puzzle_attempts
            .filter(puzzle=puzzle)
            .count()
            + 1
        )
        PuzzleAttempt.objects.create(
            session=session,
            puzzle=puzzle,
            player=session.user,
            attempt_no=attempt_no,
            answer={"value": answer},
            is_correct=is_correct,
        )

        # 2. Actualizar UserStageProgress (siempre, acierto o fallo)
        stage_progress = UserStageProgress.objects.select_for_update().get(
            session=session,
            stage=puzzle.stage,
        )
        stage_progress.attempts += 1

        # Si es el primer intento, marcar la stage como IN_PROGRESS
        if stage_progress.status == UserStageProgress.Status.AVAILABLE:
            stage_progress.status = UserStageProgress.Status.IN_PROGRESS
            stage_progress.started_at = timezone.now()

        if is_correct:
            # 2a. Marcar la stage como resuelta
            stage_progress.is_solved = True
            stage_progress.status = UserStageProgress.Status.COMPLETED
            stage_progress.completed_at = timezone.now()
            stage_progress.fragment_acquired = puzzle.stage.fragment

            # 2b. Calcular XP bruta (placeholder: puntos del puzzle)
            stage_progress.gross_xp = puzzle.points * XP_PER_POINT
            stage_progress.penalty_xp = 0  # se rellenará al liquidar
            stage_progress.net_xp = max(
                0,
                stage_progress.gross_xp - stage_progress.penalty_xp,
            )

        stage_progress.save(update_fields=[
            "attempts",
            "status",
            "started_at",
            "is_solved",
            "completed_at",
            "fragment_acquired",
            "gross_xp",
            "penalty_xp",
            "net_xp",
        ])

        # 3. Si es correcto, avanzar la sesión
        if is_correct:
            completed = advance_session(session, puzzle)
            return {
                "is_correct": True,
                "completed": completed,
                "failed": False,
            }

        # 4. Si es incorrecto, contar errores desde PuzzleAttempt
        mistakes_count = (
            session.puzzle_attempts
            .filter(is_correct=False)
            .count()
        )

        if mistakes_count >= MAX_MISTAKES:
            session.status = UserEscapeSession.Status.FAILED
            session.finished_at = timezone.now()
            session.save(update_fields=["status", "finished_at"])
            # Liquidar la sesión fallida
            settle_session(session, reason=EscapeSettlement.Reason.FAILED)
            return {
                "is_correct": False,
                "completed": False,
                "failed": True,
            }

        return {
            "is_correct": False,
            "completed": False,
            "failed": False,
        }
# ──────────────────────────────────────────────────────────────
# Liquidación de la partida
# ──────────────────────────────────────────────────────────────
def settle_session(session, *, reason):
    """
    Crea (o devuelve) el EscapeSettlement de una sesión.

    - gross_xp: suma de UserStageProgress.gross_xp de la sesión.
    - penalty_xp: suma de UserStageProgress.penalty_xp + HintUsage.score_penalty.
    - final_xp: max(0, gross_xp - penalty_xp).
    - bonus_xp y bonus_coins: solo si reason == COMPLETED.
    - Marca session.settled_at.

    Es idempotente: si ya existe un EscapeSettlement para la sesión,
    lo devuelve sin crear otro.
    """
    # 1. Idempotencia: si ya está liquidada, devolver la existente
    existing = EscapeSettlement.objects.filter(session=session).first()
    if existing is not None:
        return existing

    # 2. Validar que la sesión esté en un estado liquidable
    liquidable_statuses = {
        UserEscapeSession.Status.COMPLETED,
        UserEscapeSession.Status.FAILED,
        UserEscapeSession.Status.ABANDONED,
    }
    if session.status not in liquidable_statuses:
        raise ValueError(
            f"No se puede liquidar una sesión en estado {session.status}."
        )

    # 3. Normalizar reason a las opciones del model
    valid_reasons = {choice[0] for choice in EscapeSettlement.Reason.choices}
    if reason not in valid_reasons:
        raise ValueError(f"reason inválido: {reason}")

    with transaction.atomic():
        # 4. Calcular gross_xp desde UserStageProgress
        stage_progress_qs = UserStageProgress.objects.filter(session=session)
        gross_xp = (
            stage_progress_qs.aggregate(total=models.Sum("gross_xp"))["total"] or 0
        )

        # 5. Calcular penalty_xp:
        #    - stage_progress.penalty_xp (penalizaciones por stage)
        #    - hint_usages.score_penalty (penalizaciones por pistas)
        stage_penalty = (
            stage_progress_qs.aggregate(total=models.Sum("penalty_xp"))["total"] or 0
        )
        hint_penalty = (
            HintUsage.objects
            .filter(session=session)
            .aggregate(total=models.Sum("score_penalty"))["total"] or 0
        )
        penalty_xp = stage_penalty + hint_penalty

        # 6. final_xp nunca negativo
        final_xp = max(0, gross_xp - penalty_xp)

        # 7. Bonus: solo si COMPLETED
        bonus_xp = 0
        bonus_coins = 0
        if reason == EscapeSettlement.Reason.COMPLETED:
            # Valores provisionales de Fase 1. Ecomotor los sustituirá
            # por reglas versionadas en Fase 2.
            bonus_xp = 10
            bonus_coins = 5

        # 8. Crear el settlement
        settlement = EscapeSettlement.objects.create(
            session=session,
            gross_xp=gross_xp,
            penalty_xp=penalty_xp,
            final_xp=final_xp,
            bonus_xp=bonus_xp,
            bonus_coins=bonus_coins,
            reason=reason,
        )

        # 9. Marcar la sesión como liquidada
        session.settled_at = timezone.now()
        session.save(update_fields=["settled_at"])

    return settlement
# ──────────────────────────────────────────────────────────────
# Búsqueda de pista disponible
# ──────────────────────────────────────────────────────────────
def get_available_hint(session, stage):
    """
    Devuelve el Hint disponible para la stage actual, o None si no hay.

    Prioridad:
    1. Pista que cuelga de un Puzzle de la stage.
    2. Pista que cuelga de la Room de la stage.

    Si la pista ya ha sido usada en esta sesión, devuelve None
    (para que el template no muestre el botón de comprar otra vez).
    """
    # 1. Buscar pista de puzzle
    hint = (
        Hint.objects
        .filter(puzzle__stage=stage)
        .order_by("order")
        .first()
    )
    # 2. Si no hay, buscar pista de room
    if hint is None:
        hint = (
            Hint.objects
            .filter(room=stage.room)
            .order_by("order")
            .first()
        )
    if hint is None:
        return None

    # 3. Si ya se usó en esta sesión, no ofrecerla de nuevo
    already_used = HintUsage.objects.filter(session=session, hint=hint).exists()
    if already_used:
        return None

    return hint