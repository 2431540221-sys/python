from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from config.forms import BootstrapFormMixin

from .models import User


class RegisterForm(BootstrapFormMixin, UserCreationForm):
    consent_ai = forms.BooleanField(
        required=False,
        label="Cho phép AI coach đọc số liệu (tâm trạng, giấc ngủ, thói quen) để tóm tắt tuần. "
              "Nội dung journal không bao giờ được gửi đi.",
    )

    class Meta:
        model = User
        fields = ("username", "email")
        labels = {"username": "Tên đăng nhập", "email": "Email (không bắt buộc)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Mật khẩu"
        self.fields["password2"].label = "Nhập lại mật khẩu"
        self.fields["email"].required = False
        self.fields["username"].help_text = "Tối đa 150 ký tự: chữ, số và @/./+/-/_"

    def save(self, commit=True):
        user = super().save(commit=False)
        user.consent_ai = self.cleaned_data.get("consent_ai", False)
        if commit:
            user.save()
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(label="Tên đăng nhập", widget=forms.TextInput(attrs={"autofocus": True}))
    password = forms.CharField(label="Mật khẩu", strip=False, widget=forms.PasswordInput)
    error_messages = {
        "invalid_login": "Sai tên đăng nhập hoặc mật khẩu.",
        "inactive": "Tài khoản này đã bị khóa.",
    }


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")
        labels = {
            "username": "Tên đăng nhập",
            "first_name": "Tên",
            "last_name": "Họ",
            "email": "Email",
        }


class UserPreferencesForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("consent_ai", "email_notifications_enabled")
        labels = {
            "consent_ai": "Cho phép AI Coach sử dụng dữ liệu wellbeing tổng hợp và câu hỏi tôi chủ động gửi.",
            "email_notifications_enabled": "Gửi thông báo của ứng dụng đến email của tôi.",
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("email_notifications_enabled") and not self.instance.email:
            self.add_error(
                "email_notifications_enabled",
                "Hãy thêm email trong mục Thông tin cá nhân trước khi bật thông báo email.",
            )
        return cleaned_data
