from typing import Any, Dict, List, Union

import pytz
from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from django.utils.formats import date_format
from django.utils.timezone import now
from django.utils.translation import ugettext as _
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from postix.core.models import ItemMovement
from postix.core.models.base import ItemSupplyPack

from ..core.models import (
    Cashdesk,
    ListConstraint,
    ListConstraintEntry,
    Ping,
    Preorder,
    PreorderPosition,
    Product,
    Transaction,
)
from ..core.models.ping import generate_ping
from ..core.utils import round_decimal
from ..core.utils.compat import detail_route, list_route
from ..core.utils.flow import (
    FlowError,
    redeem_preorder_ticket,
    reverse_transaction,
    sell_ticket,
)
from .serializers import (
    ListConstraintEntrySerializer,
    ListConstraintSerializer,
    PingSerializer,
    PreorderPositionSerializer,
    PreorderSerializer,
    ProductSerializer,
    TransactionSerializer,
)


class ProcessException(Exception):
    def __init__(self, data: Any):
        self.data = data


class PreorderViewSet(ReadOnlyModelViewSet):
    """
    This is a read-only list of all preorders.
    """

    queryset = Preorder.objects.all().order_by("id")
    serializer_class = PreorderSerializer
    permission_classes = (IsAdminUser,)


class PreorderPositionViewSet(ReadOnlyModelViewSet):
    """
    This is a read-only list of all preorder positions.

    You can filter using query parameters by the ``secret`` field. You can also
    search for secrets by using the ``?search=`` query parameter, that will only
    match the *beginning* of secrets and only if the search query has more than
    6 characters.
    """

    queryset = PreorderPosition.objects.all().order_by("id")
    serializer_class = PreorderPositionSerializer

    def get_queryset(self) -> QuerySet:
        queryset = PreorderPosition.objects.all().order_by("id")
        exact_param = self.request.GET.get("secret", None)
        search_param = self.request.GET.get("search", None)
        if exact_param is not None:
            queryset = queryset.filter(secret__iexact=exact_param)
        elif search_param is not None and len(search_param) >= 6:
            queryset = queryset.filter(secret__istartswith=search_param)
        else:
            queryset = queryset.none()
        return queryset


