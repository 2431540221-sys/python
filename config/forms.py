from django import forms


class BootstrapFormMixin:
    """Apply Bootstrap 5 control classes to Django form widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if getattr(widget, "input_type", None) == "hidden":
                continue
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                class_name = "form-check-input"
            elif isinstance(widget, forms.Select):
                class_name = "form-select"
            else:
                class_name = "form-control"
            existing = widget.attrs.get("class", "").split()
            if class_name not in existing:
                widget.attrs["class"] = " ".join(existing + [class_name])
