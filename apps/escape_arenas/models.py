"""Modelos del módulo DuckyEscape (apps/escape_arenas).

Propuesta Fase 1 basada en el documento "Duckyscape Arenas · Modelos ·
Propuesta V1" del 13/10/2026 (secciones 5, 6, 11, 12 y 14).

Decisiones tomadas y asumidas en este fichero:
- Identidad: User estándar de Django (settings.AUTH_USER_MODEL resuelve a
  django.contrib.auth.models.User mientras no se declare un CustomUser).
- XP de stage: calculada por stage pero NO consolidada hasta EscapeSettlement.
- Multijugador: fuera del MVP. Un UserEscapeSession = un user.
- Pistas: solo sobre Puzzle o Room (nunca sobre la salida final).
- Monedas y RewardEvent: números brutos como columna provisional;
  marcados con `# TODO` donde deberán pasar a FK a Bank/Ecomotor
  cuando esas apps existan.
"""

import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


# ---------------------------------------------------------------------------
# Bloque 1 — Contenido raíz: EscapeRoom y Room
# ---------------------------------------------------------------------------


class EscapeRoom(models.Model):
    """Aventura completa (una partida de principio a fin).

    Agrupa todas las Rooms de un mismo escape y guarda la configuración
    global: tiempo, dificultad, hash de la salida final y versión.
    """

    class Difficulty(models.TextChoices):
        EASY = "EASY", "Fácil"
        MEDIUM = "MEDIUM", "Media"
        HARD = "HARD", "Difícil"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    description = models.TextField()
    difficulty = models.CharField(
        max_length=12,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_escape_rooms",
        null=True,  # temporal para no romper datos existentes
        blank=True,
    )
    # Duración estimada en minutos, para enseñar al jugador antes de empezar.
    estimated_duration = models.PositiveIntegerField(help_text="Minutos estimados")
    # Límite real de la partida en segundos (lo que antes vivía en la sesión).
    time_limit_seconds = models.PositiveIntegerField(default=1800)
    # Hash de la salida final. Por ahora puede ser el texto en claro;
    # el servicio de Fase 2 decidirá si usar make_password/check_password.
    final_solution_hash = models.CharField(max_length=255)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} (v{self.version})"


class Room(models.Model):
    """Sala dentro de una EscapeRoom. Contenido compartido, no depende de ningún jugador."""

    escape_room = models.ForeignKey(
        EscapeRoom,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    name = models.CharField(max_length=150)
    description = models.TextField()
    order = models.PositiveIntegerField(default=1)
    image = models.ImageField(upload_to="escape/rooms/", blank=True, null=True)
    # Hash de la puerta de salida de esta sala.
    door_solution_hash = models.CharField(max_length=255)
    # Fragmento del acertijo final que se revela al abrir la puerta.
    final_fragment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["escape_room", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["escape_room", "order"],
                name="unique_room_order_per_escape_room",
            ),
        ]

    def __str__(self):
        return f"{self.escape_room.name} — {self.order}. {self.name}"


# ---------------------------------------------------------------------------
# Bloque 2 — Pasos y pruebas: Stage, Puzzle, StageAsset
# ---------------------------------------------------------------------------


