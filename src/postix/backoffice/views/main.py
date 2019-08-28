from django.db.models import Sum
from django.views.generic import TemplateView

from postix.core.models import Quota
from postix.core.models.base import Item, ItemSupplyPack, Product
from postix.core.models.preorder import PreorderPosition

from .. import checks
from .utils import SuperuserRequiredMixin


class MainView(SuperuserRequiredMixin, TemplateView):
    template_name = "backoffice/main.html"

    def get_context_data(self):
        ctx = super().get_context_data()
        ctx["products"] = Product.objects.all()
        ctx["items"] = Item.objects.all()
        ctx["quotas"] = Quota.objects.all()
        ctx["check_errors"] = checks.all_errors()
        ctx["all_preorders"] = PreorderPosition.objects.filter(
            preorder__is_canceled=False, product__is_admission=True
        ).count()
        ctx["redeemed_preorders"] = PreorderPosition.objects.filter(
            preorder__is_canceled=False,
            product__is_admission=True,
            transaction_positions__isnull=False,
        ).count()
        ctx["preorder_percentage"] = (
            round(ctx["redeemed_preorders"] * 100 / ctx["all_preorders"], 2)
            if ctx["all_preorders"]
            else 0
        )
        ctx["troubleshooter_stock"] = (
            ItemSupplyPack.objects.filter(state="troubleshooter")
            .order_by()
            .values("item", "item__name")
            .annotate(s=Sum("amount"))
        )
        return ctx
