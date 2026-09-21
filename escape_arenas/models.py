from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


# Create your models here.
class EscapeRoom(models.Model):
    class Difficulty(models.TextChoices):
     EASY = "EASY", "Fácil"
     MEDIUM = "MEDIUM", "Media"
     HARD = "HARD", "Difícil"

    class Theme(models.TextChoices):
        FULL_STACK = "FULL_STACK", "Full Stack"
        PYTHON = "PYTHON", "Python"
        DJANGO = "DJANGO", "Django"
        JAVASCRIPT = "JAVASCRIPT", "JavaScript"
        REACT = "REACT", "ReactJS"
        SQL = "SQL", "SQL"
        POSTGRES = "POSTGRES", "PostgreSQL"
        GIT = "GIT", "Git / GitHub"
        SCRUM = "SCRUM", "Scrum"
        REGEX = "REGEX", "Regex"

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    story = models.TextField(blank=True)
    theme = models.CharField(max_length=30, choices=Theme.choices)
    time_limit_minutes = models.PositiveIntegerField(default=30)
    reward_xp = models.PositiveIntegerField(default=0)
    reward_coins = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    difficulty = models.CharField(max_length=20, choices=Difficulty.choices, default=Difficulty.EASY)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_escape_rooms")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class EscapeStage(models.Model):

    class AnswerType(models.TextChoices):
        EXACT = "EXACT", "Respuesta exacta"
        CASE_INSENSITIVE = "CASE_INSENSITIVE", "Texto sin distinguir mayúsculas"
        MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Opción"
        NORMALIZED_CODE = "NORMALIZED_CODE", "Código normalizado"
        REGEX_PATTERN = "REGEX_PATTERN", "Patrón Regex"
    class Meta:
     ordering = ["order"]  # noqa: RUF012
     constraints = [models.UniqueConstraint(fields=["room", "order"], name="unique_stage_order_per_room")]  # noqa: RUF012
    class Category(models.TextChoices):
        PYTHON = "PYTHON", "Python"
        DJANGO = "DJANGO", "Django"
        JAVASCRIPT = "JAVASCRIPT", "JavaScript"
        REACT = "REACT", "ReactJS"
        SQL = "SQL", "SQL"
        POSTGRES = "POSTGRES", "PostgreSQL"
        GIT = "GIT", "Git / GitHub"
        SCRUM = "SCRUM", "Scrum"
        REGEX = "REGEX", "Regex"
        WEB = "WEB", "HTML / CSS"

    room = models.ForeignKey(EscapeRoom, on_delete=models.CASCADE, related_name="stages")
    order = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    narrative = models.TextField(blank=True)
    statement = models.TextField()
    category = models.CharField(max_length=30, choices=Category.choices)
    answer_type = models.CharField(max_length=30, choices=AnswerType.choices)
    expected_answer = models.TextField()
    points = models.PositiveIntegerField(default=100)
    hint_text = models.TextField(blank=True)
    hint_penalty = models.PositiveIntegerField(default=25)
    max_attempts = models.PositiveIntegerField(default=0)

class EscapeSession(models.Model):

    @property
    def deadline(self):
        return self.started_at + timedelta(minutes=self.room.time_limit_minutes)

    @property
    def remaining_seconds(self):
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    @property
    def is_expired(self):
        return timezone.now() >= self.deadline

    def get_current_stage(self):
        return self.room.stages.filter(order=self.current_order).first()
    class Status(models.TextChoices): 
        ACTIVE = "ACTIVE", "En curso"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Tiempo agotado"
        ABANDONED = "ABANDONED", "Abandonada"

    room = models.ForeignKey(EscapeRoom, on_delete=models.PROTECT, related_name="sessions")
    player = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="escape_sessions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    current_order = models.PositiveIntegerField(default=1)
    score = models.PositiveIntegerField(default=0)
    hints_used = models.PositiveIntegerField(default=0)
    wrong_attempts = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class EscapeAttempt(models.Model):
    session = models.ForeignKey(EscapeSession, on_delete=models.CASCADE, related_name="attempts")
    stage = models.ForeignKey(EscapeStage, on_delete=models.PROTECT, related_name="attempts")
    submitted_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

class EscapeHintUse(models.Model):
    session = models.ForeignKey(EscapeSession, on_delete=models.CASCADE, related_name="hint_uses")
    stage = models.ForeignKey(EscapeStage, on_delete=models.PROTECT, related_name="hint_uses")
    penalty = models.PositiveIntegerField(default=0)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["session", "stage"],
                name="unique_hint_per_stage_session",
            )
        ]