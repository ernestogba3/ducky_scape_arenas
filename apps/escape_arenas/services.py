# TODO: reescribir en Fase 2 con las operaciones transaccionales descritas
# en el documento (sección 11): start_session, submit_puzzle_answer,
# purchase_hint, complete_stage, settle_session.
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    HintUsage,
    PuzzleAttempt,
    UserEscapeSession,
    UserRoomProgress,
    UserStageProgress,
)

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
    if session.status != UserEscapeSession.Status.COMPLETED:
        return False
    if get_remaining_seconds(session) > 0:
        return False

    session.status = UserEscapeSession.Status.FAILED
    session.finished_at = timezone.now()
    session.save(update_fields=["status", "finished_at"])
    return True


# ──────────────────────────────────────────────────────────────
# Validación de respuestas
# ──────────────────────────────────────────────────────────────
def normalize(text):
    """Normalización mínima y predecible. No elimina caracteres arbitrariamente."""
    return text.strip().lower()


def check_stage_answer(*, stage, submitted_answer):
    """Compara la respuesta del jugador con la esperada. El servidor decide."""
    puzzle = stage.puzzles.order_by("order").first()
    if puzzle is None:
        return False  # Stage sin puzzles: no se puede validar

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


def advance_session(session, stage):
    """
    Avanza el puntero del jugador tras un acierto.
    Devuelve True si la sesión se ha completado, False si sigue en curso.
    """
    with transaction.atomic():
        session.score += stage.points

        next_stage = _next_stage_in_room(session, stage.room)
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
        return True


# ──────────────────────────────────────────────────────────────
# Pistas
# ──────────────────────────────────────────────────────────────
def use_hint(session, stage):
    """
    Aplica una pista como máximo una vez por (session, stage).
    Devuelve True si se ha aplicado, False si ya estaba usada.
    """
   # 1. Evitar doble compra en la misma sesión
    existing = HintUsage.objects.filter(session=session, hint=hint).first()
    if existing:
        return False

    # 2. Registrar el uso con copia de las penalizaciones del Hint
    usage = HintUsage.objects.create(
        session=session,
        hint=hint,
        player=session.user,
        score_penalty=hint.penalty_points,
        time_penalty=hint.penalty_seconds,
        coins_charged=hint.coin_price,
    )

    # 3. Aplicar penalización de puntos al score de la sesión
    session.score = max(0, session.score - hint.penalty_points)

    # 4. Aplicar penalización de tiempo: extender expires_at hacia atrás
    if hint.penalty_seconds and session.expires_at:
        session.expires_at = session.expires_at - timedelta(seconds=hint.penalty_seconds)

    session.save(update_fields=["score", "expires_at"])
    return True


# ──────────────────────────────────────────────────────────────
# Registro de intentos (correcto o incorrecto)
# ──────────────────────────────────────────────────────────────
def register_attempt(*, session, stage, answer, is_correct):
    """Registra el intento y actualiza los contadores de la sesión."""
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

    # 2. Si es correcto, avanzar la sesión
    if is_correct:
        completed = advance_session(session, puzzle.stage)
        return {"is_correct": True, "completed": completed}

    # 3. Si es incorrecto, contar errores desde PuzzleAttempt
    mistakes_count = (
        session.puzzle_attempts
        .filter(is_correct=False)
        .count()
    )

    MAX_MISTAKES = 5
    if mistakes_count >= MAX_MISTAKES:
        session.status = UserEscapeSession.Status.FAILED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])

    return {"is_correct": False, "completed": False}