class TransactionViewSet(ReadOnlyModelViewSet):
    """
    This is a list of all transactions. It is also the endpoint you will use to
    create a new transaction.

    Creating transactions
    ---------------------
    To create a transaction, you have to ``POST`` a JSON document to this endpoint
    that matches the following form:

        {
            "cash_given": "12.00",
            "positions": [
                {
                    "type": "redeem",
                    "secret": "abcdefgh"
                },
                {
                    "type": "sell",
                    "product": 1,
                    "authorized_by": null
                },
                ...
            ]
        }
    """

    queryset = Transaction.objects.all().prefetch_related("positions").order_by("id")
    serializer_class = TransactionSerializer

    def create(self, request: HttpRequest, *args, **kwargs) -> Response:
        try:
            response = self.perform_create(request)
            return Response(response, status=status.HTTP_201_CREATED)
        except ProcessException as e:
            return Response(e.data, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def perform_create(
        self, request: HttpRequest
    ) -> Dict[str, Union[bool, List[Dict]]]:
        data = request.data
        trans = Transaction()
        if "cash_given" in data:
            trans.cash_given = round_decimal(data.get("cash_given", "0.00"))
        session = self.request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )
        trans.session = session
        trans.save()

        position_feedback = []
        success = True
        pos = data.get("positions", [])

        if not pos:
            raise ProcessException("Empty transaction")

        for inppos in pos:
            postype = inppos.get("type", "")
            try:
                if postype == "redeem":
                    pos = redeem_preorder_ticket(**inppos, transaction_id=trans.pk)
                elif postype == "sell":
                    pos = sell_ticket(**inppos, transaction_id=trans.pk)
                else:  # noqa
                    raise FlowError(_("Type {} is not yet implemented").format(postype))
            except FlowError as e:
                position_feedback.append(
                    {
                        "success": False,
                        "message": e.message,
                        "type": e.type,
                        "missing_field": e.missing_field,
                        "bypass_price": e.bypass_price,
                    }
                )
                success = False
            else:
                feedback = {"success": True}
                if pos.preorder_position:
                    feedback["preorder_position"] = PreorderPositionSerializer(
                        pos.preorder_position
                    ).data
                position_feedback.append(feedback)
                pos.transaction = trans
                pos.save()

        response = {"success": success, "positions": position_feedback}

        if success:
            trans.print_receipt(do_open_drawer=True)
            response["id"] = trans.pk
            return response
        else:
            # Break out of atomic transaction so everything gets rolled back!
            raise ProcessException(response)

    @detail_route(methods=["POST"])
    def reverse(self, *args, **kwargs) -> Response:
        session = self.request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )
        try:
            new_id = reverse_transaction(kwargs.get("pk"), session)
            Transaction.objects.get(pk=new_id).print_receipt(do_open_drawer=False)
            return Response(
                {"success": True, "id": new_id}, status=status.HTTP_201_CREATED
            )
        except FlowError as e:
            return Response(
                {"success": False, "message": e.message},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProductViewSet(ReadOnlyModelViewSet):
    queryset = (
        Product.objects.prefetch_related("product_items", "product_items__item")
        .all()
        .order_by("id")
    )
    serializer_class = ProductSerializer


class ListConstraintViewSet(ReadOnlyModelViewSet):
    queryset = ListConstraint.objects.all().order_by("id")
    serializer_class = ListConstraintSerializer


class ListConstraintEntryViewSet(ReadOnlyModelViewSet):
    queryset = ListConstraintEntry.objects.all().order_by("id")
    serializer_class = ListConstraintEntrySerializer

    def get_queryset(self) -> QuerySet:
        queryset = ListConstraintEntry.objects.all().order_by("id")
        listid_param = self.request.query_params.get("listid", None)
        if listid_param is not None and listid_param.isdigit():
            queryset = queryset.filter(list_id=listid_param)
            search_param = self.request.query_params.get("search", None)
            if search_param is not None and len(search_param) >= 3:
                queryset = queryset.filter(
                    Q(name__icontains=search_param)
                    | Q(identifier__icontains=search_param)
                )
            elif search_param is not None:
                queryset = queryset.filter(identifier__iexact=search_param)
            else:
                queryset = queryset.none()
        else:
            queryset = queryset.none()
        return queryset


class CashdeskActionViewSet(ReadOnlyModelViewSet):
    """ Hacky class to use restframework capabilities without being RESTful.
    We don't expose a queryset, and use a random serializer.
    Allowed actions: open-drawer, reprint-receipt, request-resupply, signal-next, print-ping, pong
    """

    serializer_class = ListConstraintEntrySerializer
    queryset = Cashdesk.objects.none()

    @list_route(methods=["POST"], url_path="open-drawer")
    def open_drawer(self, request: HttpRequest) -> Response:
        session = request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )
        session.cashdesk.printer.open_drawer()
        return Response({"success": True})

    @list_route(methods=["GET"], url_path="current-time")
    def current_time(self, request: HttpRequest) -> Response:
        return Response(
            {
                "string": date_format(
                    now().astimezone(pytz.timezone(settings.TIME_ZONE)), "TIME_FORMAT"
                )
            }
        )

    @list_route(methods=["POST"], url_path="reprint-receipt")
    def reprint_receipt(self, request: HttpRequest) -> Response:
        session = request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )

        try:
            transaction = Transaction.objects.get(pk=request.data.get("transaction"))
            session.cashdesk.printer.print_receipt(transaction, do_open_drawer=False)
            return Response({"success": True})
        except Transaction.DoesNotExist:
            return Response(
                {"success": False, "error": "Transaction not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @list_route(methods=["POST"], url_path="request-resupply")
    def request_resupply(self, request: HttpRequest) -> Response:
        session = request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )

        session.request_resupply()
        return Response({"success": True})

    @list_route(methods=["POST"], url_path="signal-next")
    def signal_next(self, request: HttpRequest) -> Response:
        session = request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )

        session.cashdesk.signal_next()
        return Response({"success": True})

    @list_route(methods=["POST"], url_path="print-ping")
    def print_ping(self, request: HttpRequest) -> Response:
        session = request.user.get_current_session()
        if not session:  # noqa
            raise RuntimeError(
                "This should never happen because the auth layer should handle this."
            )

        generate_ping(session.cashdesk)
        return Response({"success": True})

    @list_route(methods=["POST"], url_path="pong")
    def pong(self, request: HttpRequest) -> Response:
        try:
            ping = Ping.objects.get(secret=request.data.get("pong"))
            ping.pong()
        except Ping.DoesNotExist:
            pass

        return Response({"success": True})

    @list_route(methods=["POST"], url_path="supply")
    def supply(self, request: HttpRequest) -> Response:
        try:
            isp = ItemSupplyPack.objects.get(
                identifier=request.data.get("identifier").strip()
            )
        except ItemSupplyPack.DoesNotExist:
            return Response(
                {"success": False, "message": _("Unknown supply pack barcode.")}
            )

        if isp.state == "troubleshooter":
            with transaction.atomic():
                isp.state = "used"
                isp.save()
                isp.logs.create(
                    user=request.user,
                    new_state="used",
                    item_movement=ItemMovement.objects.create(
                        item=isp.item,
                        session=request.user.get_current_session(),
                        amount=isp.amount,
                        backoffice_user=request.user,
                    ),
                )
            request.user.get_current_session().cashdesk.printer.open_drawer()
            return Response({"success": True})
        elif isp.state == "backoffice":
            return Response(
                {
                    "success": False,
                    "message": _(
                        "This supply pack has not been transferred to the troubleshooter yet, you cannot use it."
                    ),
                }
            )
        elif isp.state == "dissolved":
            return Response(
                {
                    "success": False,
                    "message": _("This supply pack does not exist any more."),
                }
            )
        elif isp.state == "used":
            return Response(
                {
                    "success": False,
                    "message": _("This supply pack has already been used."),
                }
            )


class PingViewSet(ReadOnlyModelViewSet):
    queryset = Ping.objects.all().order_by("-id")
    serializer_class = PingSerializer
    permission_classes = []

    def get_queryset(self) -> QuerySet:
        queryset = self.queryset
        ponged_param = self.request.GET.get("ponged", None)
        synced_param = self.request.GET.get("synced", None)
        if ponged_param is not None:
            queryset = queryset.filter(
                ponged__isnull=(ponged_param not in ("True", "true", "1"))
            )
        if synced_param:
            queryset = queryset.filter(synced=(synced_param in ("True", "true", "1")))
        return queryset

    @detail_route(methods=["POST"])
    def mark_synced(self, *args, **kwargs) -> Response:
        obj = self.get_object()
        obj.synced = True
        obj.save()
        return Response(PingSerializer(obj).data)
