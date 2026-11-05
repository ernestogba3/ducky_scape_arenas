"""Vistas y contexto de la interfaz. No enviar soluciones a HTML o JavaScript."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import EscapeSubmitForm
from .forms import EscapeRoomForm, RoomForm, StageForm, PuzzleForm, HintForm
from .models import (
    EscapeRoom, Room, Stage, Puzzle, Hint,
    UserEscapeSession, EscapeSettlement,
)
from django.http import JsonResponse

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
def owned(request, pk):
    """Devuelve la UserEscapeSession `pk` si es del usuario; 404 si no."""
    return get_object_or_404(
        UserEscapeSession.objects.select_related("escape_room"),
        pk=pk,
        user=request.user,
    )

CHILD_REGISTRY = {
    "room": {
        "model": Room,
        "form": RoomForm,
        "parent_field": "escape_room",
        "parent_model": EscapeRoom,
        "label": "Sala",
    },
    "stage": {
        "model": Stage,
        "form": StageForm,
        "parent_field": "room",
        "parent_model": Room,
        "label": "Etapa",
    },
    "puzzle": {
        "model": Puzzle,
        "form": PuzzleForm,
        "parent_field": "stage",
        "parent_model": Stage,
        "label": "Puzzle",
    },
    "hint": {
        "model": Hint,
        "form": HintForm,
        "parent_field": "puzzle",  # o "room", pero para MVP usamos puzzle
        "parent_model": Puzzle,
        "label": "Pista",
    },
}

# ──────────────────────────────────────────────────────────────
# Catálogo
# ──────────────────────────────────────────────────────────────
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
def escape_play(request, pk):
    session = owned(request, pk)
    expire_session_if_needed(session)

    if session.status != "PLAYING":
        return redirect("escape_arenas:result", pk=pk)

    stage = session.current_stage
    puzzle = stage.puzzles.order_by("order").first()
    total = session.stage_progress.count()
    completed = session.stage_progress.filter(is_solved=True).count()
    used = (
        session.hint_usages
        .filter(Q(hint__puzzle__stage=stage) | Q(hint__room=stage.room))
        .select_related("hint")
    )

    current_progress = session.stage_progress.get(stage=stage)
    attempts_used = current_progress.attempts
    attempts_remaining = (puzzle.max_attempts - attempts_used) if puzzle.max_attempts else None

    return render(request, "escape_arenas/play.html", {
        "session": session,
        "stage": stage,
        "puzzle": puzzle,
        "options": puzzle.config.get("options", []) if puzzle.type == "MULTIPLE_CHOICE" else [],
        "form": EscapeSubmitForm(),
        "remaining_seconds": get_remaining_seconds(session),
        "hint": get_available_hint(session, stage),
        "used_hints": used,
        "total": total,
        "completed": completed,
        "percentage": round(100 * completed / total) if total else 0,
        "phase_number": completed + 1,
        "attempts_used": attempts_used,
        "attempts_remaining": attempts_remaining,
    })

@login_required
@require_POST
def escape_submit(request, pk):
    session = owned(request, pk)
    expire_session_if_needed(session)

    if session.status != UserEscapeSession.Status.PLAYING:
        return redirect("escape_arenas:result", pk=session.pk)

    stage = session.current_stage
    if stage is None:
        messages.error(request, "No hay prueba actual.")
        return redirect("escape_arenas:play", pk=session.pk)

    puzzle = stage.puzzles.order_by("order").first()
    if puzzle is None:
        messages.error(request, "Esta prueba no tiene puzzle.")
        return redirect("escape_arenas:play", pk=session.pk)

    # El cliente envía el puzzle_id que creía estar resolviendo;
    # si entre tanto la fase avanzó, no procesamos la respuesta.
    if str(puzzle.pk) != request.POST.get("puzzle_id"):
        messages.warning(request, "La fase ha cambiado. Revisa la prueba actual.")
        return redirect("escape_arenas:play", pk=session.pk)

    form = EscapeSubmitForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Respuesta no válida.")
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
        session.refresh_from_db()

    settlement = getattr(session, "settlement", None)

    # ── Estadísticas de la partida ──────────────────────────────
    total_attempts = session.puzzle_attempts.count()
    total_fails = session.puzzle_attempts.filter(is_correct=False).count()
    hints_used = session.hint_usages.count()

    total_stages = session.stage_progress.count()
    completed_stages = session.stage_progress.filter(is_solved=True).count()

    total_time_seconds = 0
    if session.started_at and session.finished_at:
        total_time_seconds = int(
            (session.finished_at - session.started_at).total_seconds()
        )

    # ── Desglose de bonus (recalculado solo para visualizarlo) ──
    bonus_base = 0
    bonus_speed = 0
    bonus_clean = 0

    if session.status == UserEscapeSession.Status.COMPLETED:
        bonus_base = 10

        total_limit = session.rules_snapshot.get('time_limit_seconds', 0)
        if (total_limit and session.expires_at and session.finished_at
                and session.expires_at > session.finished_at):
            time_left = (session.expires_at - session.finished_at).total_seconds()
            speed_ratio = min(1.0, time_left / total_limit)
            bonus_speed = int(speed_ratio * 50)

        if total_fails == 0:
            bonus_clean = 25

    return render(request, "escape_arenas/result.html", {
        "session": session,
        "settlement": settlement,
        "total": total_stages,
        "completed": completed_stages,
        "attempts": total_attempts,
        "total_fails": total_fails,
        "hints_used": hints_used,
        "total_time_seconds": total_time_seconds,
        "bonus_base": bonus_base,
        "bonus_speed": bonus_speed,
        "bonus_clean": bonus_clean,
    })


@login_required
def escape_history(request):
    sessions = (
        request.user.escape_sessions
        .select_related("escape_room")
        .order_by("-started_at")
    )
    return render(request, "escape_arenas/history.html", {"sessions": sessions})

# ──────────────────────────────────────────────────────────────
# CRUD del profesor (EscapeRoom)
# ──────────────────────────────────────────────────────────────
@login_required
def my_escape_rooms(request):
    """Lista solo las aventuras creadas por el usuario actual."""
    rooms = (
        EscapeRoom.objects
        .filter(creator=request.user)
        .order_by("-created_at")
    )
    return render(request, "escape_arenas/my_rooms.html", {"rooms": rooms})


@login_required
def escape_room_create(request):
    """Crea una nueva EscapeRoom. El autor es el usuario actual."""
    if request.method == "POST":
        form = EscapeRoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.creator = request.user  # asignar autor
            room.save()
            messages.success(request, "Aventura creada correctamente.")
            return redirect("escape_arenas:room_detail", slug=room.slug)
    else:
        form = EscapeRoomForm()

    return render(request, "escape_arenas/escape_room_form.html", {
        "form": form,
        "action": "create",
    })


@login_required
def escape_room_update(request, slug):
    """Edita una EscapeRoom. Solo el autor puede hacerlo."""
    room = get_object_or_404(EscapeRoom, slug=slug)

    # Permiso: solo el autor
    if room.creator != request.user:
        messages.error(request, "No tienes permiso para editar esta aventura.")
        return redirect("escape_arenas:room_detail", slug=room.slug)

    if request.method == "POST":
        form = EscapeRoomForm(request.POST, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, "Aventura actualizada correctamente.")
            return redirect("escape_arenas:room_detail", slug=room.slug)
    else:
        form = EscapeRoomForm(instance=room)

    return render(request, "escape_arenas/escape_room_form.html", {
        "form": form,
        "action": "update",
        "room": room,
    })


@login_required
def escape_room_delete(request, slug):
    """Borra una EscapeRoom. Solo el autor puede hacerlo."""
    room = get_object_or_404(EscapeRoom, slug=slug)

    # Permiso: solo el autor
    if room.creator != request.user:
        messages.error(request, "No tienes permiso para borrar esta aventura.")
        return redirect("escape_arenas:room_detail", slug=room.slug)

    if request.method == "POST":
        room.delete()
        messages.success(request, "Aventura borrada correctamente.")
        return redirect("escape_arenas:my_rooms")

    return render(request, "escape_arenas/escape_room_confirm_delete.html", {
        "room": room,
    })

def _user_owns_escape_room(user, escape_room):
    """Devuelve True si el usuario es el creador de la EscapeRoom."""
    return escape_room.creator == user


def _get_escape_room_of_child(child_type, child):
    """Dado un hijo (Room, Stage, Puzzle, Hint), devuelve su EscapeRoom raíz."""
    if child_type == "room":
        return child.escape_room
    if child_type == "stage":
        return child.room.escape_room
    if child_type == "puzzle":
        return child.stage.room.escape_room
    if child_type == "hint":
        if child.puzzle:
            return child.puzzle.stage.room.escape_room
        return child.room.escape_room
    raise ValueError(f"Tipo de hijo desconocido: {child_type}")

# ──────────────────────────────────────────────────────────────
# CRUD anidado genérico para hijos de EscapeRoom
# ──────────────────────────────────────────────────────────────
@login_required
def child_create(request, child_type, parent_pk):
    """Crea un hijo (Room, Stage, Puzzle, Hint) dentro de un padre."""
    if child_type not in CHILD_REGISTRY:
        messages.error(request, "Tipo de elemento desconocido.")
        return redirect("escape_arenas:room_list")

    config = CHILD_REGISTRY[child_type]
    parent_model = config["parent_model"]
    parent_field = config["parent_field"]
    form_class = config["form"]
    model = config["model"]
    label = config["label"]

    # Obtener el padre
    parent = get_object_or_404(parent_model, pk=parent_pk)

    # Comprobar permisos: el usuario debe ser el autor de la EscapeRoom raíz
    if child_type == "room":
        escape_room = parent  # el padre es la EscapeRoom
    else:
        escape_room = _get_escape_room_of_child(
            # para el padre, subimos un nivel
            child_type, parent
        ) if child_type in ("puzzle", "hint") else parent.escape_room

    if not _user_owns_escape_room(request.user, escape_room):
        messages.error(request, "No tienes permiso para añadir elementos aquí.")
        return redirect("escape_arenas:room_detail", slug=escape_room.slug)

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            child = form.save(commit=False)
            # Asignar el padre automáticamente
            setattr(child, parent_field, parent)
            child.save()
            messages.success(request, f"{label} creada correctamente.")
            return redirect("escape_arenas:room_detail", slug=escape_room.slug)
    else:
        form = form_class()

    return render(request, "escape_arenas/child_form.html", {
        "form": form,
        "action": "create",
        "label": label,
        "escape_room": escape_room,
    })


@login_required
def child_update(request, child_type, pk):
    """Edita un hijo (Room, Stage, Puzzle, Hint)."""
    if child_type not in CHILD_REGISTRY:
        messages.error(request, "Tipo de elemento desconocido.")
        return redirect("escape_arenas:room_list")

    config = CHILD_REGISTRY[child_type]
    model = config["model"]
    form_class = config["form"]
    label = config["label"]

    child = get_object_or_404(model, pk=pk)

    # Comprobar permisos
    escape_room = _get_escape_room_of_child(child_type, child)
    if not _user_owns_escape_room(request.user, escape_room):
        messages.error(request, "No tienes permiso para editar este elemento.")
        return redirect("escape_arenas:room_detail", slug=escape_room.slug)

    if request.method == "POST":
        form = form_class(request.POST, instance=child)
        if form.is_valid():
            form.save()
            messages.success(request, f"{label} actualizada correctamente.")
            return redirect("escape_arenas:room_detail", slug=escape_room.slug)
    else:
        form = form_class(instance=child)

    return render(request, "escape_arenas/child_form.html", {
        "form": form,
        "action": "update",
        "label": label,
        "escape_room": escape_room,
    })


@login_required
def child_delete(request, child_type, pk):
    """Borra un hijo (Room, Stage, Puzzle, Hint)."""
    if child_type not in CHILD_REGISTRY:
        messages.error(request, "Tipo de elemento desconocido.")
        return redirect("escape_arenas:room_list")

    config = CHILD_REGISTRY[child_type]
    model = config["model"]
    label = config["label"]

    child = get_object_or_404(model, pk=pk)

    # Comprobar permisos
    escape_room = _get_escape_room_of_child(child_type, child)
    if not _user_owns_escape_room(request.user, escape_room):
        messages.error(request, "No tienes permiso para borrar este elemento.")
        return redirect("escape_arenas:room_detail", slug=escape_room.slug)

    if request.method == "POST":
        child.delete()
        messages.success(request, f"{label} borrada correctamente.")
        return redirect("escape_arenas:room_detail", slug=escape_room.slug)

    return render(request, "escape_arenas/child_confirm_delete.html", {
        "child": child,
        "label": label,
        "escape_room": escape_room,
    })


@login_required
def game_view(request):
    """Spike inicial de Phaser — carga el canvas vacío con BootScene + HubScene."""
    return render(request, "escape_arenas/game.html")

@login_required
def hub_data_view(request):
    """Devuelve los escape rooms activos agrupados por tema para la HubScene de Phaser."""
    # Partimos de las tres temáticas conocidas aunque no tengan rooms todavía,
    # para que el hub pinte siempre los tres portales (los vacíos saldrán apagados).
    rooms_by_theme = {
        key: {"key": key, "label": label, "rooms": []}
        for key, label in EscapeRoom.Theme.choices
    }

    qs = (
        EscapeRoom.objects
        .filter(is_active=True)
        .order_by("theme", "era", "name")
    )
    for er in qs:
        rooms_by_theme[er.theme]["rooms"].append({
            "id": er.id,
            "slug": er.slug,
            "name": er.name,
            "description": er.description,
            "era": er.era,
            "era_display": er.get_era_display(),
            "difficulty": er.difficulty,
            "difficulty_display": er.get_difficulty_display(),
            "estimated_duration": er.estimated_duration,
        })

    return JsonResponse({
        "themes": list(rooms_by_theme.values()),
    })

import json
from django.views.decorators.http import require_POST


@login_required
@require_POST
def api_session_start(request):
    """Arranca (o reanuda) una partida en el escape room indicado."""
    try:
        data = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    escape_room_id = data.get("escape_room_id")
    if not escape_room_id:
        return JsonResponse({"ok": False, "error": "escape_room_id requerido"}, status=400)

    room = get_object_or_404(EscapeRoom, pk=escape_room_id, is_active=True)

    # Reanudar si ya hay una sesión activa en este escape room
    active = request.user.escape_sessions.filter(
        escape_room=room, status=UserEscapeSession.Status.PLAYING
    ).first()
    if active:
        expire_session_if_needed(active)
        if active.status == UserEscapeSession.Status.PLAYING:
            return JsonResponse({
                "ok": True, "session_id": str(active.pk), "resumed": True
            })

    try:
        session = start_session(user=request.user, escape_room=room)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({
        "ok": True, "session_id": str(session.pk), "resumed": False
    })


@login_required
def api_session_state(request, pk):
    """Devuelve el estado completo que RoomScene necesita para pintarse."""
    session = owned(request, pk)
    expire_session_if_needed(session)

    er = session.escape_room

    # Si la partida ya terminó, devolvemos solo la info de cierre
    if session.status != UserEscapeSession.Status.PLAYING:
        settlement = getattr(session, "settlement", None)
        return JsonResponse({
            "ok": True,
            "finished": True,
            "session": {
                "id": str(session.pk),
                "status": session.status,
                "score": session.score,
                "escape_room": {
                    "id": er.id, "name": er.name, "slug": er.slug,
                    "theme": er.theme, "era": er.era,
                    "era_display": er.get_era_display(),
                },
            },
            "settlement": None if settlement is None else {
                "final_xp": settlement.final_xp,
                "gross_xp": settlement.gross_xp,
                "penalty_xp": settlement.penalty_xp,
                "bonus_xp": settlement.bonus_xp,
                "reason": settlement.reason,
            },
            "stats": {
                "attempts": session.puzzle_attempts.count(),
                "fails": session.puzzle_attempts.filter(is_correct=False).count(),
                "hints_used": session.hint_usages.count(),
            },
        })

    # Partida en curso
    stage = session.current_stage
    room = session.current_room
    puzzle = stage.puzzles.order_by("order").first()
    progress = session.stage_progress.get(stage=stage)
    hint = get_available_hint(session, stage)

    total = session.stage_progress.count()
    completed = session.stage_progress.filter(is_solved=True).count()

    return JsonResponse({
        "ok": True,
        "finished": False,
        "session": {
            "id": str(session.pk),
            "status": session.status,
            "remaining_seconds": get_remaining_seconds(session),
            "score": session.score,
            "escape_room": {
                "id": er.id, "name": er.name, "slug": er.slug,
                "theme": er.theme, "era": er.era,
                "era_display": er.get_era_display(),
            },
        },
        "room": {
            "id": room.id, "name": room.name,
            "description": room.description, "order": room.order,
        },
        "stage": {
            "id": stage.id, "name": stage.name,
            "description": stage.description, "order": stage.order,
            "type": stage.type,
        },
        "puzzle": {
            "id": puzzle.id, "title": puzzle.title,
            "description": puzzle.description, "type": puzzle.type,
            "options": puzzle.config.get("options", []) if puzzle.type == "MULTIPLE_CHOICE" else [],
            "max_attempts": puzzle.max_attempts,
            "attempts_used": progress.attempts,
            "attempts_remaining": (puzzle.max_attempts - progress.attempts) if puzzle.max_attempts else None,
        },
        "hint": None if hint is None else {
            "id": hint.id, "order": hint.order,
            "penalty_seconds": hint.penalty_seconds,
            "penalty_points": hint.penalty_points,
        },
        "progress": {
            "total_stages": total, "completed_stages": completed,
            "percentage": round(100 * completed / total) if total else 0,
        },
    })


@login_required
@require_POST
def api_session_submit(request, pk):
    """Envía la respuesta al puzzle actual de la sesión."""
    session = owned(request, pk)
    expire_session_if_needed(session)

    if session.status != UserEscapeSession.Status.PLAYING:
        return JsonResponse({
            "ok": False, "error": "La partida ya no está activa",
            "status": session.status,
        }, status=400)

    try:
        data = json.loads(request.body or b"{}")
    except Exception:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    puzzle_id = data.get("puzzle_id")
    answer = data.get("answer", "")

    stage = session.current_stage
    puzzle = stage.puzzles.order_by("order").first()
    if puzzle is None or str(puzzle.pk) != str(puzzle_id):
        return JsonResponse({
            "ok": False, "error": "La fase ha cambiado. Recarga la escena.",
        }, status=409)

    result = register_attempt(session=session, puzzle=puzzle, answer=answer)
    session.refresh_from_db()

    return JsonResponse({
        "ok": True,
        "is_correct": result["is_correct"],
        "completed": result["completed"],
        "failed": result["failed"],
        "session_status": session.status,
    })


@login_required
@require_POST
def api_session_hint(request, pk):
    """Usa la siguiente pista disponible en la fase actual."""
    session = owned(request, pk)
    expire_session_if_needed(session)

    if session.status != UserEscapeSession.Status.PLAYING:
        return JsonResponse({"ok": False, "error": "Partida no activa"}, status=400)

    stage = session.current_stage
    hint = get_available_hint(session, stage)
    if hint is None:
        return JsonResponse({"ok": False, "error": "No hay pistas disponibles"}, status=404)

    applied = use_hint(session, hint)
    if not applied:
        return JsonResponse({"ok": False, "error": "La pista no puede usarse"}, status=400)

    return JsonResponse({
        "ok": True,
        "hint": {
            "id": hint.id, "order": hint.order, "text": hint.text,
            "penalty_seconds": hint.penalty_seconds,
            "penalty_points": hint.penalty_points,
        },
    })