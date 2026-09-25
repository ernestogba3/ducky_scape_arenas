from django import forms

from ducky_scape_arenas.escape_arenas.models import EscapeStage

class EscapeRoomForm(forms.ModelForm):
    class Meta:
        model = EscapeRoom
        fields = [
            "title", "slug", "description", "story", "theme",
            "time_limit_minutes", "reward_xp", "reward_coins",
        ]
class StageForm(forms.ModelForm):
    class Meta:
        model = EscapeStage
        fields = [
            "order", "title", "narrative", "statement", "category", "answer_type",
            "expected_answer", "points", "hint_text", "hint_penalty", "max_attempts",
        ]
        
class StageAnswerForm(forms.Form):
    answer = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=2000,
    )

