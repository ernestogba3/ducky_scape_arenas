from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import EscapeHintUse, EscapeRoom, EscapeSession, EscapeAttempt
from .forms import StageAnswerForm
from .services import check_stage_answer


# ──────────────────────────────────────────────────────────────
# Catálogo
# ──────────────────────────────────────────────────────────────
@login_required
def room_list(request):
    rooms = EscapeRoom.objects.filter(is_published=True)
    theme = request.GET.get("theme")
    query = request.GET.get("q")
    if theme:
        rooms = rooms.filter(theme=theme)
    if query:
        rooms = rooms.filter(title__icontains=query)
    return render(request, "escape_arenas/room_list.html", {"rooms": rooms})


@login_required
def room_detail(request, slug):
    room = get_object_or_404(EscapeRoom, slug=slug, is_published=True)
    return render(request, "escape_arenas/room_detail.html", {"room": room})


# ──────────────────────────────────────────────────────────────
# Inicio de partida
# ──────────────────────────────────────────────────────────────
@login_required
def start_escape(request, slug):
    room = get_object_or_404(EscapeRoom, slug=slug, is_published=True)
    if request.method != "POST":
        return redirect("escape_arenas:room_detail", slug=slug)

    session = EscapeSession.objects.create(room=room, player=request.user)
    messages.success(request, "¡Escape iniciado! Buena suerte.")
    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Pantalla de juego
# ──────────────────────────────────────────────────────────────
@login_required
def play_escape(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("room"),
        pk=pk,
        player=request.user,
    )

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    if session.status != EscapeSession.Status.ACTIVE:
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.room.stages.filter(order=session.current_order).first()
    if stage is None:
        session.status = EscapeSession.Status.COMPLETED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        return redirect("escape_arenas:result", pk=session.pk)

    form = StageAnswerForm()
    return render(request, "escape_arenas/play.html", {
        "session": session,
        "stage": stage,
        "form": form,
    })


# ──────────────────────────────────────────────────────────────
# Enviar respuesta
# ──────────────────────────────────────────────────────────────
@login_required
def submit_answer(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("room"),
        pk=pk,
        player=request.user,
    )

    if request.method != "POST" or session.status != EscapeSession.Status.ACTIVE:
        return redirect("escape_arenas:play", pk=session.pk)

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    form = StageAnswerForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Respuesta no válida.")
        return redirect("escape_arenas:play", pk=session.pk)

    stage = session.room.stages.filter(order=session.current_order).first()
    if stage is None:
        session.status = EscapeSession.Status.COMPLETED
        session.finished_at = timezone.now()
        session.save(update_fields=["status", "finished_at"])
        return redirect("escape_arenas:result", pk=session.pk)

    answer = form.cleaned_data["answer"]
    is_correct = check_stage_answer(stage=stage, submitted_answer=answer)

    with transaction.atomic():
        EscapeAttempt.objects.create(
            session=session,
            stage=stage,
            submitted_answer=answer,
            is_correct=is_correct,
        )
        if is_correct:
            session.score += stage.points
            session.current_order += 1
            session.save(update_fields=["score", "current_order"])
        else:
            session.wrong_attempts += 1
            session.save(update_fields=["wrong_attempts"])

    if is_correct:
        messages.success(request, "Respuesta correcta: cerradura desbloqueada.")
        if not session.room.stages.filter(order=session.current_order).exists():
            session.status = EscapeSession.Status.COMPLETED
            session.finished_at = timezone.now()
            session.save(update_fields=["status", "finished_at"])
            return redirect("escape_arenas:result", pk=session.pk)
    else:
        messages.error(request, "Respuesta incorrecta: revisa la pista del enunciado.")

    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Pistas
# ──────────────────────────────────────────────────────────────
@login_required
def use_hint(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("room"),
        pk=pk,
        player=request.user,
    )

    if request.method != "POST" or session.status != EscapeSession.Status.ACTIVE:
        return redirect("escape_arenas:play", pk=session.pk)

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.room.stages.filter(order=session.current_order).first()
    if stage is None or not stage.hint_text:
        return redirect("escape_arenas:play", pk=session.pk)

    _, created = EscapeHintUse.objects.get_or_create(
        session=session,
        stage=stage,
        defaults={"penalty": stage.hint_penalty},
    )

    if created:
        session.score = max(0, session.score - stage.hint_penalty)
        session.hints_used += 1
        session.save(update_fields=["score", "hints_used"])
        messages.info(request, "Pista utilizada: se ha aplicado la penalización.")

    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Resultado e historial
# ──────────────────────────────────────────────────────────────
@login_required
def escape_result(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("room"),
        pk=pk,
        player=request.user,
    )
    return render(request, "escape_arenas/result.html", {"session": session})


@login_required
def history(request):
    sessions = (
        request.user.escape_sessions
        .select_related("room")
        .order_by("-started_at")
    )
    return render(request, "escape_arenas/history.html", {"sessions": sessions})