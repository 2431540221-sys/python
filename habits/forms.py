from django import forms

from config.forms import BootstrapFormMixin

from .models import Habit


class HabitForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Habit
        fields = ["name", "description", "weekly_target", "streak_goal", "reminder_enabled", "reminder_time"]
        widgets = {
            "reminder_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "weekly_target": forms.NumberInput(attrs={"min": 1, "max": 7}),
            "streak_goal": forms.NumberInput(attrs={"min": 1, "placeholder": "Ví dụ 21"}),
        }
        help_texts = {"streak_goal": "Để trống nếu bạn chưa muốn đặt mục tiêu chuỗi."}
