from typing import Any, Dict, Union

from django.contrib import messages
from django.core.files.storage import default_storage
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.translation import ugettext as _
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from ...core.models import Cashdesk, CashdeskSession, Transaction, TransactionPosition
from ..forms import InvoiceAddressForm
from ..invoicing import generate_invoice
from .utils import TroubleshooterUserRequiredMixin, troubleshooter_user_required


class TransactionListView(TroubleshooterUserRequiredMixin, ListView):
    template_name = "troubleshooter/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 50

    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        self.filter = dict()
        _filter = self.request.GET
        types = [t[0] for t in TransactionPosition.TYPES]

        if "type" in _filter and _filter["type"] in types:
            self.filter["type"] = _filter["type"]

        if "desk" in _filter and _filter["desk"]:
            try:
                desk = Cashdesk.objects.get(pk=_filter["desk"])
                self.filter["cashdesk"] = desk
            except Cashdesk.DoesNotExist:
                pass
        if "receipt" in _filter and _filter["receipt"]:
            try:
                self.filter["receipt"] = int(_filter["receipt"])
            except (TypeError, ValueError):
                messages.error(request, _("Receipt ID has to be an integer."))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet:
        qs = (
            TransactionPosition.objects.all()
            .order_by("-transaction__datetime")
            .select_related("transaction")
        )
        if "cashdesk" in self.filter:
            qs = qs.filter(transaction__session__cashdesk=self.filter["cashdesk"])
        if "type" in self.filter and self.filter["type"]:
            qs = qs.filter(type=self.filter["type"])
        if "receipt" in self.filter and self.filter["receipt"]:
            qs = qs.filter(transaction__receipt_id=self.filter["receipt"])
        return qs

    def get_context_data(self) -> Dict[str, Any]:
        ctx = super().get_context_data()
        ctx["cashdesks"] = Cashdesk.objects.all()
        ctx["types"] = [t[0] for t in TransactionPosition.TYPES]
        return ctx


class TransactionDetailView(TroubleshooterUserRequiredMixin, DetailView):
    template_name = "troubleshooter/transaction_detail.html"
    context_object_name = "transaction"
    model = Transaction

    def get_context_data(self, object):
        ctx = super().get_context_data()
        ctx["sessions"] = CashdeskSession.active.all()
        return ctx


@troubleshooter_user_required
def transaction_reprint(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    if request.method == "POST":
        try:
            transaction = Transaction.objects.get(pk=pk)
        except Transaction.DoesNotExist:
            messages.error(request, _("Unknown transaction."))
        else:
            if "session" in request.POST:
                session = CashdeskSession.objects.filter(
                    pk=request.POST.get("session")
                ).first()
            else:
                session = None
            transaction.print_receipt(do_open_drawer=False, session=session)
            messages.success(
                request,
                _("Receipt has been reprinted at {}.").format(
                    (session or transaction.session).cashdesk
                ),
            )

    return redirect("troubleshooter:transaction-detail", pk=pk)


@troubleshooter_user_required
def transaction_invoice(request, pk) -> Union[HttpResponse, HttpResponseRedirect]:
    def return_invoice(path: str, pk: int = pk) -> HttpResponse:
        response = HttpResponse(content=default_storage.open(path, "rb"))
        response["Content-Type"] = "application/pdf"
        response["Content-Disposition"] = "inline; filename=invoice-{}.pdf".format(pk)
        return response

    try:
        transaction = Transaction.objects.get(pk=pk)
    except Transaction.DoesNotExist:
        messages.error(request, _("Unknwon transaction."))
        return redirect("troubleshooter:transaction-list")

    path = transaction.get_invoice_path()
    if path:
        return return_invoice(path)

    form = InvoiceAddressForm()
    if request.method == "POST":
        form = InvoiceAddressForm(request.POST)
        if form.is_valid():
            path = generate_invoice(transaction, form.cleaned_data["address"])
            return return_invoice(path)
        else:
            messages.error(request, str(form.errors))

    return render(request, "troubleshooter/invoice.html", {"form": form})
