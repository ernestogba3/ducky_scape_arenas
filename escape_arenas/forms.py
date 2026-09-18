class StageAnswerForm(forms.Form):
    answer = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=2000,
)

class EscapeRoomForm(forms.ModelForm):
    class Meta:
        model = EscapeRoom
        fields = [
            "title", "slug", "description", "story", "theme",
            "time_limit_minutes", "reward_xp", "reward_coins",
        ]