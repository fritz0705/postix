from django import forms


class CalculatorWidget(forms.NumberInput):
    def __init__(self, *args, attrs=None, **kwargs):
        attrs = attrs or dict()
        attrs["type"] = "text"
        attrs["class"] = "calculatable"
        super().__init__(*args, attrs=attrs, **kwargs)


class RelaxedDecimalField(forms.DecimalField):
    widget = CalculatorWidget

    def to_python(self, value):
        return super().to_python(
            value.replace(",", ".") if isinstance(value, str) else value
        )

    def validate(self, value):
        return super().validate(
            value.replace(",", ".") if isinstance(value, str) else value
        )
