from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from escape_arenas.models import EscapeRoom, EscapeStage, EscapeSession

User = get_user_model()


class EscapeRoomModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="profe", password="x")

    def test_create_room(self):
        room = EscapeRoom.objects.create(
            title="Test", slug="test",
            description="d", theme=EscapeRoom.Theme.PYTHON,
            creator=self.user,
        )
        self.assertEqual(str(room), "Test")

    def test_unique_stage_order_per_room(self):
        room = EscapeRoom.objects.create(
            title="R", slug="r", description="d",
            theme=EscapeRoom.Theme.PYTHON, creator=self.user,
        )
        EscapeStage.objects.create(
            room=room, order=1, title="A", statement="s",
            category=EscapeStage.Category.PYTHON,
            answer_type=EscapeStage.AnswerType.EXACT,
            expected_answer="x",
        )
        with self.assertRaises(IntegrityError):
            EscapeStage.objects.create(
                room=room, order=1, title="B", statement="s",
                category=EscapeStage.Category.PYTHON,
                answer_type=EscapeStage.AnswerType.EXACT,
                expected_answer="y",
            )

    def test_multiple_sessions_per_user(self):
        room = EscapeRoom.objects.create(
            title="R", slug="r", description="d",
            theme=EscapeRoom.Theme.PYTHON, creator=self.user,
        )
        s1 = EscapeSession.objects.create(room=room, player=self.user)
        s2 = EscapeSession.objects.create(room=room, player=self.user)
        self.assertNotEqual(s1.pk, s2.pk)
        self.assertEqual(self.user.escape_sessions.count(), 2)