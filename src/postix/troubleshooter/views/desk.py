from django.contrib import messages
from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _

from ...core.models import CashdeskSession, TroubleshooterNotification
from .utils import troubleshooter_user_required


@troubleshooter_user_required
def check_requests(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"has_requests": TroubleshooterNotification.objects.active().exists()}
    )


@troubleshooter_user_required
def confirm_resupply(request: HttpRequest, pk: int) -> HttpResponseRedirect:
    if request.method == "POST":
        try:
            session = CashdeskSession.objects.get(pk=pk)
            TroubleshooterNotification.objects.active(session=session).update(
                status=TroubleshooterNotification.STATUS_ACK, modified_by=request.user
            )
            messages.success(
                request, _("{} has been resupplied.").format(session.cashdesk)
            )
        except CashdeskSession.DoesNotExist:
            messages.error(request, _("Unknown session."))

    return redirect("troubleshooter:main")
