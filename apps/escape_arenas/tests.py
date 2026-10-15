"""Pruebas de regresión del contrato MVP del miembro 3."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import EscapeRoom, Room, Stage, Puzzle, Hint, UserEscapeSession
from .services import start_session, check_stage_answer, register_attempt, get_remaining_seconds, expire_session_if_needed, use_hint

class EscapeTests(TestCase):
    fixtures = ['escape_demo']
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user('alumna',password='Prueba-segura-2026')
        cls.other=get_user_model().objects.create_user('otra',password='Prueba-segura-2026')
        cls.room=EscapeRoom.objects.get(slug='full-stack-lockdown')
    def setUp(self):
        self.client.force_login(self.user)
    def start(self):
        return start_session(user=self.user,escape_room=self.room)
    def url(self,name,s):
        return reverse('escape_arenas:'+name,args=[s.pk])
    def submit(self,s,answer,**extra):
        return self.client.post(self.url('submit',s),{'puzzle_id':s.current_stage.puzzles.get().pk,'answer':answer,**extra})
    def test_content_eight_phases(self):
        stages=Stage.objects.filter(room__escape_room=self.room).order_by('order')
        self.assertEqual(list(stages.values_list('order',flat=True)),list(range(1,9)))
        for stage in stages:
            puzzle=stage.puzzles.get()
            self.assertTrue(puzzle.hints.exists())
            self.assertFalse(puzzle.solution_hash.startswith('placeholder'))
            self.assertTrue(check_stage_answer(puzzle=puzzle,submitted_answer=puzzle.solution_hash))
    def test_catalog_detail_and_filters(self):
        url=reverse('escape_arenas:room_list')
        self.assertContains(self.client.get(url),'Full Stack Lockdown')
        self.assertNotContains(self.client.get(url,{'q':'imposible'}),'Explorar misión')
        self.assertNotContains(self.client.get(url,{'difficulty':'HARD'}),'Explorar misión')
        self.assertContains(self.client.get(reverse('escape_arenas:room_detail',args=[self.room.slug])),'800')
    def test_inactive_hidden(self):
        self.room.is_active=False;self.room.save()
        self.assertNotContains(self.client.get(reverse('escape_arenas:room_list')),'Explorar misión')
        self.assertEqual(self.client.post(reverse('escape_arenas:escape_start',args=[self.room.slug])).status_code,404)
    def test_login_required(self):
        self.client.logout()
        self.assertRedirects(self.client.get(reverse('escape_arenas:room_list')),'/accounts/login/?next=/escape/')
    def test_start_resume(self):
        url=reverse('escape_arenas:escape_start',args=[self.room.slug])
        self.client.post(url);self.client.post(url)
        self.assertEqual(UserEscapeSession.objects.count(),1)
        self.assertEqual(UserEscapeSession.objects.get().stage_progress.count(),8)
    def test_get_cannot_mutate(self):
        s=self.start()
        for name in ['submit','hint']:self.assertEqual(self.client.get(self.url(name,s)).status_code,405)
        self.assertEqual(self.client.get(reverse('escape_arenas:escape_start',args=[self.room.slug])).status_code,405)
    def test_wrong_does_not_advance(self):
        s=self.start();stage=s.current_stage_id
        self.submit(s,'incorrecta');s.refresh_from_db()
        self.assertEqual(s.current_stage_id,stage);self.assertEqual(s.score,0)
        self.assertFalse(s.puzzle_attempts.get().is_correct)
    def test_full_flow_and_room_transition(self):
        second=Room.objects.create(escape_room=self.room,name='Salida',order=2,description='Final',door_solution_hash='',final_fragment='Abierta')
        Stage.objects.filter(room__escape_room=self.room,order__gt=4).update(room=second)
        s=self.start();self.submit(s,'incorrecta')
        for _ in range(8):
            s.refresh_from_db();self.submit(s,s.current_stage.puzzles.get().solution_hash)
        s.refresh_from_db()
        self.assertEqual(s.status,'COMPLETED');self.assertEqual(s.score,800)
        self.assertEqual(s.puzzle_attempts.count(),9)
        self.assertEqual(s.stage_progress.filter(is_solved=True).count(),8)
        self.assertEqual(s.room_progress.filter(status='COMPLETED').count(),2)
        self.assertEqual(s.settlement.final_xp,800)
        self.assertContains(self.client.get(self.url('result',s)),'¡Has escapado!')
    def test_terminal_rejects_answer_and_hint(self):
        for status in ['COMPLETED','FAILED','ABANDONED']:
            s=self.start();s.status=status;s.save()
            self.submit(s,'#salida');self.client.post(self.url('hint',s))
            self.assertFalse(s.puzzle_attempts.exists());self.assertFalse(s.hint_usages.exists())
    def test_stale_form_rejected(self):
        s=self.start();old=s.current_stage.puzzles.get().pk
        self.submit(s,'#salida');s.refresh_from_db();self.submit(s,'6',puzzle_id=old)
        self.assertEqual(s.puzzle_attempts.count(),1)
    def test_client_cannot_choose_result(self):
        s=self.start();deadline=s.expires_at
        self.submit(s,'bad',score=9999,is_correct=True,remaining_seconds=99999,stage_id=1008)
        s.refresh_from_db();self.assertEqual(s.score,0);self.assertEqual(s.expires_at,deadline)
        self.assertFalse(s.puzzle_attempts.get().is_correct)
    def test_html_hides_solutions_future_phases_and_unbought_hints(self):
        s=self.start();p=s.current_stage.puzzles.get();p.solution_hash='SECRETO-NO-ENVIAR';p.save()
        Stage.objects.filter(pk=1008).update(description='FASE-FUTURA-SECRETA')
        page=self.client.get(self.url('play',s))
        for secret in ['SECRETO-NO-ENVIAR','solution_hash','FASE-FUTURA-SECRETA','Un selector de id comienza']:
            self.assertNotContains(page,secret)
    def test_html_escape(self):
        s=self.start();s.current_stage.description='<script>alert(1)</script>';s.current_stage.save()
        page=self.client.get(self.url('play',s))
        self.assertContains(page,'&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(page,'<script>alert(1)</script>')
    def test_other_user_blocked(self):
        s=self.start();self.client.force_login(self.other)
        for name in ['play','result']:self.assertEqual(self.client.get(self.url(name,s)).status_code,404)
        for name in ['submit','hint']:self.assertEqual(self.client.post(self.url(name,s)).status_code,404)
    def test_csrf(self):
        s=self.start();client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        for url in [self.url('submit',s),self.url('hint',s),reverse('escape_arenas:escape_start',args=[self.room.slug])]:
            self.assertEqual(client.post(url).status_code,403)
        client.get(self.url('play',s));token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url('submit',s),{'answer':'#salida','puzzle_id':1001,'csrfmiddlewaretoken':token}).status_code,302)
        self.assertEqual(s.puzzle_attempts.count(),1)
    def test_deadline_before_at_after(self):
        for offset,status in [(-1,'PLAYING'),(0,'FAILED'),(1,'FAILED')]:
            s=self.start()
            with patch('apps.escape_arenas.services.timezone.now',return_value=s.expires_at+timedelta(seconds=offset)):
                self.submit(s,'#salida')
            s.refresh_from_db();self.assertEqual(s.status,status)
            self.assertEqual(s.puzzle_attempts.count(),1 if offset<0 else 0)
    def test_seconds_and_fractional_last_second(self):
        s=self.start()
        with patch('apps.escape_arenas.services.timezone.now',return_value=s.started_at):self.assertEqual(get_remaining_seconds(s),1800)
        with patch('apps.escape_arenas.services.timezone.now',return_value=s.expires_at-timedelta(milliseconds=100)):
            self.assertEqual(get_remaining_seconds(s),1);self.assertFalse(expire_session_if_needed(s))
    def test_hint_once_and_final_score(self):
        s=self.start();hint=Hint.objects.get(pk=1001);deadline=s.expires_at
        for _ in range(2):self.client.post(self.url('hint',s),{'hint_id':hint.pk})
        s.refresh_from_db();self.assertEqual(s.hint_usages.count(),1)
        self.assertEqual(s.expires_at,deadline-timedelta(seconds=30))
        self.assertContains(self.client.get(self.url('play',s)),hint.text)
        for _ in range(8):
            s.refresh_from_db();self.submit(s,s.current_stage.puzzles.get().solution_hash)
        s.refresh_from_db();self.assertEqual(s.score,775)
        self.assertEqual(s.settlement.penalty_xp,25);self.assertEqual(s.settlement.bonus_coins,0)
    def test_hint_can_expire(self):
        s=self.start();s.expires_at=timezone.now()+timedelta(seconds=10);s.save()
        use_hint(s,Hint.objects.get(pk=1001));s.refresh_from_db()
        self.assertEqual(s.status,'FAILED');self.assertEqual(s.settlement.reason,'TIME_EXPIRED')
    def test_hint_other_phase_delay_and_coins(self):
        s=self.start();self.assertFalse(use_hint(s,Hint.objects.get(pk=1002)))
        hint=Hint.objects.get(pk=1001);hint.unlock_after_seconds=60;hint.save()
        self.assertFalse(use_hint(s,hint))
        hint.unlock_after_seconds=0;hint.coin_price=5;hint.save();self.assertFalse(use_hint(s,hint))
    def test_attempt_limit_and_unlimited(self):
        s=self.start();p=s.current_stage.puzzles.get()
        for _ in range(6):register_attempt(session=s,puzzle=p,answer='bad')
        self.assertEqual(s.status,'PLAYING')
        p.max_attempts=7;p.save();register_attempt(session=s,puzzle=p,answer='bad')
        self.assertEqual(s.status,'FAILED')
    def test_service_ignores_correctness_argument(self):
        s=self.start();register_attempt(session=s,puzzle=s.current_stage.puzzles.get(),answer='bad',is_correct=True)
        self.assertFalse(s.puzzle_attempts.get().is_correct)
    def test_validation_modes(self):
        p=Puzzle.objects.get(pk=1001);p.solution_hash='git status'
        for mode,answer,ok in [('EXACT',' git status ',True),('EXACT','GIT STATUS',False),('CASE_INSENSITIVE','GIT STATUS',True),('CASE_INSENSITIVE','git log',False)]:
            p.config={'answer_mode':mode};self.assertEqual(check_stage_answer(puzzle=p,submitted_answer=answer),ok)
        self.assertFalse(check_stage_answer(puzzle=p,submitted_answer='__import__("os").system("echo peligro")'))
    def test_model_constraints(self):
        stage=Stage.objects.get(pk=1001)
        with self.assertRaises(IntegrityError),transaction.atomic():Stage.objects.create(room=stage.room,order=1,name='Duplicada',description='x')
        with self.assertRaises(IntegrityError),transaction.atomic():Hint.objects.create(text='Sin destino')
    def test_multiple_sessions_and_history_protection(self):
        s=self.start();self.start();self.assertEqual(self.user.escape_sessions.count(),2)
        with self.assertRaises(ProtectedError):self.room.delete()
        self.assertTrue(str(s));self.assertTrue(str(s.current_stage))
    def test_private_history_and_completed_only_ranking(self):
        self.start()
        self.assertContains(self.client.get(reverse('escape_arenas:history')),'Full Stack Lockdown')
        self.assertNotContains(self.client.get(reverse('escape_arenas:ranking',args=[self.room.slug])),'<td>alumna</td>')
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('escape_arenas:history')),'Todavía no has iniciado')
    def test_seed_is_idempotent(self):
        out=StringIO();call_command('seed_escape',stdout=out)
        self.assertIn('conserva',out.getvalue());self.assertEqual(EscapeRoom.objects.count(),1)
    def test_incomplete_content_cannot_start(self):
        p=Puzzle.objects.get(pk=1001);p.solution_hash='placeholder_respuesta';p.save()
        with self.assertRaises(ValueError):self.start()
    def test_student_cannot_edit_admin(self):
        response=self.client.get('/admin/escape_arenas/escaperoom/1001/change/')
        self.assertEqual(response.status_code,302);self.assertIn('/admin/login/',response.url)
