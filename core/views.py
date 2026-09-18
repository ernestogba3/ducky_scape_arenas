from django.shortcuts import render
from django.conf import settings
from accounts import models

player = models.ForeignKey(
settings.AUTH_USER_MODEL,
on_delete=models.CASCADE,
related_name="escape_sessions",
)

def home(request):
    return render(request, 'core/home.html')


def dashboard(request):
    return render(request, 'core/dashboard.html')

