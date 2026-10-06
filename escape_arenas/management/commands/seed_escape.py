from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from escape_arenas.models import EscapeRoom, EscapeStage

User = get_user_model()


class Command(BaseCommand):
    help = "Crea la sala Full Stack Lockdown con sus fases"

    def handle(self, *args, **options):
        creator, _ = User.objects.get_or_create(
            username="profesor",
            defaults={"is_staff": True, "is_superuser": True},
        )

        room, _ = EscapeRoom.objects.get_or_create(
            slug="full-stack-lockdown",
            defaults={
                "title": "Full Stack Lockdown",
                "description": "Ocho cerraduras protegen la consola de recuperación.",
                "story": "El servidor de Ducky Arena ha quedado bloqueado...",
                "theme": EscapeRoom.Theme.FULL_STACK,
                "difficulty": EscapeRoom.Difficulty.MEDIUM,
                "time_limit_minutes": 35,
                "reward_xp": 500,
                "reward_coins": 200,
                "is_published": True,
                "creator": creator,
            },
        )

        stages = [
            (1, "HTML/CSS", "Repara el enlace de acceso", "WEB", "EXACT", "<a>"),
            (2, "JavaScript", "Salida de la función", "JAVASCRIPT", "EXACT", "[20, 40]"),
            (3, "ReactJS", "Corrige props/state", "REACT", "EXACT", "useState"),
            (4, "Python", "Comprensión de listas", "PYTHON", "EXACT", "[4, 16]"),
            (5, "Django", "Consulta ORM", "DJANGO", "CASE_INSENSITIVE", "filter"),
            (6, "SQL", "Reconstruye el JOIN", "SQL", "CASE_INSENSITIVE", "inner join"),
            (7, "Regex", "Patrón para clave", "REGEX", "REGEX_PATTERN", r"^[A-Z]{3}\d{4}$"),
            (8, "Git", "Secuencia de hotfix", "GIT", "CASE_INSENSITIVE", "git switch -c hotfix"),
        ]

        for order, title, narrative, category, answer_type, expected in stages:
            EscapeStage.objects.get_or_create(
                room=room,
                order=order,
                defaults={
                    "title": title,
                    "narrative": narrative,
                    "statement": f"Fase {order}: {narrative}",
                    "category": category,
                    "answer_type": answer_type,
                    "expected_answer": expected,
                    "points": 100 if order <= 3 else 150,
                    "hint_text": "Revisa la documentación oficial.",
                    "hint_penalty": 25,
                },
            )

        self.stdout.write(self.style.SUCCESS("Contenido inicial creado."))