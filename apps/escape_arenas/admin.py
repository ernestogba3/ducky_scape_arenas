from django.contrib import admin

from .models import (
    EscapeRoom,
    Room,
    Stage,
    Puzzle,
    StageAsset,
    Hint,
    UserEscapeSession,
    UserRoomProgress,
    UserStageProgress,
    PuzzleAttempt,
    HintUsage,
    EscapeSettlement,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    fields = ("order", "name", "door_solution_hash")
    ordering = ("order",)


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0
    fields = ("order", "name", "type", "time_limit")
    ordering = ("order",)


class PuzzleInline(admin.TabularInline):
    model = Puzzle
    extra = 0
    fields = ("order", "title", "type", "points", "max_attempts")
    ordering = ("order",)


class StageAssetInline(admin.TabularInline):
    model = StageAsset
    extra = 0
    fields = ("order", "type", "url")
    ordering = ("order",)


class HintInline(admin.TabularInline):
    model = Hint
    extra = 0
    fields = ("order", "text", "coin_price", "penalty_seconds", "penalty_points", "unlock_after_seconds")
    ordering = ("order",)


# ---------------------------------------------------------------------------
# Bloque 1 — EscapeRoom y Room
# ---------------------------------------------------------------------------

@admin.register(EscapeRoom)
class EscapeRoomAdmin(admin.ModelAdmin):
    list_display        = ("name", "slug", "difficulty", "estimated_duration", "time_limit_seconds", "version", "is_active")
    list_filter         = ("difficulty", "is_active")
    search_fields       = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields     = ("created_at", "updated_at")
    inlines             = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display    = ("__str__", "escape_room", "order")
    list_filter     = ("escape_room",)
    search_fields   = ("name", "escape_room__name")
    readonly_fields = ("created_at", "updated_at")
    inlines         = [StageInline]


# ---------------------------------------------------------------------------
# Bloque 2 — Stage, Puzzle, StageAsset
# ---------------------------------------------------------------------------

@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display    = ("__str__", "room", "order", "type", "time_limit")
    list_filter     = ("type", "room__escape_room")
    search_fields   = ("name", "room__name", "room__escape_room__name")
    readonly_fields = ("created_at", "updated_at")
    inlines         = [PuzzleInline, StageAssetInline]


@admin.register(Puzzle)
class PuzzleAdmin(admin.ModelAdmin):
    list_display    = ("__str__", "stage", "type", "points", "max_attempts", "order", "version")
    list_filter     = ("type", "stage__room__escape_room")
    search_fields   = ("title", "stage__name", "stage__room__escape_room__name")
    readonly_fields = ("created_at", "updated_at")
    inlines         = [HintInline]


@admin.register(StageAsset)
class StageAssetAdmin(admin.ModelAdmin):
    list_display    = ("__str__", "stage", "type", "order", "url")
    list_filter     = ("type",)
    search_fields   = ("stage__name",)
    readonly_fields = ("created_at",)


# ---------------------------------------------------------------------------
# Bloque 3 — Hint
# ---------------------------------------------------------------------------

@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    list_display    = ("__str__", "puzzle", "room", "order", "coin_price", "penalty_seconds", "penalty_points", "unlock_after_seconds")
    list_filter     = ("puzzle__stage__room__escape_room",)
    search_fields   = ("text", "puzzle__title", "room__name")
    readonly_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# Bloque 4 — UserEscapeSession, UserRoomProgress
# ---------------------------------------------------------------------------

@admin.register(UserEscapeSession)
class UserEscapeSessionAdmin(admin.ModelAdmin):
    list_display    = ("user", "escape_room", "status", "score", "started_at", "finished_at", "expires_at")
    list_filter     = ("status", "escape_room")
    search_fields   = ("user__username", "escape_room__name")
    readonly_fields = ("id", "expires_at", "settled_at", "created_at", "updated_at")


@admin.register(UserRoomProgress)
class UserRoomProgressAdmin(admin.ModelAdmin):
    list_display = ("__str__", "session", "room", "status", "started_at", "completed_at", "coins_awarded")
    list_filter  = ("status",)
    search_fields = ("session__user__username", "room__name")


# ---------------------------------------------------------------------------
# Bloque 5 — UserStageProgress, PuzzleAttempt, HintUsage
# ---------------------------------------------------------------------------

@admin.register(UserStageProgress)
class UserStageProgressAdmin(admin.ModelAdmin):
    list_display  = ("__str__", "session", "stage", "status", "is_solved", "attempts", "time_spent_seconds", "gross_xp", "penalty_xp", "net_xp")
    list_filter   = ("status", "is_solved")
    search_fields = ("session__user__username", "stage__name")


@admin.register(PuzzleAttempt)
class PuzzleAttemptAdmin(admin.ModelAdmin):
    list_display  = ("player", "puzzle", "attempt_no", "is_correct", "submitted_at")
    list_filter   = ("is_correct",)
    search_fields = ("player__username", "puzzle__title")
    readonly_fields = ("submitted_at",)


@admin.register(HintUsage)
class HintUsageAdmin(admin.ModelAdmin):
    list_display  = ("player", "hint", "used_at", "coins_charged", "score_penalty", "time_penalty")
    search_fields = ("player__username",)
    readonly_fields = ("used_at",)


# ---------------------------------------------------------------------------
# Bloque 6 — EscapeSettlement
# ---------------------------------------------------------------------------

@admin.register(EscapeSettlement)
class EscapeSettlementAdmin(admin.ModelAdmin):
    list_display    = ("session", "reason", "gross_xp", "penalty_xp", "final_xp", "bonus_xp", "bonus_coins", "created_at")
    list_filter     = ("reason",)
    search_fields   = ("session__user__username",)
    readonly_fields = ("created_at",)