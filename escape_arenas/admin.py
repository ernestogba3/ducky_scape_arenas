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