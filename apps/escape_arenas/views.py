from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import EscapeHintUse, EscapeRoom, EscapeSession, EscapeAttempt
from .forms import StageAnswerForm
from .services import check_stage_answer

# Create your views here.
@login_required
def start_escape(request, slug):
    room = get_object_or_404(EscapeRoom, slug=slug, is_published=True)
    if request.method == "POST":
        session = EscapeSession.objects.create(room=room, player=request.user)
        return redirect("escape_arenas:play", pk=session.pk)

@login_required
def submit_answer(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("room"),
        pk=pk,
        player=request.user,
    )

    if request.method != "POST" or session.status != EscapeSession.Status.ACTIVE:
        return redirect("escape_arenas:play", pk=session.pk)

    # Tiempo agotado
    deadline = session.started_at + timedelta(minutes=session.room.time_limit_minutes)
    if timezone.now() >= deadline:
        session.status = EscapeSession.Status.FAILED
        session.finished_at = timezone.now()
        session.save()
        return redirect("escape_arenas:result", pk=session.pk)

    form = StageAnswerForm(request.POST)
    if not form.is_valid():
        return redirect("escape_arenas:play", pk=session.pk)

    # Fase actual (nunca desde el cliente)
    stage = session.room.stages.filter(order=session.current_order).first()
    if stage is None:
        session.status = EscapeSession.Status.COMPLETED
        session.finished_at = timezone.now()
        session.save()
        return redirect("escape_arenas:result", pk=session.pk)

    is_correct = check_stage_answer(stage=stage, submitted_answer=form.cleaned_data["answer"])

    with transaction.atomic():
        EscapeAttempt.objects.create(
            session=session, stage=stage,
            submitted_answer=form.cleaned_data["answer"],
            is_correct=is_correct,
        )
        if is_correct:
            session.score += stage.points
            session.current_order += 1
        else:
            session.wrong_attempts += 1
        session.save()

    # ¿Queda siguiente fase?
    if is_correct and not session.room.stages.filter(order=session.current_order).exists():
        session.status = EscapeSession.Status.COMPLETED
        session.finished_at = timezone.now()
        session.save()
        return redirect("escape_arenas:result", pk=session.pk)

    return redirect("escape_arenas:play", pk=session.pk)

@login_required
def use_hint(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("room"),
        pk=pk,
        player=request.user,
    )

    if request.method != "POST" or session.status != EscapeSession.Status.ACTIVE:
        return redirect("escape_arenas:play", pk=session.pk)

    stage = session.room.stages.filter(order=session.current_order).first()
    if stage is None or not stage.hint_text:
        return redirect("escape_arenas:play", pk=session.pk)

    # Una sola vez por fase
    hint_use, created = EscapeHintUse.objects.get_or_create(
        session=session,
        stage=stage,
        defaults={"penalty": stage.hint_penalty},
    )

    if created:
        session.score = max(0, session.score - stage.hint_penalty)
        session.hints_used += 1
        session.save()

    return redirect("escape_arenas:play", pk=session.pk)