from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect

from postix.core.models import User


def is_backoffice_user(user: User) -> bool:
    if user.is_authenticated and not user.is_anonymous:
        return user.is_superuser or user.is_backoffice_user
    return False


class BackofficeUserRequiredMixin(UserPassesTestMixin):
    login_url = "backoffice:login"

    def test_func(self) -> bool:
        return is_backoffice_user(self.request.user)

    def handle_no_permission(self):
        return redirect("backoffice:login")


backoffice_user_required = user_passes_test(
    is_backoffice_user, login_url="backoffice:login"
)


def is_superuser(user: User) -> bool:
    if user.is_authenticated and not user.is_anonymous:
        return user.is_superuser
    return False


class SuperuserRequiredMixin(UserPassesTestMixin):
    login_url = "backoffice:login"

    def test_func(self) -> bool:
        return is_superuser(self.request.user)

    def handle_no_permission(self):
        return redirect("backoffice:login")


superuser_required = user_passes_test(is_superuser, login_url="backoffice:login")
