import json
from collections import defaultdict
from decimal import Decimal

from crispy_forms.helper import FormHelper
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.forms import formset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
)

from postix.backoffice.forms.record import (
    BillBulkForm,
    BillForm,
    CoinBulkForm,
    CoinForm,
    RecordCreateForm,
    RecordEntityForm,
    RecordSearchForm,
    RecordUpdateForm,
)
from postix.backoffice.report import generate_record
from postix.core.models.record import Record, RecordEntity, record_balance

from .utils import (
    BackofficeUserRequiredMixin,
    SuperuserRequiredMixin,
    backoffice_user_required,
)

User = get_user_model()


class RecordListView(BackofficeUserRequiredMixin, TemplateView):
    model = Record
    template_name = "backoffice/record_list.html"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)

        ctx["filter_form"] = RecordSearchForm(data=self.request.GET)

        records = Record.objects.prefetch_related(
            # prefetch_related should save some RAM and bandwith over select_related since we expect a small set of
            # objects to show up a large number of times
            "backoffice_user"
        ).select_related(
            "cash_movement",
            "cash_movement__session",
            "cash_movement__session__cashdesk",
            "cash_movement__session__user",
        )
        if ctx["filter_form"].is_valid():
            filters = ctx["filter_form"].cleaned_data
            if filters.get("date_min"):
                records = records.filter(datetime__gte=filters.get("date_min"))
            if filters.get("date_max"):
                records = records.filter(datetime__lte=filters.get("date_max"))
            if filters.get("backoffice_user"):
                records = records.filter(
                    backoffice_user__username__icontains=filters.get("backoffice_user")
                )
            if filters.get("carrier"):
                records = records.filter(
                    Q(carrier__icontains=filters.get("carrier"))
                    | Q(cash_movement__session__user__username=filters.get("carrier"))
                    | Q(cash_movement__session__user__firstname=filters.get("carrier"))
                    | Q(cash_movement__session__user__lastname=filters.get("carrier"))
                )
            if filters.get("source"):
                records = records.filter(
                    Q(
                        cash_movement__session__cashdesk__name__icontains=filters.get(
                            "source"
                        )
                    )
                    | Q(
                        cash_movement__session__cashdesk__record_name__icontains=filters.get(
                            "source"
                        )
                    )
                    | Q(entity__name__icontains=filters.get("source"))
                    | Q(entity__detail__icontains=filters.get("source"))
                )

        running_total = 0
        for obj in records:
            if obj.type == "inflow":
                running_total += obj.amount
            else:
                running_total -= obj.amount
            obj.running_total = running_total
        ctx["records"] = reversed(records)
        return ctx


class RecordCreateView(BackofficeUserRequiredMixin, CreateView):
    model = Record
    form_class = RecordCreateForm
    template_name = "backoffice/new_record.html"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["backoffice_users"] = User.objects.filter(is_backoffice_user=True)
        ctx["carriers"] = set(Record.objects.all().values_list("carrier", flat=True))
        return ctx

    def get_success_url(self):
        return reverse(
            "backoffice:record-print", kwargs={"pk": self.get_form().instance.pk}
        )


