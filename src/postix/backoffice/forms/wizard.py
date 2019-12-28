import json

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.urls import reverse
from django.utils.translation import ugettext as _

from postix.core.models import Cashdesk, EventSettings, Item, Product, ProductItem


class EventSettingsForm(forms.ModelForm):
    class Meta:
        model = EventSettings
        exclude = []
        widgets = {
            "invoice_address": forms.widgets.Textarea,
            "invoice_footer": forms.widgets.Textarea,
            "receipt_address": forms.widgets.Textarea,
            "receipt_footer": forms.widgets.Textarea,
            "report_footer": forms.widgets.Textarea,
            "initialized": forms.widgets.HiddenInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.add_input(Submit("submit", _("Set up settings")))
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"


class CashdeskForm(forms.ModelForm):
    class Meta:
        model = Cashdesk
        fields = (
            "name",
            "ip_address",
            "printer_queue_name",
            "printer_handles_drawer",
            "handles_items",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.add_input(Submit("submit", _("Add Cashdesk")))
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"


class ImportForm(forms.Form):

    _file = forms.FileField(label=_("JSON File"))
    cashdesks = forms.IntegerField(
        min_value=0,
        required=False,
        label=_("Create cashdesks"),
        help_text=_("If you do not have any cashdesks yet, create them"),
    )
    questions = forms.CharField(
        required=False,
        label=_("Questions to import"),
        help_text=_(
            "Please enter comma separated question IDs that you wish to import"
        ),
    )

    def clean_questions(self):
        value = self.cleaned_data["questions"]
        if not value:
            return []
        values = value.split(",")
        return [v.strip() for v in values if v.strip().isdigit()]

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault(
            "questions", EventSettings.get_solo().last_import_questions
        )
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.add_input(Submit("submit", _("Import presale export")))
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"


class ItemForm(forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all(), widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Item
        fields = ("name", "description", "initial_stock")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            valid_products = ProductItem.objects.filter(item=self.instance).values_list(
                "product_id", flat=True
            )
            self.initial["products"] = Product.objects.filter(pk__in=valid_products)
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.add_input(Submit("submit", _("Save Item")))
        self.helper.label_class = "col-lg-2"
        self.helper.field_class = "col-lg-8"

    def save(self, *args, **kwargs):
        ret = super().save(*args, **kwargs)
        old_products = set(
            ProductItem.objects.filter(item=ret).values_list("product", flat=True)
        )
        new_products = set(self.cleaned_data["products"])

        for product in old_products - new_products:
            ProductItem.objects.filter(product=product, item=ret).delete()
        for product in new_products - old_products:
            ProductItem.objects.create(product=product, item=ret, amount=1)
        return ret


class WizardSettingsExportForm(forms.Form):
    include_cashdesks = forms.BooleanField(required=False, label=_("Include cashdesks"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Export settings")))
        self.helper.form_action = reverse("backoffice:wizard-settings-export")


class WizardSettingsImportForm(forms.Form):
    include_cashdesks = forms.BooleanField(required=False, label=_("Include cashdesks"))
    settings_file = forms.FileField(
        label=_("Settings file"),
        help_text=_("A JSON file exported from another postix event."),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit("submit", _("Import settings")))
        self.helper.form_action = reverse("backoffice:wizard-settings-import")

    def clean_settings_file(self):
        content = json.loads(self.cleaned_data["settings_file"].read().decode())
        if "settings" not in content:
            raise forms.ValidationError("Malformed settings file")
        return content

    def save(self):
        if not self.is_valid:
            raise Exception("Can only save a validated form.")
        from postix.core.models import Cashdesk, EventSettings

        import_data = self.cleaned_data["settings_file"]
        settings = EventSettings.get_solo()
        settings.loaddata(import_data.get("settings", {}))
        if self.cleaned_data["include_cashdesks"]:
            for cashdesk_data in import_data.get("cashdesks", []):
                cashdesk = (
                    Cashdesk.objects.filter(name__iexact=cashdesk_data["name"]).first()
                    or Cashdesk()
                )
                cashdesk.loaddata(cashdesk_data)

    def widget_attrs(self, widget):
        attrs = super().widget_attrs(widget)
        attrs["accept"] = "text/*"
        return attrs
