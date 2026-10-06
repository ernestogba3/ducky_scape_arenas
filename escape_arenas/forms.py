from django import forms

from .models import EscapeRoom, Room, Stage


class EscapeRoomForm(forms.ModelForm):
    """Formulario para que un profesor cree/edite una EscapeRoom."""

    class Meta:
        model = EscapeRoom
        fields = [
            "title",
            "slug",
            "description",
            "story",
            "time_limit_minutes",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "story": forms.Textarea(attrs={"rows": 6}),
        }
        # creator e is_published NO se exponen: los fija el servidor.

    def clean_time_limit_minutes(self):
        value = self.cleaned_data["time_limit_minutes"]
        if value <= 0:
            raise forms.ValidationError("El tiempo límite debe ser mayor que 0.")
        return value


class RoomForm(forms.ModelForm):
    """Formulario para crear/editar una habitación dentro de una EscapeRoom."""

    class Meta:
        model = Room
        fields = ["title", "order", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_order(self):
        value = self.cleaned_data["order"]
        if value < 1:
            raise forms.ValidationError("El orden debe ser 1 o superior.")
        return value


class StageForm(forms.ModelForm):
    """Formulario para crear/editar una prueba (Stage) dentro de una Room."""

    class Meta:
        model = Stage
        fields = [
            "title",
            "statement",
            "expected_answer",
            "order",
            "points",
            "hint_text",
            "hint_penalty",
        ]
        widgets = {
            "statement": forms.Textarea(attrs={"rows": 4}),
            "expected_answer": forms.Textarea(attrs={"rows": 3}),
            "hint_text": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_order(self):
        value = self.cleaned_data["order"]
        if value < 1:
            raise forms.ValidationError("El orden debe ser 1 o superior.")
        return value

    def clean_points(self):
        value = self.cleaned_data["points"]
        if value <= 0:
            raise forms.ValidationError("Los puntos deben ser mayores que 0.")
        return value

    def clean_hint_penalty(self):
        value = self.cleaned_data["hint_penalty"]
        if value < 0:
            raise forms.ValidationError("La penalización no puede ser negativa.")
        return value


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