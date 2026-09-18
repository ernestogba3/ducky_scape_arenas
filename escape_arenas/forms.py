class EscapeRoomForm(forms.ModelForm):
    class Meta:
        model = EscapeRoom
        fields = [
            "title", "slug", "description", "story", "theme",
            "time_limit_minutes", "reward_xp", "reward_coins",
        ]