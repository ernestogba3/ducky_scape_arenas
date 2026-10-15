"""Motor seguro del MVP: una prueba por fase y recompensas locales."""
from datetime import timedelta
from math import ceil
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import (Stage, UserEscapeSession, UserRoomProgress, UserStageProgress,
                     PuzzleAttempt, Hint, HintUsage, EscapeSettlement)

def get_deadline(session):
    return session.expires_at

def get_remaining_seconds(session):
    return max(0,ceil((session.expires_at-timezone.now()).total_seconds())) if session.expires_at else 0

def normalize(text):
    return str(text).strip().casefold()

def check_stage_answer(*,puzzle,submitted_answer):
    if puzzle.config.get('answer_mode')=='EXACT':
        return str(submitted_answer).strip()==puzzle.solution_hash.strip()
    return normalize(submitted_answer)==normalize(puzzle.solution_hash)

@transaction.atomic
def start_session(*,user,escape_room):
    stages=list(Stage.objects.filter(room__escape_room=escape_room).select_related('room').prefetch_related('puzzles').order_by('room__order','order'))
    if not escape_room.is_active or not stages or any(not r.stages.exists() for r in escape_room.rooms.all()):
        raise ValueError('La aventura necesita habitaciones publicadas con fases jugables.')
    for stage in stages:
        puzzles=list(stage.puzzles.all())
        if len(puzzles)!=1:
            raise ValueError('El MVP requiere un puzzle en cada fase.')
        puzzle=puzzles[0]
        if not puzzle.solution_hash or puzzle.solution_hash.startswith('placeholder_'):
            raise ValueError('El contenido contiene soluciones provisionales.')
        if puzzle.config.get('answer_mode','CASE_INSENSITIVE') not in {'EXACT','CASE_INSENSITIVE'}:
            raise ValueError('Modo de comparación no compatible.')
        if puzzle.type=='MULTIPLE_CHOICE' and puzzle.solution_hash not in puzzle.config.get('options',[]):
            raise ValueError('La respuesta debe pertenecer a las opciones.')
    now=timezone.now()
    s=UserEscapeSession.objects.create(user=user,escape_room=escape_room,status='PLAYING',started_at=now,
        expires_at=now+timedelta(seconds=escape_room.time_limit_seconds),current_room=stages[0].room,current_stage=stages[0],
        rules_snapshot={'time_limit_seconds':escape_room.time_limit_seconds,'difficulty':escape_room.difficulty,'version':escape_room.version})
    for room in escape_room.rooms.all():
        first=room.pk==s.current_room_id
        UserRoomProgress.objects.create(session=s,room=room,status='AVAILABLE' if first else 'LOCKED',started_at=now if first else None)
    for stage in stages:
        first=stage.pk==s.current_stage_id
        UserStageProgress.objects.create(session=s,stage=stage,status='AVAILABLE' if first else 'LOCKED',started_at=now if first else None)
    return s

@transaction.atomic
def settle_session(session,*,reason):
    s=UserEscapeSession.objects.select_for_update().get(pk=session.pk)
    if s.status not in {'COMPLETED','FAILED','ABANDONED'}:
        raise ValueError('La sesión todavía está activa.')
    existing=EscapeSettlement.objects.filter(session=s).first()
    if existing:return existing
    gross=s.stage_progress.aggregate(v=Sum('gross_xp'))['v'] or 0
    penalty=s.hint_usages.aggregate(v=Sum('score_penalty'))['v'] or 0
    final=max(0,gross-penalty)
    result=EscapeSettlement.objects.create(session=s,gross_xp=gross,penalty_xp=penalty,final_xp=final,
        bonus_xp=10 if s.status=='COMPLETED' else 0,bonus_coins=0,reason=reason)
    s.score=final;s.settled_at=timezone.now();s.save(update_fields=['score','settled_at','updated_at'])
    return result

def _expire(s):
    if s.status=='PLAYING' and (s.expires_at is None or timezone.now()>=s.expires_at):
        s.status='FAILED';s.finished_at=timezone.now();s.save(update_fields=['status','finished_at','updated_at'])
        settle_session(s,reason='TIME_EXPIRED')
        return True
    return False

