from django import forms

# TODO: reescribir en Fase 2.
from django import forms

from .models import EscapeRoom, Room, Stage, Hint, Puzzle


class EscapeRoomForm(forms.ModelForm):
    """Formulario para que un profesor cree/edite una EscapeRoom."""

    class Meta:
        model = EscapeRoom
        fields = [
            "name",
            "slug",
            "description",
            "time_limit_seconds",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
        # creator e is_published NO se exponen: los fija el servidor.

    def clean_time_limit_seconds(self):
        value = self.cleaned_data["time_limit_seconds"]
        if value <= 0:
            raise forms.ValidationError("El tiempo límite debe ser mayor que 0.")
        return value


class RoomForm(forms.ModelForm):
    """Formulario para crear/editar una habitación dentro de una EscapeRoom."""

    class Meta:
        model = Room
        fields = ["name", "order", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_order(self):
        value = self.cleaned_data["order"]
        if value < 1:
            raise forms.ValidationError("El orden debe ser 1 o superior.")
        return value


class PuzzleForm(forms.ModelForm):
    """Formulario para crear/editar un Puzzle dentro de una Stage.

    Un Puzzle es la prueba concreta que el jugador resuelve. Una Stage
    puede tener varios Puzzles; este form crea uno.
    """

    class Meta:
        model = Puzzle
        fields = [
            "stage",
            "title",
            "description",
            "type",
            "config",
            "solution_hash",
            "max_attempts",
            "points",
            "order",
            "version",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "config": forms.Textarea(attrs={"rows": 4}),
            "solution_hash": forms.Textarea(attrs={"rows": 2}),
        }
        help_texts = {
            "config": (
                'JSON específico del tipo. Ej para MULTIPLE_CHOICE: '
                '{"options": ["Rojo", "Azul", "Verde"]}'
            ),
            "solution_hash": (
                "Solución esperada. En Fase 1 se compara en texto plano; "
                "en Fase 2 se sustituirá por un hash real."
            ),
            "max_attempts": "Dejar vacío para intentos ilimitados.",
            "points": "Puntos base del puzzle. Ecomotor los traducirá a XP.",
        }

    def clean_order(self):
        value = self.cleaned_data["order"]
        if value < 1:
            raise forms.ValidationError("El orden debe ser 1 o superior.")
        return value

    def clean_points(self):
        value = self.cleaned_data["points"]
        if value < 0:
            raise forms.ValidationError("Los puntos no pueden ser negativos.")
        return value

    def clean_max_attempts(self):
        value = self.cleaned_data.get("max_attempts")
        if value is not None and value < 1:
            raise forms.ValidationError(
                "Si se especifica, el número de intentos debe ser 1 o superior."
            )
        return value

    def clean_config(self):
        """Asegura que config sea un dict válido (JSONField)."""
        value = self.cleaned_data.get("config") or {}
        if not isinstance(value, dict):
            raise forms.ValidationError("La configuración debe ser un objeto JSON.")
        return value

    def clean(self):
        """Validación cruzada según el tipo de puzzle."""
        cleaned = super().clean()
        puzzle_type = cleaned.get("type")
        config = cleaned.get("config") or {}

        if puzzle_type == Puzzle.Type.MULTIPLE_CHOICE:
            options = config.get("options")
            if not isinstance(options, list) or len(options) < 2:
                self.add_error(
                    "config",
                    "MULTIPLE_CHOICE requiere {'options': [...]} con al menos 2 opciones.",
                )

        if puzzle_type == Puzzle.Type.SEQUENCE:
            steps = config.get("steps")
            if not isinstance(steps, list) or len(steps) < 1:
                self.add_error(
                    "config",
                    "SEQUENCE requiere {'steps': [...]} con al menos 1 paso.",
                )

        return cleaned

class EscapeSubmitForm(forms.Form):
    """Formulario que envía el jugador con su respuesta a la prueba actual."""

    answer = forms.CharField(
        label="Tu respuesta",
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 4, "autocomplete": "off"}),
    )

    def clean_answer(self):
        value = self.cleaned_data["answer"].strip()
        if not value:
            raise forms.ValidationError("La respuesta no puede estar vacía.")
        return value
    
class HintForm(forms.ModelForm):
    """Formulario para crear/editar una pista de un Puzzle o de una Room."""

    class Meta:
        model = Hint
        fields = [
            "puzzle",
            "room",
            "text",
            "order",
            "coin_price",
            "penalty_seconds",
            "penalty_points",
            "unlock_after_seconds",
        ]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        puzzle = cleaned.get("puzzle")
        room = cleaned.get("room")

        # Exactamente uno de los dos debe estar presente (coherente con el
        # CheckConstraint del model).
        if (puzzle is None) == (room is None):
            raise forms.ValidationError(
                "Una pista debe apuntar a un Puzzle O a una Room, nunca a ambos "
                "ni a ninguno."
            )
        return cleaned

    def clean_coin_price(self):
        value = self.cleaned_data.get("coin_price", 0)
        if value < 0:
            raise forms.ValidationError("El precio no puede ser negativo.")
        return value

    def clean_penalty_seconds(self):
        value = self.cleaned_data.get("penalty_seconds", 0)
        if value < 0:
            raise forms.ValidationError("La penalización de tiempo no puede ser negativa.")
        return value

    def clean_penalty_points(self):
        value = self.cleaned_data.get("penalty_points", 0)
        if value < 0:
            raise forms.ValidationError("La penalización de puntos no puede ser negativa.")
        return value