class Stage(models.Model):
    """Etapa dentro de una Room. Es el "paso" del recorrido, no la prueba.

    Una Stage puede tener uno o varios Puzzles, y cuando se completan
    todos (según completion_condition) se revela su fragment y se
    desbloquea la siguiente Stage de la Room.
    """

    class Type(models.TextChoices):
        INTRO = "INTRO", "Introducción"
        PUZZLE = "PUZZLE", "Prueba"
        LOCK = "LOCK", "Cerradura"
        FINAL = "FINAL", "Final de sala"

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="stages",
    )
    name = models.CharField(max_length=150)
    description = models.TextField()
    order = models.PositiveIntegerField(default=1)
    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.PUZZLE,
    )
    # Condición configurable para considerar la stage "resuelta".
    # Ej: {"require": "all_puzzles"} o {"require": "any_puzzle"} o
    # {"require": "n_puzzles", "n": 2}. El servicio de Fase 2 interpreta esto.
    completion_condition = models.JSONField(default=dict, blank=True)
    # Límite opcional en segundos solo para esta stage.
    # None significa "sin límite propio" (vale el de la EscapeRoom).
    time_limit = models.PositiveIntegerField(null=True, blank=True)
    # Fragmento del acertijo que revela esta stage al completarse.
    # Puede estar vacío si la stage es INTRO o si el fragmento va en la Room.
    fragment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["room", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "order"],
                name="unique_stage_order_per_room",
            ),
        ]

    def __str__(self):
        return f"{self.room.name} — {self.order}. {self.name}"


class Puzzle(models.Model):
    """Prueba concreta dentro de una Stage. Es lo que el jugador resuelve.

    Una Stage puede tener uno o varios Puzzles; cada Puzzle tiene su
    propia solución y su propia configuración.
    """

    class Type(models.TextChoices):
        TEXT = "TEXT", "Texto libre"
        NUMBER = "NUMBER", "Número"
        MULTIPLE_CHOICE = "MULTIPLE_CHOICE", "Opción múltiple"
        SEQUENCE = "SEQUENCE", "Secuencia"
        OBJECT = "OBJECT", "Objeto a usar"

    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name="puzzles",
    )
    title = models.CharField(max_length=150)
    description = models.TextField()
    type = models.CharField(max_length=24, choices=Type.choices)
    # Configuración específica según type. Ej para MULTIPLE_CHOICE:
    # {"options": ["Rojo", "Azul", "Verde"]}. El servicio valida por tipo.
    config = models.JSONField(default=dict, blank=True)
    # Hash de la solución. De momento puede ser texto en claro;
    # el servicio de Fase 2 decidirá si usar make_password/check_password.
    solution_hash = models.CharField(max_length=255)
    # Intentos máximos; None = ilimitado.
    max_attempts = models.PositiveIntegerField(null=True, blank=True)
    # Puntos base que otorga resolverlo. Es contenido, no es XP:
    # Ecomotor decide luego cómo traducir estos puntos a XP real.
    points = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stage", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["stage", "order"],
                name="unique_puzzle_order_per_stage",
            ),
        ]

    def __str__(self):
        return f"{self.stage} — {self.order}. {self.title}"


class StageAsset(models.Model):
    """Recurso multimedia asociado a una Stage: imagen, audio, vídeo o texto largo."""

    class Type(models.TextChoices):
        IMAGE = "IMAGE", "Imagen"
        AUDIO = "AUDIO", "Audio"
        VIDEO = "VIDEO", "Vídeo"
        DOCUMENT = "DOCUMENT", "Documento"

    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    type = models.CharField(max_length=20, choices=Type.choices)
    url = models.URLField(max_length=500)
    # Metadatos libres: pie de foto, duración, etc.
    metadata = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["stage", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["stage", "order"],
                name="unique_asset_order_per_stage",
            ),
        ]

    def __str__(self):
        return f"{self.stage} — {self.get_type_display()} #{self.order}"


# ---------------------------------------------------------------------------
# Bloque 3 — Pistas: Hint
# ---------------------------------------------------------------------------


