from django.contrib import messages
from django.urls import reverse
from django.views.generic import FormView
from django.views.generic.list import ListView

from postix.core.models import Info
from postix.core.utils import times
from postix.troubleshooter.forms import PrintForm
from postix.troubleshooter.views.utils import TroubleshooterUserRequiredMixin


class InformationListView(TroubleshooterUserRequiredMixin, ListView):
    template_name = "troubleshooter/information_list.html"
    context_object_name = "information"
    paginate_by = 50
    model = Info
    queryset = Info.objects.all().order_by("id")


class InformationDetailView(TroubleshooterUserRequiredMixin, FormView):
    template_name = "troubleshooter/information_detail.html"
    form_class = PrintForm

    def get_context_data(self):
        ctx = super().get_context_data()
        ctx["information"] = Info.objects.get(pk=self.kwargs["pk"])
        return ctx

    def post(self, request, pk):
        form = self.get_form()
        if form.is_valid():
            info = Info.objects.get(pk=self.kwargs["pk"])
            cashdesk = form.cleaned_data.get("cashdesk")
            amount = form.cleaned_data.get("amount")
            for _ in times(amount):
                cashdesk.printer.print_text(info.content)
            messages.success(request, "Done.")
            return self.form_valid(form)

        else:
            messages.error(request, form.errors)
            return self.form_valid(form)

    def get_success_url(self):
        return reverse("troubleshooter:information-detail", kwargs=self.kwargs)
