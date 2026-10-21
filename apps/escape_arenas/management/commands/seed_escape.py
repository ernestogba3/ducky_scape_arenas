"""Carga una sola vez la aventura funcional; nunca reescribe partidas existentes."""
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction
from apps.escape_arenas.models import EscapeRoom, Room, Stage, Puzzle, Hint

class Command(BaseCommand):
    help = 'Carga Full Stack Lockdown sin sobrescribir contenido ni usuarios.'

    @transaction.atomic
    def handle(self, *args, **options):
        existing = EscapeRoom.objects.filter(slug='full-stack-lockdown').first()
        if existing:
            self.stdout.write('La aventura ya existe; se conserva sin cambios.')
            return
        for model, ids in [(EscapeRoom, [1001]), (Room, [1001]),
                           (Stage, range(1001, 1009)), (Puzzle, range(1001, 1009)),
                           (Hint, range(1001, 1009))]:
            if model.objects.filter(pk__in=ids).exists():
                raise CommandError('IDs de demo ocupados. No se ha sobrescrito nada; ajusta el fixture en una copia.')
        call_command('loaddata', 'escape_demo', verbosity=0)
        self.stdout.write(self.style.SUCCESS('Full Stack Lockdown lista: ocho fases, 30 minutos, 800 puntos.'))