class Hint(models.Model):
    """Pista que el jugador puede comprar durante la partida.

    Una pista pertenece a un Puzzle concreto (ayuda a resolverlo) o a
    una Room (ayuda a abrir la puerta final de la sala), nunca a las
    dos a la vez. Nunca hay pistas sobre la salida final de la EscapeRoom
    (eso lo resuelve el jugador uniendo los fragmentos).
    """

    puzzle = models.ForeignKey(
        Puzzle,
        on_delete=models.CASCADE,
        related_name="hints",
        null=True,
        blank=True,
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="hints",
        null=True,
        blank=True,
    )
    text = models.TextField()
    order = models.PositiveIntegerField(default=1)
    # Precio en monedas que cobra Bank al desbloquear la pista.
    coin_price = models.PositiveIntegerField(default=0)
    # Penalización en segundos: se resta al tiempo restante de la sesión.
    penalty_seconds = models.PositiveIntegerField(default=0)
    # Penalización en puntos: se resta al score bruto al liquidar.
    penalty_points = models.PositiveIntegerField(default=0)
    # Segundos desde el inicio de la stage/room antes de que la pista
    # pueda comprarse. 0 significa "disponible desde el principio".
    unlock_after_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            # Exactamente una FK destino: o puzzle o room, no ambas ni ninguna.
            models.CheckConstraint(
                condition=(
                    (Q(puzzle__isnull=False) & Q(room__isnull=True))
                    | (Q(puzzle__isnull=True) & Q(room__isnull=False))
                ),
                name="hint_targets_puzzle_xor_room",
            ),
            # Orden único por puzzle (cuando la pista cuelga de un puzzle).
            models.UniqueConstraint(
                fields=["puzzle", "order"],
                name="unique_hint_order_per_puzzle",
                condition=Q(puzzle__isnull=False),
            ),
            # Orden único por room (cuando la pista cuelga de una room).
            models.UniqueConstraint(
                fields=["room", "order"],
                name="unique_hint_order_per_room",
                condition=Q(room__isnull=False),
            ),
        ]

    def __str__(self):
        target = self.puzzle or self.room
        return f"Pista {self.order} para {target}"


# ---------------------------------------------------------------------------
# Bloque 4 — Estado de partida: UserEscapeSession y UserRoomProgress
# ---------------------------------------------------------------------------


class UserEscapeSession(models.Model):
    """Partida de un jugador en una EscapeRoom concreta.

    Guarda el estado global (status, tiempos, puntuación) y señala en qué
    Room y Stage está el jugador ahora mismo. Las métricas por sala y por
    stage viven en UserRoomProgress y UserStageProgress respectivamente.
    """

    class Status(models.TextChoices):
        WAITING = "WAITING", "En espera"
        PLAYING = "PLAYING", "Jugando"
        PAUSED = "PAUSED", "En pausa"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Fallada"
        ABANDONED = "ABANDONED", "Abandonada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="escape_sessions",
    )
    escape_room = models.ForeignKey(
        EscapeRoom,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    # Momento en el que esta sesión expira
    # (= started_at + rules_snapshot["time_limit_seconds"]).
    # Lo calcula y guarda el servicio al arrancar la partida;
    # así no se recalcula a cada request.
    expires_at = models.DateTimeField(null=True, blank=True)
    # Puntero: en qué sala y stage está el jugador ahora mismo.
    # Pueden ser null durante WAITING (aún no ha empezado).
    current_room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    current_stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    # Puntuación bruta acumulada durante la partida (sin penalizaciones aún).
    score = models.PositiveIntegerField(default=0)
    # Congelación de las reglas de la EscapeRoom en el momento de empezar.
    # Debe incluir al menos: time_limit_seconds, difficulty, version.
    # Así, si alguien edita la EscapeRoom después, esta partida no cambia.
    rules_snapshot = models.JSONField(default=dict, blank=True)
    # Cuándo se liquidó esta sesión (EscapeSettlement cerrado). Lo rellena
    # el servicio del bloque 6, no la lógica de juego.
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.escape_room.name} — {self.status}"

    @property
    def remaining_seconds(self):
        """Segundos restantes según expires_at. Si no ha empezado, None."""
        if self.expires_at is None:
            return None
        return max(0, int((self.expires_at - timezone.now()).total_seconds()))

    @property
    def is_expired(self):
        """True si ya pasó expires_at (y la sesión está jugándose)."""
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at


