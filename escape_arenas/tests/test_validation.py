from django.test import TestCase
from escape_arenas.models import EscapeStage
from escape_arenas.services import check_stage_answer


class ValidationTests(TestCase):
    def _stage(self, answer_type, expected):
        return EscapeStage(answer_type=answer_type, expected_answer=expected)

    def test_exact(self):
        stage = self._stage(EscapeStage.AnswerType.EXACT, "32")
        self.assertTrue(check_stage_answer(stage=stage, submitted_answer="32"))
        self.assertTrue(check_stage_answer(stage=stage, submitted_answer=" 32 "))
        self.assertFalse(check_stage_answer(stage=stage, submitted_answer="31"))

    def test_case_insensitive(self):
        stage = self._stage(EscapeStage.AnswerType.CASE_INSENSITIVE, "git status")
        self.assertTrue(check_stage_answer(stage=stage, submitted_answer="git status"))
        self.assertTrue(check_stage_answer(stage=stage, submitted_answer="GIT STATUS"))
        self.assertFalse(check_stage_answer(stage=stage, submitted_answer="git log"))