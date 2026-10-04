from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone


class Room(models.Model):
    """Habitación de la aventura. Contenido compartido, no depende de ningún jugador."""

    title = models.CharField(max_length=150)
    order = models.PositiveIntegerField(default=1)
    description = models.TextField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.title}"


class Stage(models.Model):
    """Prueba (puzle) dentro de una habitación."""

    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="stages")
    title = models.CharField(max_length=150)
    statement = models.TextField()
    expected_answer = models.TextField()
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["room", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "order"],
                name="unique_stage_order_per_room",
            )
        ]

    def __str__(self):
        return f"{self.room.title} — {self.order}. {self.title}"


class EscapeRoomSession(models.Model):
    """Partida global de un jugador: estado y cuenta atrás."""

    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "En curso"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Fallada"
        ABANDONED = "ABANDONED", "Abandonada"

    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="escape_sessions",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    time_limit_seconds = models.PositiveIntegerField(default=1800)

    def __str__(self):
        return f"{self.player} — {self.status} — {self.started_at:%Y-%m-%d %H:%M}"

    # El servidor manda: el tiempo se calcula siempre desde started_at.
    @property
    def deadline(self):
        return self.started_at + timedelta(seconds=self.time_limit_seconds)

    @property
    def remaining_seconds(self):
        return max(0, int((self.deadline - timezone.now()).total_seconds()))

    @property
    def is_expired(self):
        return timezone.now() >= self.deadline


class PlayerProgress(models.Model):
    """Posición actual del jugador dentro de su sesión."""

    session = models.ForeignKey(
        EscapeRoomSession,
        on_delete=models.CASCADE,
        related_name="progress",
    )
    current_room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="+")
    current_stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="+")
    mistakes_count = models.PositiveIntegerField(default=0)
    is_finished = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session"],
                name="unique_progress_per_session",
            )
        ]

    def __str__(self):
        return f"Progreso de {self.session.player}: {self.current_stage}"


class StageAttempt(models.Model):
    """Registro de cada vez que un jugador entra en una prueba. Base de las estadísticas.

    Sin UniqueConstraint(session, stage): si el jugador abandona y vuelve,
    se crea una fila nueva y la antigua queda con completed_at vacío.
    """

    session = models.ForeignKey(
        EscapeRoomSession,
        on_delete=models.CASCADE,
        related_name="stage_attempts",
    )
    stage = models.ForeignKey(Stage, on_delete=models.PROTECT, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.session.player} — {self.stage} — {'OK' if self.is_correct else 'sin resolver'}"

    @property
    def duration(self):
        """Tiempo empleado en la prueba, o None si aún no se ha completado."""
        if self.completed_at is None:
            return None
        return self.completed_at - self.started_at