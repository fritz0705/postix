from typing import Union

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import ugettext as _
from django.views.generic import FormView, ListView

from ...core.models import User
from ..forms import CreateUserForm, ResetPasswordForm, get_normal_user_form
from .utils import BackofficeUserRequiredMixin, backoffice_user_required


@backoffice_user_required
def create_user_view(request: HttpRequest) -> Union[HttpResponseRedirect, HttpResponse]:
    if request.method == "POST":
        form = CreateUserForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(**form.cleaned_data)
            if user.is_backoffice_user:
                messages.success(
                    request,
                    _("Backoffice user {user} has been created.").format(
                        user=user.username
                    ),
                )
            else:
                messages.success(
                    request,
                    _("User {user} has been created.").format(user=user.username),
                )
            return redirect("backoffice:create-user")
    else:
        form = get_normal_user_form()

    return render(request, "backoffice/create_user.html", {"form": form})


class UserListView(BackofficeUserRequiredMixin, ListView):
    template_name = "backoffice/user_list.html"
    queryset = User.objects.all().order_by("username")

    def dispatch(self, request, *args, **kwargs):
        if "export" not in request.GET:
            return super().dispatch(request, *args, **kwargs)
        user_list = (
            User.objects.filter(cashdesksession__isnull=False).order_by().distinct()
        )
        user_list = sorted(user_list, key=lambda u: u.hours[0], reverse=True)
        content = "nick,name,minutes\n"
        content += "\n".join(
            [
                "{nick},{name},{minutes}".format(
                    nick=user.username,
                    name=user.get_full_name(),
                    minutes=int(user.hours[0].seconds / 60)
                    + user.hours[0].days * 24 * 60,
                )
                for user in user_list
            ]
        )
        response = HttpResponse(content, content_type="text/plain;charset=utf-8")
        return response


class ResetPasswordView(BackofficeUserRequiredMixin, FormView):
    form_class = ResetPasswordForm
    template_name = "backoffice/reset_password.html"

    def get_context_data(self, **kwargs):
        pk = self.kwargs["pk"]
        ctx = super().get_context_data(**kwargs)
        ctx["user"] = User.objects.get(pk=pk)
        return ctx

    def post(self, request, pk):
        form = self.get_form()
        pk = self.kwargs["pk"]
        user = User.objects.get(pk=pk)
        if user.is_superuser and not request.user.is_superuser:
            messages.error(
                self.request,
                _(
                    "You can only change administrator passwords if you are an admin yourself."
                ),
            )
            return self.form_valid(form)

        if form.is_valid():
            user.set_password(form.cleaned_data.get("password1"))
            user.save()
            messages.success(self.request, _("Passwort has been changed."))
            return self.form_valid(form)
        return self.form_invalid(form)

    def get_success_url(self):
        return reverse("backoffice:user-list")
