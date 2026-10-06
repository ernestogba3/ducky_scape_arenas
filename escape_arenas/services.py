# escape_arenas/services.py
from datetime import timedelta

from django.utils import timezone

from .models import AnswerType, EscapeSession


def expire_session_if_needed(session):
    """Marca la sesión como FAILED si ha pasado el deadline. Devuelve True si caducó."""
    deadline = session.started_at + timedelta(
        minutes=session.room.time_limit_minutes
    )
    if timezone.now() >= deadline:
        session.status = EscapeSession.Status.FAILED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        return True
    return False


def normalize_code(text):
    return text.strip().lower()


def check_stage_answer(*, stage, submitted_answer):
    expected = stage.expected_answer.strip()
    submitted = submitted_answer.strip()

    if stage.answer_type == AnswerType.EXACT:
        return submitted == expected
    if stage.answer_type == AnswerType.CASE_INSENSITIVE:
        return submitted.lower() == expected.lower()
    if stage.answer_type == AnswerType.NORMALIZED_CODE:
        return normalize_code(submitted) == normalize_code(expected)
    return False

