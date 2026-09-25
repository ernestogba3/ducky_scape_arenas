from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from .models import EscapeRoom, EscapeSession, EscapeAttempt
from .forms import StageAnswerForm
from .services import check_stage_answer

# Create your views here.
@login_required
def start_escape(request, slug):
    room = get_object_or_404(EscapeRoom, slug=slug, is_published=True)
    if request.method == "POST":
        session = EscapeSession.objects.create(room=room, player=request.user)
        return redirect("escape_arenas:play", pk=session.pk)

