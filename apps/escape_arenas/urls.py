from django.urls import path
from . import views

app_name = "escape_arenas"

urlpatterns = [
    # Catálogo
    path("", views.room_list, name="room_list"),
    path("room/<slug:slug>/", views.room_detail, name="room_detail"),

    # Partida
    path("room/<slug:slug>/start/", views.escape_start, name="escape_start"),
    path("session/<uuid:pk>/play/", views.escape_play, name="play"),
    path("session/<uuid:pk>/submit/", views.escape_submit, name="submit"),
    path("session/<uuid:pk>/hint/", views.escape_hint, name="hint"),
    path("session/<uuid:pk>/result/", views.escape_result, name="result"),

    # Historial
    path("history/", views.escape_history, name="history"),
]