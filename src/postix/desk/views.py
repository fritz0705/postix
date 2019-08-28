from typing import Union

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from django.views.generic import TemplateView

from ..core.models import Cashdesk
from ..core.utils.iputils import detect_cashdesk, get_ip_address


class LoginView(TemplateView):
    template_name = "desk/login.html"

    def dispatch(
        self, request: HttpRequest, *args, **kwargs
    ) -> Union[HttpResponseRedirect, HttpResponse]:
        if not self.cashdesk:
            return render(
                request,
                "desk/fail.html",
                {
                    "message": _("This is not a registered cashdesk."),
                    "detail": _("Your IP address is {0}").format(
                        get_ip_address(request)
                    ),
                },
            )
        if request.user.is_authenticated:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponseRedirect:
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(username=username, password=password)
        if user is not None:
            session = user.get_current_session()
            if session is None:
                messages.error(request, _("You do not have an active session."))
                return redirect("desk:login")

            if session.cashdesk != self.cashdesk:
                messages.error(
                    request,
                    _(
                        "Your session is scheduled for a different cashdesk. Please go to "
                        "{desk}"
                    ).format(desk=str(session.cashdesk)),
                )
                return redirect("desk:login")

            login(request, user)
            session.cashdesk.signal_next()
            return redirect("desk:main")
        else:
            messages.error(
                request, _("No user account matches the entered credentials.")
            )
        return redirect("desk:login")

    @cached_property
    def cashdesk(self) -> Cashdesk:
        return detect_cashdesk(self.request)


def logout_view(request: HttpRequest) -> HttpResponseRedirect:
    if request.user.is_authenticated:
        session = request.user.get_current_session()
    else:
        session = None
    logout(request)
    if session:
        session.cashdesk.signal_close()
    return redirect("desk:login")


@login_required(login_url="/login/")
def main_view(request: HttpRequest) -> HttpResponse:
    cashdesk = detect_cashdesk(request)
    session = request.user.get_current_session()
    if not cashdesk or session is None or session.cashdesk != cashdesk:
        return render(
            request,
            "desk/fail.html",
            {
                "message": _("You do not have an active session at this cashdesk."),
                "detail": _("You are logged in as {}.".format(request.user)),
                "offer_logout": True,
            },
        )

    if not session.start:
        session.start = now()
        session.save(update_fields=["start"])

    return render(request, "desk/main.html")
