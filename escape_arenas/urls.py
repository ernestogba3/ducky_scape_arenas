from django.urls import path
from . import views

app_name = "escape_arenas"

urlpatterns = [

    path("", views.room_list, name="room_list"),
    path("room/<slug:slug>/", views.room_detail, name="room_detail"),
    path("room/<slug:slug>/ranking/", views.room_ranking, name="ranking"),

    path("room/<slug:slug>/start/", views.start_escape, name="start"),
    path("session/<int:pk>/", views.play_escape, name="play"),
    path("session/<int:pk>/answer/", views.submit_answer, name="answer"),
    path("session/<int:pk>/hint/", views.use_hint, name="hint"),
    path("session/<int:pk>/result/", views.escape_result, name="result"),

    path("history/", views.history, name="history"),
]