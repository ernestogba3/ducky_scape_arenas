from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.utils import timezone

from .forms import EscapeSubmitForm
from .models import EscapeRoom, UserEscapeSession, Stage, Hint, EscapeSettlement
from .services import (
    check_stage_answer,
    expire_session_if_needed,
    get_available_hint,
    get_remaining_seconds,
    register_attempt,
    start_session,
    settle_session,
    use_hint,
)


# ──────────────────────────────────────────────────────────────
# Catálogo
# ──────────────────────────────────────────────────────────────
@login_required
def room_list(request):
    rooms = EscapeRoom.objects.filter(is_active=True)
    return render(request, "escape_arenas/room_list.html", {"rooms": rooms})


@login_required
def room_detail(request, slug):
    room = get_object_or_404(EscapeRoom, slug=slug, is_active=True)
    return render(request, "escape_arenas/room_detail.html", {"room": room})


# ──────────────────────────────────────────────────────────────
# Inicio / reanudación de partida
# ──────────────────────────────────────────────────────────────
@login_required
def escape_start(request, slug):
    escape_room = get_object_or_404(EscapeRoom, slug=slug, is_active=True)

    if request.method != "POST":
        return redirect("escape_arenas:room_detail", slug=slug)

    # Si ya tiene una sesión PLAYING en esta sala, la reanuda
    existing = (
        UserEscapeSession.objects
        .filter(
            user=request.user,
            escape_room=escape_room,
            status=UserEscapeSession.Status.PLAYING,
        )
        .first()
    )
    if existing:
        messages.info(request, "Reanudando tu partida en curso.")
        return redirect("escape_arenas:play", pk=existing.pk)

    try:
        session = start_session(user=request.user, escape_room=escape_room)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("escape_arenas:room_detail", slug=slug)

    messages.success(request, "¡Aventura iniciada! Buena suerte.")
    return redirect("escape_arenas:play", pk=session.pk)

# ──────────────────────────────────────────────────────────────
# Pantalla de juego
# ──────────────────────────────────────────────────────────────
@login_required
def escape_play(request, pk):
    session = get_object_or_404(
        UserEscapeSession.objects.select_related("escape_room"),
        pk=pk,
        user=request.user,
    )

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    if session.status != UserEscapeSession.Status.PLAYING:
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.current_stage
    if stage is None:
        messages.error(request, "No hay prueba actual.")
        return redirect("escape_arenas:result", pk=session.pk)
    hint = get_available_hint(session, stage)
    form = EscapeSubmitForm()
    return render(request, "escape_arenas/play.html", {
        "session": session,
        "stage": stage,
        "form": form,
        "remaining_seconds": get_remaining_seconds(session),
        "hint": hint,
    })


# ──────────────────────────────────────────────────────────────
# Enviar respuesta
# ──────────────────────────────────────────────────────────────
@login_required
def escape_submit(request, pk):
    session = get_object_or_404(
        UserEscapeSession.objects.select_related("escape_room"),
        pk=pk,
        user=request.user,
    )

    if request.method != "POST" or session.status != UserEscapeSession.Status.PLAYING:
        return redirect("escape_arenas:play", pk=session.pk)

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    form = EscapeSubmitForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Respuesta no válida.")
        return redirect("escape_arenas:play", pk=session.pk)

    stage = session.current_stage
    if stage is None:
        messages.error(request, "No hay prueba actual.")
        return redirect("escape_arenas:play", pk=session.pk)
    puzzle = stage.puzzles.order_by("order").first()
    if puzzle is None:
        messages.error(request, "Esta prueba no tiene puzzle.")
        return redirect("escape_arenas:play", pk=session.pk)

    answer = form.cleaned_data["answer"]
    is_correct = check_stage_answer(puzzle=puzzle, submitted_answer=answer)
    result = register_attempt(
        session=session,
        puzzle=puzzle,
        answer=answer,
        is_correct=is_correct,
    )

    if result["is_correct"]:
        messages.success(request, "¡Correcto! Has avanzado.")
    else:
        messages.error(request, "Respuesta incorrecta.")

    if result.get("completed"):
        messages.success(request, "¡Has escapado!")
        return redirect("escape_arenas:result", pk=session.pk)

    if session.status == UserEscapeSession.Status.FAILED:
        messages.error(request, "Demasiados errores. Aventura fallida.")
        return redirect("escape_arenas:result", pk=session.pk)

    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Pistas
# ──────────────────────────────────────────────────────────────
@login_required
def escape_hint(request, pk):
    session = get_object_or_404(
        UserEscapeSession.objects.select_related("escape_room"),
        pk=pk,
        user=request.user,
    )

    if request.method != "POST" or session.status != UserEscapeSession.Status.PLAYING:
        return redirect("escape_arenas:play", pk=session.pk)

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.current_stage
    if stage is None:
        return redirect("escape_arenas:play", pk=session.pk)

    hint = get_available_hint(session, stage)

    if hint is None:
        messages.warning(request, "No hay pistas disponibles para esta prueba.")
        return redirect("escape_arenas:play", pk=session.pk)
    
    applied = use_hint(session, hint)
    if applied:
        messages.info(request, "Pista utilizada: se ha aplicado la penalización.")
    else:
        messages.warning(request, "Ya has usado la pista de esta prueba.")

    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Resultado e historial
# ──────────────────────────────────────────────────────────────
@login_required
def escape_result(request, pk):
    session = get_object_or_404(
        UserEscapeSession.objects.select_related("escape_room"),
        pk=pk,
        user=request.user,
    )

    # Si la sesión está en estado terminal pero no tiene liquidación,
    # crearla ahora (idempotente: settle_session no duplica).
    liquidable = {
        UserEscapeSession.Status.COMPLETED,
        UserEscapeSession.Status.FAILED,
        UserEscapeSession.Status.ABANDONED,
    }
    if session.status in liquidable and not hasattr(session, "settlement"):
        reason_map = {
            UserEscapeSession.Status.COMPLETED: EscapeSettlement.Reason.COMPLETED,
            UserEscapeSession.Status.FAILED: EscapeSettlement.Reason.FAILED,
            UserEscapeSession.Status.ABANDONED: EscapeSettlement.Reason.ABANDONED,
        }
        settle_session(session, reason=reason_map[session.status])
        # Refrescar la sesión para que el acceso a .settlement funcione
        session.refresh_from_db()

    settlement = getattr(session, "settlement", None)

    total_time_seconds = 0
    if session.started_at and session.finished_at:
        total_time_seconds = int(
            (session.finished_at - session.started_at).total_seconds()
        )
    hints_used = session.hint_usages.count()
    return render(request, "escape_arenas/result.html", {
        "session": session,
        "settlement": settlement,
    })


@login_required
def escape_history(request):
    sessions = (
        request.user.escape_sessions
        .select_related("escape_room")
        .order_by("-started_at")
    )
    return render(request, "escape_arenas/history.html", {"sessions": sessions})
# TODO: reescribir en Fase 2 con UserEscapeSession, UserStageProgress,
# PuzzleAttempt y HintUsage.