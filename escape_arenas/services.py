from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    EscapeAttempt,
    EscapeHintUse,
    EscapeSession,
    Stage,
)


# ──────────────────────────────────────────────────────────────
# Temporizador
# ──────────────────────────────────────────────────────────────
def get_deadline(session):
    """Devuelve el instante límite de la sesión."""
    return session.started_at + timedelta(
        minutes=session.escape_room.time_limit_minutes
    )


def get_remaining_seconds(session):
    """Segundos que quedan. 0 si ya caducó."""
    remaining = (get_deadline(session) - timezone.now()).total_seconds()
    return max(0, int(remaining))


def expire_session_if_needed(session):
    """Marca FAILED si ha caducado. Devuelve True si expiró."""
    if session.status != EscapeSession.Status.IN_PROGRESS:
        return False
    if get_remaining_seconds(session) > 0:
        return False

    session.status = EscapeSession.Status.FAILED
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
    expected = normalize(stage.expected_answer)
    submitted = normalize(submitted_answer)
    return submitted == expected


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
        session.status = EscapeSession.Status.COMPLETED
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
    if not stage.hint_text:
        return False

    hint_use, created = EscapeHintUse.objects.get_or_create(
        session=session,
        stage=stage,
        defaults={"penalty": stage.hint_penalty},
    )
    if not created:
        return False

    session.score = max(0, session.score - stage.hint_penalty)
    session.hints_used += 1
    session.save(update_fields=["score", "hints_used"])
    return True


# ──────────────────────────────────────────────────────────────
# Registro de intentos (correcto o incorrecto)
# ──────────────────────────────────────────────────────────────
def register_attempt(*, session, stage, answer, is_correct):
    """
    Registra el intento y actualiza la sesión de forma atómica.
    Bloquea la fila de la sesión para evitar carreras.
    """
    with transaction.atomic():
        # 1. Bloquear la sesión (evita submits simultáneos)
        locked_session = (
            EscapeSession.objects
            .select_for_update()
            .get(pk=session.pk)
        )

        # 2. Si la sesión ya no está en curso, no hacemos nada
        if locked_session.status != EscapeSession.Status.IN_PROGRESS:
            return {"is_correct": False, "completed": False, "skipped": True}

        # 3. Registrar el intento
        EscapeAttempt.objects.create(
            session=locked_session,
            stage=stage,
            submitted_answer=answer,
            is_correct=is_correct,
        )

        # 4. Actualizar la sesión según acierto o fallo
        if is_correct:
            completed = advance_session(locked_session, stage)
            # Refrescar el objeto que recibió la vista para que el caller
            # vea el estado actualizado
            session.refresh_from_db()
            return {"is_correct": True, "completed": completed}

        # Fallo
        locked_session.mistakes_count += 1
        update_fields = ["mistakes_count"]

        MAX_MISTAKES = 5
        if locked_session.mistakes_count >= MAX_MISTAKES:
            locked_session.status = EscapeSession.Status.FAILED
            locked_session.finished_at = timezone.now()
            update_fields += ["status", "finished_at"]

        locked_session.save(update_fields=update_fields)
        session.refresh_from_db()
        return {"is_correct": False, "completed": False}