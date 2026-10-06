from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import EscapeSubmitForm
from .models import EscapeRoom, EscapeSession, Stage
from .services import (
    check_stage_answer,
    expire_session_if_needed,
    get_remaining_seconds,
    register_attempt,
    use_hint,
)


# ──────────────────────────────────────────────────────────────
# Catálogo
# ──────────────────────────────────────────────────────────────
@login_required
def room_list(request):
    rooms = EscapeRoom.objects.filter(is_published=True)
    return render(request, "escape_arenas/room_list.html", {"rooms": rooms})


@login_required
def room_detail(request, slug):
    room = get_object_or_404(EscapeRoom, slug=slug, is_published=True)
    return render(request, "escape_arenas/room_detail.html", {"room": room})


# ──────────────────────────────────────────────────────────────
# Inicio / reanudación de partida
# ──────────────────────────────────────────────────────────────
@login_required
def escape_start(request, slug):
    escape_room = get_object_or_404(EscapeRoom, slug=slug, is_published=True)

    if request.method != "POST":
        return redirect("escape_arenas:room_detail", slug=slug)

    # Si ya tiene una sesión IN_PROGRESS en esta sala, la reanuda
    existing = (
        EscapeSession.objects
        .filter(player=request.user, escape_room=escape_room,
                status=EscapeSession.Status.IN_PROGRESS)
        .first()
    )
    if existing:
        return redirect("escape_arenas:play", pk=existing.pk)

    first_room = escape_room.rooms.order_by("order").first()
    if first_room is None:
        messages.error(request, "Esta aventura todavía no tiene habitaciones.")
        return redirect("escape_arenas:room_detail", slug=slug)

    first_stage = first_room.stages.order_by("order").first()
    if first_stage is None:
        messages.error(request, "Esta habitación no tiene pruebas.")
        return redirect("escape_arenas:room_detail", slug=slug)

    session = EscapeSession.objects.create(
        escape_room=escape_room,
        player=request.user,
        current_room=first_room,
        current_stage=first_stage,
    )
    messages.success(request, "¡Aventura iniciada! Buena suerte.")
    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Pantalla de juego
# ──────────────────────────────────────────────────────────────
@login_required
def escape_play(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("escape_room"),
        pk=pk,
        player=request.user,
    )

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    if session.status != EscapeSession.Status.IN_PROGRESS:
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.current_stage
    if stage is None:
        messages.error(request, "No hay prueba actual.")
        return redirect("escape_arenas:result", pk=session.pk)

    form = EscapeSubmitForm()
    return render(request, "escape_arenas/play.html", {
        "session": session,
        "stage": stage,
        "form": form,
        "remaining_seconds": get_remaining_seconds(session),
    })


# ──────────────────────────────────────────────────────────────
# Enviar respuesta
# ──────────────────────────────────────────────────────────────
@login_required
def escape_submit(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("escape_room"),
        pk=pk,
        player=request.user,
    )

    if request.method != "POST" or session.status != EscapeSession.Status.IN_PROGRESS:
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
        return redirect("escape_arenas:result", pk=session.pk)

    answer = form.cleaned_data["answer"]
    is_correct = check_stage_answer(stage=stage, submitted_answer=answer)

    result = register_attempt(
        session=session,
        stage=stage,
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

    if session.status == EscapeSession.Status.FAILED:
        messages.error(request, "Demasiados errores. Aventura fallida.")
        return redirect("escape_arenas:result", pk=session.pk)

    return redirect("escape_arenas:play", pk=session.pk)


# ──────────────────────────────────────────────────────────────
# Pistas
# ──────────────────────────────────────────────────────────────
@login_required
def escape_hint(request, pk):
    session = get_object_or_404(
        EscapeSession.objects.select_related("escape_room"),
        pk=pk,
        player=request.user,
    )

    if request.method != "POST" or session.status != EscapeSession.Status.IN_PROGRESS:
        return redirect("escape_arenas:play", pk=session.pk)

    if expire_session_if_needed(session):
        messages.error(request, "Tiempo agotado.")
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.current_stage
    if stage is None:
        return redirect("escape_arenas:play", pk=session.pk)

    applied = use_hint(session, stage)
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
        EscapeSession.objects.select_related("escape_room"),
        pk=pk,
        player=request.user,
    )
    return render(request, "escape_arenas/result.html", {"session": session})


@login_required
def escape_history(request):
    sessions = (
        request.user.escape_sessions
        .select_related("escape_room")
        .order_by("-started_at")
    )
    return render(request, "escape_arenas/history.html", {"sessions": sessions})