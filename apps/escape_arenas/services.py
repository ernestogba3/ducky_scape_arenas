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

def advance_session(*, session, stage, answer):
    with transaction.atomic():
        # 1. Registrar el intento correcto
        EscapeAttempt.objects.create(
            session=session,
            stage=stage,
            submitted_answer=answer,
            is_correct=True,
        )

        # 2. Sumar puntos
        session.score += stage.points

        # 3. Avanzar a la siguiente fase
        session.current_order += 1

        # 4. Guardar los cambios
        session.save(update_fields=["score", "current_order"])

        # 5. Comprobar si queda una nueva fase
        next_stage = session.room.stages.filter(
            order=session.current_order
        ).first()

        if next_stage is None:
            # No quedan más fases → completar la sala
            session.status = EscapeSession.Status.COMPLETED
            session.finished_at = timezone.now()
            session.save(update_fields=["status", "finished_at"])

    return session