class RecordBalanceView(BackofficeUserRequiredMixin, TemplateView):
    model = Record
    form_class = RecordCreateForm
    template_name = "backoffice/new_balance.html"

    @cached_property
    def balance(self):
        return record_balance()

    @cached_property
    def formsets(self):
        result = dict()
        request_data = self.request.POST if self.request.method == "POST" else None
        result["bills_automated"] = formset_factory(BillForm)(
            request_data, prefix="bills_automated"
        )
        result["bills_manually"] = formset_factory(BillForm)(
            request_data, prefix="bills_manually"
        )
        result["bills_bulk"] = formset_factory(BillBulkForm)(
            request_data, prefix="bills_bulk"
        )
        result["coins_automated"] = formset_factory(CoinForm)(
            request_data, prefix="coins_automated"
        )
        result["coins_bulk"] = formset_factory(CoinBulkForm)(
            request_data, prefix="coins_bulk"
        )
        return result

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if not all([f.is_valid() for f in self.formsets.values()]):
            messages.warning(_("Something seems wrong here."))
            return super().post(request, *args, **kwargs)

        total_value = Decimal(
            str(
                sum(
                    [
                        form.total_value()
                        for formset in self.formsets.values()
                        for form in formset
                    ]
                )
            )
        )
        total_data = dict()
        for name, formset in self.formsets.items():
            total_data[name] = defaultdict(int)
            for form in formset:
                for key, value in form.cleaned_data.items():
                    total_data[name][key] += value or 0
                total_data[name]["total"] += form.total_value()
        expected_value = self.balance
        direction = "inflow" if total_value >= expected_value else "outflow"
        total_data["expected"] = float(expected_value)
        total_data["total"] = float(total_value)
        record = Record.objects.create(
            type=direction,
            amount=abs(expected_value - total_value),
            backoffice_user=request.user,
            is_balancing=True,
            data=json.dumps(total_data),
        )
        Record.objects.all().update(is_locked=True)
        return redirect(reverse("backoffice:record-print", kwargs={"pk": record.pk}))

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["balance"] = self.balance
        ctx["formsets"] = self.formsets
        helper = FormHelper()
        helper.form_tag = False
        ctx["helper"] = helper
        return ctx


class RecordDetailView(BackofficeUserRequiredMixin, UpdateView):
    model = Record
    form_class = RecordUpdateForm
    template_name = "backoffice/record_detail.html"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["backoffice_users"] = User.objects.filter(is_backoffice_user=True)
        ctx["carriers"] = set(Record.objects.all().values_list("carrier", flat=True))
        return ctx

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super().get_form_kwargs(*args, **kwargs)
        kwargs["editable"] = "edit" in self.request.GET and not self.object.is_locked
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        record = self.get_object()
        if record.is_locked:
            messages.error(self.request, _("This record cannot be modified any more."))
            return redirect(self.get_success_url())
        difference = form.cleaned_data["amount"] - record.amount
        if record.cash_movement:
            movement = record.cash_movement
            if movement.cash > 0:
                movement.cash += difference
            else:
                movement.cash -= difference
            movement.save()
            if record.closes_session and movement.session:
                if movement.session.cash_after > 0:
                    movement.session.cash_after += difference
                else:
                    movement.session.cash_after -= difference
                movement.session.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("backoffice:record-print", kwargs={"pk": self.kwargs["pk"]})


@backoffice_user_required
def record_print(request, pk: int = None):
    if pk is None:
        record = Record()
        content = generate_record(record)
    else:
        record = get_object_or_404(Record, pk=pk)
        if (
            not record.record_path or "cached" not in request.GET
        ):  # TODO: don't regenerate pdf always
            generate_record(record)
        content = default_storage.open(record.record_path, "rb")

    response = HttpResponse(content=content)
    response["Content-Type"] = "application/pdf"
    response["Content-Disposition"] = "inline; filename=record-{}.pdf".format(
        record.pk if record.pk else "blank"
    )
    return response


class RecordEntityListView(SuperuserRequiredMixin, ListView):
    model = RecordEntity
    template_name = "backoffice/record_entity_list.html"
    context_object_name = "entities"


class RecordEntityCreateView(SuperuserRequiredMixin, CreateView):
    model = RecordEntity
    form_class = RecordEntityForm
    template_name = "backoffice/new_record_entity.html"

    def get_success_url(self):
        return reverse("backoffice:record-entity-list")


class RecordEntityDetailView(SuperuserRequiredMixin, UpdateView):
    model = RecordEntity
    form_class = RecordEntityForm
    template_name = "backoffice/new_record_entity.html"

    def get_success_url(self):
        return reverse("backoffice:record-entity-list")


class RecordEntityDeleteView(SuperuserRequiredMixin, DeleteView):
    model = RecordEntity
    template_name = "backoffice/delete_record_entity.html"
    context_object_name = "record"

    def get_success_url(self):
        return reverse("backoffice:record-entity-list")
