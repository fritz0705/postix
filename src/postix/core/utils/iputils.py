from typing import Union

from django.http import HttpRequest

from postix.core.models import Cashdesk


def get_ip_address(request: HttpRequest) -> str:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    else:
        return request.META.get("REMOTE_ADDR")


def detect_cashdesk(request: HttpRequest) -> Union[Cashdesk, None]:
    try:
        return Cashdesk.objects.get(ip_address=get_ip_address(request), is_active=True)
    except Cashdesk.DoesNotExist:
        return None
