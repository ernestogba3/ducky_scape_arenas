from django.contrib import admin

from apps.escape_arenas.models import (
    EscapeRoomSession,
    PlayerProgress,
    Room,
    Stage,
    StageAttempt,
)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("title", "order")
    search_fields = ("title", "description")
    ordering = ("order",)


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("title", "room", "order")
    list_filter = ("room",)
    search_fields = ("title", "statement")
    ordering = ("room", "order")
    list_select_related = ("room",)


@admin.register(EscapeRoomSession)
class EscapeRoomSessionAdmin(admin.ModelAdmin):
    list_display = ("player", "status", "started_at", "finished_at", "time_limit_seconds")
    list_filter = ("status",)
    search_fields = ("player__username",)
    ordering = ("-started_at",)
    list_select_related = ("player",)


@admin.register(PlayerProgress)
class PlayerProgressAdmin(admin.ModelAdmin):
    list_display = ("session", "current_room", "current_stage", "mistakes_count", "is_finished")
    list_filter = ("is_finished", "current_room")
    list_select_related = ("session__player", "current_room", "current_stage")


@admin.register(StageAttempt)
class StageAttemptAdmin(admin.ModelAdmin):
    list_display = ("session", "stage", "started_at", "completed_at", "duration", "is_correct")
    list_filter = ("is_correct", "stage__room")
    ordering = ("-started_at",)
    list_select_related = ("session__player", "stage__room")