@transaction.atomic
def expire_session_if_needed(session):
    locked=UserEscapeSession.objects.select_for_update().get(pk=session.pk)
    result=_expire(locked);session.refresh_from_db();return result

def _advance(s,stage):
    now=timezone.now()
    next_stage=stage.room.stages.filter(order__gt=stage.order).order_by('order').first()
    if next_stage is None:
        s.room_progress.filter(room=stage.room).update(status='COMPLETED',completed_at=now,final_fragment_acquired=stage.room.final_fragment)
        next_room=s.escape_room.rooms.filter(order__gt=stage.room.order).order_by('order').first()
        if next_room:
            next_stage=next_room.stages.order_by('order').first()
            s.room_progress.filter(room=next_room).update(status='AVAILABLE',started_at=now)
    if next_stage:
        s.current_stage=next_stage;s.current_room=next_stage.room
        s.stage_progress.filter(stage=next_stage).update(status='AVAILABLE',started_at=now)
    else:
        s.status='COMPLETED';s.finished_at=now
    s.save()
    if s.status=='COMPLETED':settle_session(s,reason='COMPLETED')

@transaction.atomic
def register_attempt(*,session,puzzle,answer,is_correct=None):
    s=UserEscapeSession.objects.select_for_update().get(pk=session.pk)
    if _expire(s) or s.status!='PLAYING':
        session.refresh_from_db()
        return {'is_correct':False,'completed':False,'failed':True}
    if puzzle.stage_id!=s.current_stage_id:
        raise ValueError('La fase ha cambiado. Revisa la prueba actual.')
    correct=check_stage_answer(puzzle=puzzle,submitted_answer=answer)
    number=s.puzzle_attempts.filter(puzzle=puzzle).count()+1
    PuzzleAttempt.objects.create(session=s,puzzle=puzzle,player=s.user,attempt_no=number,answer={'value':answer},is_correct=correct)
    progress=s.stage_progress.get(stage=puzzle.stage)
    progress.attempts+=1;progress.status='IN_PROGRESS'
    if correct:
        progress.is_solved=True;progress.status='COMPLETED';progress.completed_at=timezone.now()
        progress.fragment_acquired=puzzle.stage.fragment;progress.gross_xp=puzzle.points;progress.net_xp=puzzle.points
        progress.time_spent_seconds=max(0,int((progress.completed_at-(progress.started_at or s.started_at)).total_seconds()))
        s.score+=puzzle.points
    progress.save()
    if correct:_advance(s,puzzle.stage)
    elif puzzle.max_attempts and number>=puzzle.max_attempts:
        s.status='FAILED';s.finished_at=timezone.now();s.save()
        progress.status='FAILED';progress.save(update_fields=['status'])
        settle_session(s,reason='FAILED')
    session.refresh_from_db()
    return {'is_correct':correct,'completed':session.status=='COMPLETED','failed':session.status=='FAILED'}

def get_available_hint(session,stage):
    hint=(Hint.objects.filter(puzzle__stage=stage).order_by('order').first() or Hint.objects.filter(room=stage.room).order_by('order').first())
    if hint is None or hint.coin_price or session.hint_usages.filter(hint=hint).exists():return None
    start=session.stage_progress.get(stage=stage).started_at or session.started_at
    if (timezone.now()-start).total_seconds()<hint.unlock_after_seconds:return None
    return hint

@transaction.atomic
def use_hint(session,hint):
    s=UserEscapeSession.objects.select_for_update().get(pk=session.pk)
    if _expire(s) or s.status!='PLAYING':
        session.refresh_from_db();return False
    candidate=get_available_hint(s,s.current_stage)
    if candidate is None or candidate.pk!=hint.pk:return False
    HintUsage.objects.create(session=s,hint=hint,player=s.user,score_penalty=hint.penalty_points,time_penalty=hint.penalty_seconds,coins_charged=0)
    s.expires_at-=timedelta(seconds=hint.penalty_seconds);s.save(update_fields=['expires_at','updated_at'])
    _expire(s);session.refresh_from_db();return True
