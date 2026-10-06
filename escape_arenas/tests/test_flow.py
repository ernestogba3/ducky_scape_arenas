from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from escape_arenas.models import EscapeRoom, EscapeStage, EscapeSession

User = get_user_model()


class EscapeFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="player", password="x")
        self.client = Client()
        self.client.login(username="player", password="x")

        self.room = EscapeRoom.objects.create(
            title="R", slug="r", description="d",
            theme=EscapeRoom.Theme.PYTHON, creator=self.user,
            is_published=True, time_limit_minutes=30,
        )
        EscapeStage.objects.create(
            room=self.room, order=1, title="F1", statement="s",
            category=EscapeStage.Category.PYTHON,
            answer_type=EscapeStage.AnswerType.EXACT,
            expected_answer="42", points=100,
        )
        EscapeStage.objects.create(
            room=self.room, order=2, title="F2", statement="s",
            category=EscapeStage.Category.PYTHON,
            answer_type=EscapeStage.AnswerType.EXACT,
            expected_answer="ok", points=100,
        )

    def test_full_flow(self):
        self.client.post(reverse("escape_arenas:start", args=["r"]))
        session = EscapeSession.objects.get(player=self.user)
        self.assertEqual(session.status, "ACTIVE")

        self.client.post(
            reverse("escape_arenas:answer", args=[session.pk]),
            {"answer": "mal"},
        )
        session.refresh_from_db()
        self.assertEqual(session.current_order, 1)
        self.assertEqual(session.wrong_attempts, 1)

        self.client.post(
            reverse("escape_arenas:answer", args=[session.pk]),
            {"answer": "42"},
        )
        session.refresh_from_db()
        self.assertEqual(session.current_order, 2)

        self.client.post(
            reverse("escape_arenas:answer", args=[session.pk]),
            {"answer": "ok"},
        )
        session.refresh_from_db()
        self.assertEqual(session.status, "COMPLETED")

    def test_cannot_answer_completed(self):
        session = EscapeSession.objects.create(
            room=self.room, player=self.user,
            status=EscapeSession.Status.COMPLETED,
        )
        response = self.client.post(
            reverse("escape_arenas:answer", args=[session.pk]),
            {"answer": "42"},
        )
        self.assertNotEqual(response.status_code, 200)