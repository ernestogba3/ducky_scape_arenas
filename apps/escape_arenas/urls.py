from django.urls import path
from . import views
from . import views

app_name = "escape_arenas"

urlpatterns = [
    # Catálogo
    path("", views.room_list, name="room_list"),
    path("room/<slug:slug>/", views.room_detail, name="room_detail"),

    # CRUD del profesor (ANTES de las rutas de partida)
    path("my-rooms/", views.my_escape_rooms, name="my_rooms"),
    path("room/create/", views.escape_room_create, name="room_create"),
    path("room/<slug:slug>/edit/", views.escape_room_update, name="room_update"),
    path("room/<slug:slug>/delete/", views.escape_room_delete, name="room_delete"),

    # CRUD anidado genérico
    path("child/create/<str:child_type>/<int:parent_pk>/", views.child_create, name="child_create"),
    path("child/<str:child_type>/<int:pk>/edit/", views.child_update, name="child_update"),
    path("child/<str:child_type>/<int:pk>/delete/", views.child_delete, name="child_delete"),

    # Partida
    path("room/<slug:slug>/start/", views.escape_start, name="escape_start"),
    path("session/<uuid:pk>/play/", views.escape_play, name="play"),
    path("session/<uuid:pk>/submit/", views.escape_submit, name="submit"),
    path("session/<uuid:pk>/hint/", views.escape_hint, name="hint"),
    path("session/<uuid:pk>/result/", views.escape_result, name="result"),

    # Historial
    path("history/", views.escape_history, name="history"),
]