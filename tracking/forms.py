from django import forms

from config.forms import BootstrapFormMixin

from .models import ACTIVITY_CHOICES, MOOD_CHOICES, DailyCheckin, JournalEntry


class CheckinForm(BootstrapFormMixin, forms.ModelForm):
    mood = forms.TypedChoiceField(
        label="Hôm nay bạn thấy thế nào?", choices=MOOD_CHOICES, coerce=int, widget=forms.RadioSelect
    )

    class Meta:
        model = DailyCheckin
        fields = ["mood", "sleep_hours", "activity_type", "activity_minutes", "note"]
        widgets = {
            "sleep_hours": forms.NumberInput(attrs={"step": "0.5", "min": 0, "max": 24}),
            "activity_minutes": forms.NumberInput(attrs={"min": 0, "max": 1440}),
        }

    def clean(self):
        data = super().clean()
        kind, minutes = data.get("activity_type"), data.get("activity_minutes")
        if kind and kind != "none" and not minutes:
            self.add_error("activity_minutes", "Hãy nhập số phút bạn đã vận động.")
        if kind == "none" and minutes:
            data["activity_minutes"] = 0
        return data


class JournalForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = ["title", "content", "tags"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 10, "placeholder": "Viết điều bạn muốn ghi lại. Chỉ bạn đọc được."}),
            "tags": forms.TextInput(attrs={"placeholder": "học tập, gia đình, sức khỏe"}),
        }
