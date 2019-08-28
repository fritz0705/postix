from typing import Any, Dict

from django.contrib import messages
from django.db.models import Q
from django.utils.translation import ugettext as _
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from ...core.models import ListConstraint
from .utils import TroubleshooterUserRequiredMixin


class ListConstraintListView(TroubleshooterUserRequiredMixin, ListView):
    template_name = "troubleshooter/constraints_list.html"
    context_object_name = "constraints"
    model = ListConstraint


class ListConstraintDetailView(TroubleshooterUserRequiredMixin, DetailView):
    template_name = "troubleshooter/constraint_detail.html"
    context_object_name = "constraint"
    model = ListConstraint

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        ctx["restricted"] = False
        obj = kwargs["object"]

        if self.request.GET and self.request.GET["filter"]:
            query = self.request.GET["filter"]

            if obj.confidential and len(query) < 3:
                ctx["entries"] = []
                ctx["restricted"] = True
                messages.error(
                    self.request,
                    _(
                        "Search strings must be 3 characters or longer for confidential lists."
                    ),
                )
            else:
                ctx["entries"] = obj.entries.filter(
                    Q(name__icontains=query) | Q(identifier__icontains=query)
                )
                if obj.confidential:
                    ctx["entries"] = ctx["entries"][:10]
                    ctx["restricted"] = ctx["entries"].count() > 10
        else:
            if obj.confidential:
                ctx["entries"] = []
                ctx["restricted"] = True
            else:
                ctx["entries"] = obj.entries.all()
        return ctx
