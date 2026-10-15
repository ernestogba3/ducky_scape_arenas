"""Vistas y contexto de la interfaz. No enviar soluciones a HTML o JavaScript."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import EscapeSubmitForm
from .models import EscapeRoom, UserEscapeSession
from .services import start_session,expire_session_if_needed,get_remaining_seconds,register_attempt,get_available_hint,use_hint

def owned(request,pk):
    return get_object_or_404(UserEscapeSession.objects.select_related('escape_room','current_room','current_stage'),pk=pk,user=request.user)

@login_required
def room_list(request):
    rooms=EscapeRoom.objects.filter(is_active=True).annotate(stage_count=Count('rooms__stages',distinct=True))
    q=request.GET.get('q','').strip();difficulty=request.GET.get('difficulty','')
    if q:rooms=rooms.filter(Q(name__icontains=q)|Q(description__icontains=q))
    if difficulty:rooms=rooms.filter(difficulty=difficulty)
    return render(request,'escape_arenas/room_list.html',{'rooms':rooms,'q':q,'difficulty':difficulty,'difficulties':EscapeRoom.Difficulty.choices})

@login_required
def room_detail(request,slug):
    room=get_object_or_404(EscapeRoom,slug=slug,is_active=True)
    stats=room.rooms.aggregate(stage_count=Count('stages',distinct=True),points=Sum('stages__puzzles__points'))
    active=request.user.escape_sessions.filter(escape_room=room,status='PLAYING').first()
    return render(request,'escape_arenas/room_detail.html',{'room':room,'stats':stats,'active':active})

@login_required
@require_POST
def escape_start(request,slug):
    room=get_object_or_404(EscapeRoom,slug=slug,is_active=True)
    active=request.user.escape_sessions.filter(escape_room=room,status='PLAYING').first()
    if active:
        expire_session_if_needed(active)
        if active.status=='PLAYING':
            messages.info(request,'Reanudando tu partida en curso.')
            return redirect('escape_arenas:play',pk=active.pk)
    try:s=start_session(user=request.user,escape_room=room)
    except ValueError as exc:
        messages.error(request,str(exc));return redirect('escape_arenas:room_detail',slug=slug)
    messages.success(request,'¡Aventura iniciada! Resuelve las fases en orden.')
    return redirect('escape_arenas:play',pk=s.pk)

@login_required
def escape_play(request,pk):
    s=owned(request,pk);expire_session_if_needed(s)
    if s.status!='PLAYING':return redirect('escape_arenas:result',pk=pk)
    stage=s.current_stage;puzzle=stage.puzzles.order_by('order').first()
    total=s.stage_progress.count();completed=s.stage_progress.filter(is_solved=True).count()
    used=s.hint_usages.filter(Q(hint__puzzle__stage=stage)|Q(hint__room=stage.room)).select_related('hint')
    return render(request,'escape_arenas/play.html',{'session':s,'stage':stage,'puzzle':puzzle,
        'options':puzzle.config.get('options',[]) if puzzle.type=='MULTIPLE_CHOICE' else [],
        'form':EscapeSubmitForm(),'remaining_seconds':get_remaining_seconds(s),
        'hint':get_available_hint(s,stage),'used_hints':used,'total':total,'completed':completed,
        'percentage':round(100*completed/total) if total else 0,'phase_number':completed+1})

@login_required
@require_POST
def escape_submit(request,pk):
    s=owned(request,pk);expire_session_if_needed(s)
    if s.status!='PLAYING':return redirect('escape_arenas:result',pk=pk)
    puzzle=s.current_stage.puzzles.order_by('order').first()
    if str(puzzle.pk)!=request.POST.get('puzzle_id'):
        messages.warning(request,'La fase ha cambiado. Revisa la prueba actual.')
        return redirect('escape_arenas:play',pk=pk)
    form=EscapeSubmitForm(request.POST)
    if not form.is_valid():
        messages.error(request,'Escribe una respuesta de entre 1 y 2000 caracteres.')
        return redirect('escape_arenas:play',pk=pk)
    try:result=register_attempt(session=s,puzzle=puzzle,answer=form.cleaned_data['answer'])
    except ValueError as exc:
        messages.warning(request,str(exc));return redirect('escape_arenas:play',pk=pk)
    if result['is_correct']:messages.success(request,'¡Correcto! Fase superada.')
    else:messages.error(request,'Respuesta incorrecta. Revisa el enunciado y vuelve a intentarlo.')
    return redirect('escape_arenas:play' if s.status=='PLAYING' else 'escape_arenas:result',pk=pk)

@login_required
@require_POST
def escape_hint(request,pk):
    s=owned(request,pk);expire_session_if_needed(s)
    if s.status!='PLAYING':return redirect('escape_arenas:result',pk=pk)
    hint=get_available_hint(s,s.current_stage)
    if hint and str(hint.pk)==request.POST.get('hint_id') and use_hint(s,hint):
        messages.info(request,'Pista desbloqueada. Penalización registrada una sola vez.')
    else:messages.warning(request,'Esta pista no está disponible o ya está desbloqueada.')
    return redirect('escape_arenas:play',pk=pk)

@login_required
def escape_result(request,pk):
    s=owned(request,pk);expire_session_if_needed(s)
    if s.status=='PLAYING':return redirect('escape_arenas:play',pk=pk)
    return render(request,'escape_arenas/result.html',{'session':s,'settlement':getattr(s,'settlement',None),
        'attempts':s.puzzle_attempts.count(),'completed':s.stage_progress.filter(is_solved=True).count(),'total':s.stage_progress.count()})

@login_required
def escape_history(request):
    return render(request,'escape_arenas/history.html',{'sessions':request.user.escape_sessions.select_related('escape_room','settlement')})

@login_required
def ranking(request,slug):
    room=get_object_or_404(EscapeRoom,slug=slug,is_active=True)
    sessions=room.sessions.filter(status='COMPLETED').select_related('user').order_by('-score','finished_at')[:50]
    return render(request,'escape_arenas/ranking.html',{'room':room,'sessions':sessions})
