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