class UserRoomProgress(models.Model):
    """Estado de una Room dentro de una partida.

    Una fila por (sesión, room). La sala va cambiando de status a medida
    que el jugador la desbloquea, entra en ella y la completa.
    """

    class Status(models.TextChoices):
        LOCKED = "LOCKED", "Bloqueada"
        AVAILABLE = "AVAILABLE", "Disponible"
        COMPLETED = "COMPLETED", "Completada"

    session = models.ForeignKey(
        UserEscapeSession,
        on_delete=models.CASCADE,
        related_name="room_progress",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.PROTECT,
        related_name="+",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LOCKED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Fragmento final que el jugador se lleva al abrir la puerta de esta room.
    # Se copia desde Room.final_fragment al cerrar la sala.
    final_fragment_acquired = models.TextField(blank=True)
    # Monedas que Bank concedió al completar esta sala (dato "cacheado").
    # TODO: cuando exista ecomotor/bank, sustituir por FK a RewardEvent y
    # borrar este campo. De momento guardamos el número bruto para que la
    # vista pueda enseñarlo sin depender de otro módulo.
    coins_awarded = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["session", "room__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "room"],
                name="unique_room_progress_per_session",
            ),
        ]

    def __str__(self):
        return f"{self.session.user} — {self.room.name} — {self.status}"


# ---------------------------------------------------------------------------
# Bloque 5 — Detalle de partida: UserStageProgress, PuzzleAttempt, HintUsage
# ---------------------------------------------------------------------------


class UserStageProgress(models.Model):
    """Estado agregado de una Stage dentro de una partida.

    Una fila por (sesión, stage). Guarda contadores y XP calculada
    (pero pendiente de consolidar en EscapeSettlement).
    """

    class Status(models.TextChoices):
        LOCKED = "LOCKED", "Bloqueada"
        AVAILABLE = "AVAILABLE", "Disponible"
        IN_PROGRESS = "IN_PROGRESS", "En curso"
        COMPLETED = "COMPLETED", "Completada"
        FAILED = "FAILED", "Fallada"

    session = models.ForeignKey(
        UserEscapeSession,
        on_delete=models.CASCADE,
        related_name="stage_progress",
    )
    stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        related_name="+",
    )
    is_solved = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LOCKED,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Nº total de intentos sobre los puzzles de esta stage (suma de PuzzleAttempt).
    attempts = models.PositiveIntegerField(default=0)
    # Segundos reales que pasó el jugador en esta stage.
    time_spent_seconds = models.PositiveIntegerField(default=0)
    # Fragmento revelado al completar (copia de Stage.fragment en el momento).
    fragment_acquired = models.TextField(blank=True)
    # XP calculada pero pendiente de consolidar.
    # Ecomotor la postea cuando se liquide.
    gross_xp = models.PositiveIntegerField(default=0)
    penalty_xp = models.PositiveIntegerField(default=0)
    net_xp = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["session", "stage__room__order", "stage__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "stage"],
                name="unique_stage_progress_per_session",
            ),
        ]

    def __str__(self):
        return f"{self.session.user} — {self.stage} — {self.status}"


class PuzzleAttempt(models.Model):
    """Cada vez que un jugador envía una respuesta a un Puzzle.

    Es el historial fino: una fila por intento. El resumen por stage
    (cuántos intentos lleva, cuánto tiempo) vive en UserStageProgress.
    """

    session = models.ForeignKey(
        UserEscapeSession,
        on_delete=models.CASCADE,
        related_name="puzzle_attempts",
    )
    puzzle = models.ForeignKey(
        Puzzle,
        on_delete=models.PROTECT,
        related_name="attempts",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="puzzle_attempts",
    )
    # Nº de intento del jugador sobre este puzzle en esta sesión (1, 2, 3...).
    # Lo asigna el servicio al crear la fila, no se calcula "al vuelo".
    attempt_no = models.PositiveIntegerField()
    # Respuesta enviada por el jugador. JSON para admitir texto, número,
    # opción marcada o secuencia según Puzzle.type.
    answer = models.JSONField(default=dict, blank=True)
    is_correct = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["session", "puzzle", "attempt_no"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "puzzle", "attempt_no"],
                name="unique_puzzle_attempt_number",
            ),
        ]

    def __str__(self):
        mark = "OK" if self.is_correct else "KO"
        return f"{self.player} — {self.puzzle.title} #{self.attempt_no} ({mark})"


