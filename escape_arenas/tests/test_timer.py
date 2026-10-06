from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from escape_arenas.models import EscapeRoom, EscapeStage, EscapeSession

User = get_user_model()


class TimerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="p", password="x")
        self.room = EscapeRoom.objects.create(
            title="R", slug="r", description="d",
            theme=EscapeRoom.Theme.PYTHON, creator=self.user,
            is_published=True, time_limit_minutes=1,
        )
        EscapeStage.objects.create(
            room=self.room, order=1, title="F1", statement="s",
            category=EscapeStage.Category.PYTHON,
            answer_type=EscapeStage.AnswerType.EXACT,
            expected_answer="42",
        )

    def _session(self, started):
        return EscapeSession.objects.create(
            room=self.room, player=self.user, started_at=started,
        )

    def test_inside_time(self):
        s = self._session(timezone.now() - timedelta(seconds=30))
        deadline = s.started_at + timedelta(minutes=1)
        self.assertLess(timezone.now(), deadline)

    def test_exactly_at_limit(self):
        s = self._session(timezone.now() - timedelta(minutes=1))
        deadline = s.started_at + timedelta(minutes=1)
        self.assertGreaterEqual(timezone.now(), deadline)

    def test_out_of_time(self):
        s = self._session(timezone.now() - timedelta(minutes=5))
        deadline = s.started_at + timedelta(minutes=1)
        self.assertGreater(timezone.now(), deadline)