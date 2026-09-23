from django.contrib import admin

from escape_arenas.models import (
    EscapeAttempt,
    EscapeHintUse,
    EscapeRoom,
    EscapeSession,
    EscapeStage,
)

# Register your models here.
admin.site.register(EscapeRoom)
admin.site.register(EscapeStage)
admin.site.register(EscapeSession)
admin.site.register(EscapeAttempt)
admin.site.register(EscapeHintUse)

@admin.register(EscapeRoom)
class EscapeRoomAdmin(admin.ModelAdmin):
    list_display = ("title", "theme", "time_limit_minutes", "is_published", "creator")
    list_filter = ("theme", "is_published")
    search_fields = ("title", "description")


@admin.register(EscapeStage)
class EscapeStageAdmin(admin.ModelAdmin):
    list_display = ("title", "room", "category", "points")
    list_filter = ("room", "category")
    ordering = ("room", "order")