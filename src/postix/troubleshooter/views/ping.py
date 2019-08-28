from django.urls import reverse
from django.views.generic import FormView

from postix.core.models.ping import Ping, generate_ping
from postix.troubleshooter.forms import CashdeskForm
from postix.troubleshooter.views.utils import TroubleshooterUserRequiredMixin


def get_minutes(timedelta):
    return timedelta.total_seconds() // 60


class PingView(TroubleshooterUserRequiredMixin, FormView):
    template_name = "troubleshooter/ping.html"
    form_class = CashdeskForm

    def get_context_data(self):
        ctx = super().get_context_data()
        if Ping.objects.exists():
            pings = Ping.objects.order_by("pinged")
            ping_count = pings.count()
            ping_success = pings.filter(ponged__isnull=False)
            ping_success_count = ping_success.count()

            durations = [get_minutes(p.ponged - p.pinged) for p in ping_success]

            ctx["pings"] = pings
            ctx["ping_success"] = ping_success_count
            ctx["loss_percent"] = "{:.2f}".format(
                (ping_count - ping_success_count) * 100 / ping_count
            )

            if durations:
                ctx["total_min"] = min(durations)
                ctx["total_max"] = max(durations)
                ctx["total_avg"] = sum(durations) / len(durations)
                ctx["total_mdev"] = sum(
                    ((duration - ctx["total_avg"]) ** 2) for duration in durations
                ) / len(durations)
        else:
            ctx["pings"] = []
            ctx["ping_success"] = 0

        return ctx

    def post(self, request):
        form = self.get_form()
        if form.is_valid():
            cashdesk = form.cleaned_data.get("cashdesk")
            generate_ping(cashdesk)
            return self.form_valid(form)

    def get_success_url(self):
        return reverse("troubleshooter:ping")
