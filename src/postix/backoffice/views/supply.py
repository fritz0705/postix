from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView, ListView

from postix.backoffice.forms.supply import SupplyCreateForm, SupplyMoveForm
from postix.core.models.base import Item, ItemSupplyPack

from .utils import BackofficeUserRequiredMixin

User = get_user_model()


class SupplyListView(BackofficeUserRequiredMixin, ListView):
    model = ItemSupplyPack
    template_name = "backoffice/supply_list.html"
    context_object_name = "supplies"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["in_states"] = (
            ItemSupplyPack.objects.order_by()
            .values("item", "item__name", "state")
            .annotate(s=Sum("amount"))
            .order_by("state", "item__name")
        )
        return ctx


class SupplyCreateView(BackofficeUserRequiredMixin, FormView):
    form_class = SupplyCreateForm
    template_name = "backoffice/supply_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get("initial", {})
        if "amount" in self.request.GET:
            initial["amount"] = int(self.request.GET.get("amount"))
        if "item" in self.request.GET:
            initial["item"] = get_object_or_404(Item, pk=self.request.GET.get("item"))
        kwargs["initial"] = initial
        return kwargs

    def form_valid(self, form):
        isp = ItemSupplyPack.objects.create(
            amount=form.cleaned_data["amount"],
            item=form.cleaned_data["item"],
            identifier=form.cleaned_data["identifier"],
            state="backoffice",
        )
        isp.logs.create(user=self.request.user, new_state="backoffice")
        messages.success(
            self.request,
            _("The supply pack {id} has been created.").format(
                id=form.cleaned_data["identifier"]
            ),
        )
        return redirect(
            self.request.path
            + "?amount={amount}&item={item.pk}".format_map(form.cleaned_data)
        )


class SupplyMoveOutView(BackofficeUserRequiredMixin, FormView):
    form_class = SupplyMoveForm
    template_name = "backoffice/supply_move_out.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get("initial", {})
        if "identifier" in self.request.GET:
            initial["identifier"] = self.request.GET.get("identifier")
        kwargs["initial"] = initial
        kwargs["require_state"] = "backoffice"
        return kwargs

    def form_valid(self, form):
        form.cleaned_data["identifier"].state = "troubleshooter"
        form.cleaned_data["identifier"].save()
        form.cleaned_data["identifier"].logs.create(
            user=self.request.user, new_state="troubleshooter"
        )
        messages.success(
            self.request,
            _("The supply pack {id} has been moved to the troubleshooter.").format(
                id=form.cleaned_data["identifier"]
            ),
        )
        return redirect(self.request.path)


class SupplyMoveInView(BackofficeUserRequiredMixin, FormView):
    form_class = SupplyMoveForm
    template_name = "backoffice/supply_move_in.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        initial = kwargs.get("initial", {})
        if "identifier" in self.request.GET:
            initial["identifier"] = self.request.GET.get("identifier")
        kwargs["initial"] = initial
        kwargs["require_state"] = "troubleshooter"
        return kwargs

    def form_valid(self, form):
        form.cleaned_data["identifier"].state = "backoffice"
        form.cleaned_data["identifier"].save()
        form.cleaned_data["identifier"].logs.create(
            user=self.request.user, new_state="troubleshooter"
        )
        messages.success(
            self.request,
            _("The supply pack {id} has been moved to the backoffice.").format(
                id=form.cleaned_data["identifier"]
            ),
        )
        return redirect(self.request.path)


class SupplyMoveAwayView(BackofficeUserRequiredMixin, FormView):
    form_class = SupplyMoveForm
    template_name = "backoffice/supply_move_away.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["require_state"] = "backoffice"
        initial = kwargs.get("initial", {})
        if "identifier" in self.request.GET:
            initial["identifier"] = self.request.GET.get("identifier")
        kwargs["initial"] = initial
        return kwargs

    def form_valid(self, form):
        form.cleaned_data["identifier"].logs.create(
            user=self.request.user, new_state="troubleshooter"
        )
        form.cleaned_data["identifier"].state = "dissolved"
        form.cleaned_data["identifier"].save()
        messages.success(
            self.request,
            _("The supply pack {id} has been dissolved.").format(
                id=form.cleaned_data["identifier"]
            ),
        )
        return redirect(self.request.path)
