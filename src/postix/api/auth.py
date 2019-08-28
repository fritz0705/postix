from typing import Tuple

from django.http import HttpRequest
from django.utils.translation import ugettext as _
from rest_framework import authentication, exceptions
from rest_framework.authtoken.models import Token

from ..core.models import CashdeskSession, User
from ..core.utils.iputils import detect_cashdesk, get_ip_address


class TokenAuthentication(authentication.TokenAuthentication):
    def authenticate(self, request: HttpRequest) -> Tuple[User, Token]:
        self.request = request
        return super().authenticate(request)

    def authenticate_credentials(self, key) -> Tuple[User, Token]:
        try:
            session = CashdeskSession.objects.get(api_token=key)
        except CashdeskSession.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token.")

        if not session.is_active():
            raise exceptions.AuthenticationFailed("Your session has ended.")

        if session.cashdesk != detect_cashdesk(self.request):
            raise exceptions.AuthenticationFailed(
                _(
                    "Your token is valid for a different cashdesk. Your IP is: {}"
                ).format(get_ip_address(self.request))
            )

        return session.user, session.api_token
