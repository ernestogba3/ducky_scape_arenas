from django.test import TestCase

# Create your tests here.
#Para las prubas un usuario y 
def create_user_and_escape_room():
    user = User.objects.create_user(username="test", password="test")
    escape_room = EscapeRoom.objects.create(
        name="Test Room",
        slug="test-room",
        description="...",
        time_limit_seconds=1800,
        final_solution_hash="final",
        creator=user,  # si añades creator
    )
    room = Room.objects.create(
        escape_room=escape_room,
        name="Room 1",
        description="...",
        order=1,
        door_solution_hash="door",
        final_fragment="frag",
    )
    stage = Stage.objects.create(
        room=room,
        name="Stage 1",
        description="...",
        order=1,
        type=Stage.Type.PUZZLE,
        fragment="frag1",
    )
    puzzle = Puzzle.objects.create(
        stage=stage,
        title="Puzzle 1",
        description="...",
        type=Puzzle.Type.TEXT,
        solution_hash="respuesta",
        points=10,
        order=1,
    )
    return user, escape_room, room, stage, puzzle

class GameFlowTests(TestCase):
    def setUp(self):
        self.user, self.escape_room, self.room, self.stage, self.puzzle = (
            create_user_and_escape_room()
        )
        self.client.force_login(self.user)

    def test_start_creates_session(self):
        response = self.client.post(
            reverse("escape_arenas:escape_start", kwargs={"slug": self.escape_room.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(UserEscapeSession.objects.count(), 1)
        session = UserEscapeSession.objects.first()
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.status, UserEscapeSession.Status.PLAYING)
        self.assertIsNotNone(session.started_at)
        self.assertIsNotNone(session.expires_at)
        self.assertEqual(session.current_room, self.room)
        self.assertEqual(session.current_stage, self.stage)

    def test_submit_correct_answer_advances(self):
        session = start_session(user=self.user, escape_room=self.escape_room)
        response = self.client.post(
            reverse("escape_arenas:submit", kwargs={"pk": session.pk}),
            {"answer": "respuesta"},
        )
        self.assertEqual(response.status_code, 302)
        session.refresh_from_db()
        # Si era la última stage, la sesión se completa
        self.assertEqual(session.status, UserEscapeSession.Status.COMPLETED)
        # Se ha creado un PuzzleAttempt
        self.assertEqual(PuzzleAttempt.objects.filter(session=session).count(), 1)
        # El UserStageProgress está resuelto
        stage_progress = UserStageProgress.objects.get(session=session, stage=self.stage)
        self.assertTrue(stage_progress.is_solved)

    def test_submit_wrong_answer_does_not_advance(self):
        session = start_session(user=self.user, escape_room=self.escape_room)
        response = self.client.post(
            reverse("escape_arenas:submit", kwargs={"pk": session.pk}),
            {"answer": "mal"},
        )
        session.refresh_from_db()
        self.assertEqual(session.status, UserEscapeSession.Status.PLAYING)
        self.assertEqual(session.current_stage, self.stage)
        self.assertEqual(PuzzleAttempt.objects.filter(session=session, is_correct=False).count(), 1)
    
    def test_hint_creates_usage_and_discounts(self):
        # Crear un Hint para el puzzle
        hint = Hint.objects.create(
            puzzle=self.puzzle,
            text="Pista de prueba",
            order=1,
            coin_price=5,
            penalty_points=3,
            penalty_seconds=60,
        )
        session = start_session(user=self.user, escape_room=self.escape_room)
        session.score = 10
        session.save()

        response = self.client.post(
            reverse("escape_arenas:hint", kwargs={"pk": session.pk})
        )
        session.refresh_from_db()
        self.assertEqual(session.score, 7)  # 10 - 3
        self.assertEqual(HintUsage.objects.filter(session=session).count(), 1)
    
    def test_hint_twice_does_not_duplicate(self):
        hint = Hint.objects.create(puzzle=self.puzzle, text="...", order=1, penalty_points=3)
        session = start_session(user=self.user, escape_room=self.escape_room)
        self.client.post(reverse("escape_arenas:hint", kwargs={"pk": session.pk}))
        self.client.post(reverse("escape_arenas:hint", kwargs={"pk": session.pk}))
        self.assertEqual(HintUsage.objects.filter(session=session).count(), 1)

    def test_expired_session_fails(self):
        session = start_session(user=self.user, escape_room=self.escape_room)
        # Forzar expiración
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save()
        response = self.client.get(
            reverse("escape_arenas:play", kwargs={"pk": session.pk})
        )
        session.refresh_from_db()
        self.assertEqual(session.status, UserEscapeSession.Status.FAILED)
        self.assertRedirects(response, reverse("escape_arenas:result", kwargs={"pk": session.pk}))

    def test_other_user_cannot_access_session(self):
        other = User.objects.create_user(username="other", password="other")
        session = start_session(user=self.user, escape_room=self.escape_room)
        self.client.force_login(other)
        response = self.client.get(
            reverse("escape_arenas:play", kwargs={"pk": session.pk})
        )
        self.assertEqual(response.status_code, 404)