class HintUsage(models.Model):
    """Registro de una pista que el jugador ha comprado y usado.

    Una fila por (sesión, hint): no se puede comprar la misma pista dos
    veces en la misma partida (al segundo intento, se devuelve el uso
    existente sin cobrar).
    """

    session = models.ForeignKey(
        UserEscapeSession,
        on_delete=models.CASCADE,
        related_name="hint_usages",
    )
    hint = models.ForeignKey(
        Hint,
        on_delete=models.PROTECT,
        related_name="usages",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hint_usages",
    )
    used_at = models.DateTimeField(auto_now_add=True)
    # Penalizaciones aplicadas en el momento (copia de Hint.penalty_*
    # para que un cambio futuro de la pista no reescriba partidas vivas).
    score_penalty = models.PositiveIntegerField(default=0)
    time_penalty = models.PositiveIntegerField(default=0)
    # Monedas cobradas (dato "cacheado" mientras no exista Bank).
    # TODO: cuando exista bank, sustituir por FK 1:1 a Purchase y borrar
    # este campo. De momento guardamos el número bruto.
    coins_charged = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["session", "used_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "hint"],
                name="unique_hint_usage_per_session",
            ),
        ]

    def __str__(self):
        return f"{self.player} — pista {self.hint.order} de {self.session}"


# ---------------------------------------------------------------------------
# Bloque 6 — Cierre de partida: EscapeSettlement
# ---------------------------------------------------------------------------


class EscapeSettlement(models.Model):
    """Liquidación final de una partida.

    Una fila por sesión, creada cuando la sesión pasa a COMPLETED, FAILED
    o ABANDONED. Consolida la XP pendiente, aplica penalizaciones y, si
    corresponde, añade el bonus de salida.

    Es la bisagra con Ecomotor: cuando exista, esta tabla pedirá a
    Ecomotor un RewardEvent y guardará la referencia. De momento guarda
    los números brutos directamente.
    """

    class Reason(models.TextChoices):
        COMPLETED = "COMPLETED", "Aventura completada"
        TIME_EXPIRED = "TIME_EXPIRED", "Tiempo agotado"
        ABANDONED = "ABANDONED", "Abandonada por el jugador"
        FAILED = "FAILED", "Fallada por reglas de juego"

    session = models.OneToOneField(
        UserEscapeSession,
        on_delete=models.PROTECT,
        related_name="settlement",
    )
    # XP bruta sumada de todas las UserStageProgress de la sesión.
    gross_xp = models.PositiveIntegerField(default=0)
    # XP de penalización sumada (pistas, errores, timeouts por stage).
    penalty_xp = models.PositiveIntegerField(default=0)
    # XP final = max(0, gross_xp - penalty_xp). Lo calcula el servicio.
    final_xp = models.PositiveIntegerField(default=0)
    # Bonus de XP que solo se concede si la aventura termina COMPLETED.
    # En TIME_EXPIRED/ABANDONED/FAILED debe ser 0.
    bonus_xp = models.PositiveIntegerField(default=0)
    # Bonus de monedas por completar la aventura entera (lo paga Bank).
    # TODO: cuando exista bank, mover este número a una Transaction y
    # dejar aquí solo la referencia (reward_event FK a Ecomotor).
    bonus_coins = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=30, choices=Reason.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Liquidación de {self.session} — {self.reason} — {self.final_xp} XP"