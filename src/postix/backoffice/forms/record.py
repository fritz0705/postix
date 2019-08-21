from datetime import datetime

from crispy_forms.helper import FormHelper
from django import forms
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from postix.core.models import Record, RecordEntity

from .session import RelaxedDecimalField

User = get_user_model()


class RecordCreateForm(forms.ModelForm):
    backoffice_user = forms.CharField(max_length=254, label=_('Backoffice angel'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['backoffice_user'].queryset = User.objects.filter(
            is_backoffice_user=True
        )
        self.fields['datetime'].required = False
        self.helper = FormHelper()
        self.helper.form_tag = False

    def clean_backoffice_user(self) -> User:
        value = self.cleaned_data['backoffice_user']
        try:
            return User.objects.filter(is_backoffice_user=True).get(username=value)
        except User.DoesNotExist:
            raise forms.ValidationError(
                _('Angel does not exist or is no backoffice angel.')
            )

    def clean_amount(self) -> User:
        amount = self.cleaned_data['amount']
        if amount is None:
            raise forms.ValidationError(_('"Amount" is a required field.'))
        if amount < 0:
            raise forms.ValidationError(_('No negative values allowed!'))
        return amount

    def clean_datetime(self) -> datetime:
        value = self.cleaned_data['datetime']
        return value or now()

    class Meta:
        model = Record
        fields = ('type', 'datetime', 'entity', 'carrier', 'amount', 'backoffice_user')
        field_classes = {'amount': RelaxedDecimalField}


class RecordUpdateForm(RecordCreateForm):
    backoffice_user = forms.CharField(max_length=254, label=_('Backoffice angel'))

    def __init__(self, *args, **kwargs):
        self.editable = kwargs.pop('editable', False)
        initial = kwargs.get('initial', dict())
        initial['backoffice_user'] = str(kwargs['instance'].backoffice_user)
        super().__init__(*args, **kwargs)
        if not self.editable:
            for field_name, field in self.fields.items():
                field.disabled = True
        self.helper = FormHelper()
        self.helper.form_tag = False

    class Meta:
        model = Record
        fields = ('type', 'datetime', 'entity', 'carrier', 'amount', 'backoffice_user')

    def save(self, *args, **kwargs):
        i = super().save(*args, **kwargs)
        self.instance.cash_movement.cash = (-1 if self.instance.type == "inflow" else 1) * self.instance.amount
        self.instance.cash_movement.save()
        return i


class RecordEntityForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False

    class Meta:
        model = RecordEntity
        fields = ('name', 'detail')


class BillForm(forms.Form):
    bill_500 = forms.IntegerField(min_value=0, required=False, label='500 €')
    bill_200 = forms.IntegerField(min_value=0, required=False, label='200 €')
    bill_100 = forms.IntegerField(min_value=0, required=False, label='100 €')
    bill_50 = forms.IntegerField(min_value=0, required=False, label='50 €')
    bill_20 = forms.IntegerField(min_value=0, required=False, label='20 €')
    bill_10 = forms.IntegerField(min_value=0, required=False, label='10 €')
    bill_5 = forms.IntegerField(min_value=0, required=False, label='5 €')

    def total_value(self):
        total = 0
        for bill, amount in self.cleaned_data.items():
            total += int(bill.rsplit('_', maxsplit=2)[-1]) * (amount or 0)
        return total


class CoinForm(forms.Form):
    coin_200 = forms.IntegerField(min_value=0, required=False, label='2 €')
    coin_50 = forms.IntegerField(min_value=0, required=False, label='0,50 €')
    coin_100 = forms.IntegerField(min_value=0, required=False, label='1 €')
    coin_20 = forms.IntegerField(min_value=0, required=False, label='0,20 €')
    coin_5 = forms.IntegerField(min_value=0, required=False, label='0,05 €')
    coin_10 = forms.IntegerField(min_value=0, required=False, label='0,10 €')
    coin_2 = forms.IntegerField(min_value=0, required=False, label='0,02 €')
    coin_1 = forms.IntegerField(min_value=0, required=False, label='0,01 €')

    def total_value(self):
        total = 0
        for coin, amount in self.cleaned_data.items():
            total += int(coin.rsplit('_', maxsplit=1)[-1]) * (amount or 0)
        return total / 100


class BillBulkForm(forms.Form):
    bill_50000 = forms.IntegerField(min_value=0, required=False, label='500 €')
    bill_20000 = forms.IntegerField(min_value=0, required=False, label='200 €')
    bill_10000 = forms.IntegerField(min_value=0, required=False, label='100 €')
    bill_5000 = forms.IntegerField(min_value=0, required=False, label='50 €')
    bill_2000 = forms.IntegerField(min_value=0, required=False, label='20 €')
    bill_1000 = forms.IntegerField(min_value=0, required=False, label='10 €')
    bill_500 = forms.IntegerField(min_value=0, required=False, label='5 €')

    def total_value(self):
        total = 0
        for bill, amount in self.cleaned_data.items():
            total += int(bill.rsplit('_', maxsplit=1)[-1]) * (amount or 0)
        return total


class CoinBulkForm(forms.Form):
    coin_5000 = forms.IntegerField(min_value=0, required=False, label='2 €')
    coin_2000 = forms.IntegerField(min_value=0, required=False, label='0,50 €')
    coin_2500 = forms.IntegerField(min_value=0, required=False, label='1 €')
    coin_800 = forms.IntegerField(min_value=0, required=False, label='0,20 €')
    coin_250 = forms.IntegerField(min_value=0, required=False, label='0,05 €')
    coin_400 = forms.IntegerField(min_value=0, required=False, label='0,10 €')
    coin_100 = forms.IntegerField(min_value=0, required=False, label='0,02 €')
    coin_50 = forms.IntegerField(min_value=0, required=False, label='0,01 €')

    def total_value(self):
        total = 0
        for coin, amount in self.cleaned_data.items():
            total += int(coin.rsplit('_', maxsplit=1)[-1]) * (amount or 0)
        return total / 100


class RecordSearchForm(forms.Form):
    date_min = forms.DateTimeField(required=False, label=_('Start date'))
    date_max = forms.DateTimeField(required=False, label=_('End date'))
    source = forms.CharField(max_length=254, label=_('Source'), required=False)
    user = forms.CharField(max_length=254, label=_('User'), required=False)
    carrier = forms.CharField(max_length=254, label=_('Carrier'), required=False)
