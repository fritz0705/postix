from crispy_forms.helper import FormHelper
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from postix.core.models import Item
from postix.core.models.base import ItemSupplyPack


class SupplyCreateForm(forms.Form):
    amount = forms.IntegerField(initial=50, label=_("Amount of items in pack"))
    item = forms.ModelChoiceField(Item.objects.all(), label=_("Type of items in pack"))
    identifier = forms.CharField(max_length=190, label=_("Pack barcode"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "item" in self.initial:
            self.fields["identifier"].widget.attrs["autofocus"] = "autofocus"
        else:
            self.fields["item"].widget.attrs["autofocus"] = "autofocus"
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_identifier(self):
        if not self.cleaned_data["identifier"].startswith("/supply "):
            raise ValidationError('The pack identifier needs to start with "/supply ".')
        if ItemSupplyPack.objects.filter(
            identifier=self.cleaned_data["identifier"]
        ).exists():
            raise ValidationError("This pack identifier has already been used!")
        return self.cleaned_data["identifier"]


class SupplyMoveForm(forms.Form):
    identifier = forms.CharField(max_length=190, label=_("Pack barcode"))

    def __init__(self, *args, **kwargs):
        self.require_state = kwargs.pop("require_state")
        super().__init__(*args, **kwargs)
        self.fields["identifier"].widget.attrs["autofocus"] = "autofocus"
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_identifier(self):
        try:
            isp = ItemSupplyPack.objects.get(identifier=self.cleaned_data["identifier"])
        except ItemSupplyPack.DoesNotExist:
            raise ValidationError("This pack identifier does not exist!")
        if self.require_state and isp.state != self.require_state:
            raise ValidationError(
                'This pack is currently in state "{}", no action performed!'.format(
                    isp.get_state_display()
                )
            )
        return isp
