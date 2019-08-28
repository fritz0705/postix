import json

import pytest
from django.utils.crypto import get_random_string
from tests.factories import cashdesk_session_before_factory, user_factory

from postix.core.models import (
    Cashdesk,
    CashdeskSession,
    EventSettings,
    Item,
    Preorder,
    Product,
    ProductItem,
)
from postix.core.utils import round_decimal
from postix.core.utils.printing import DummyPrinter

DUMMY_PRINTER_COUNT = 0


class DummyPrinterTesting(DummyPrinter):
    def print_receipt(self, transaction, do_open_drawer=True) -> None:
        if super().print_receipt(transaction, do_open_drawer):
            global DUMMY_PRINTER_COUNT
            DUMMY_PRINTER_COUNT += 1


@pytest.mark.django_db
class TestFullEvent:
    def _setup_base(self):
        s = EventSettings.get_solo()
        s.initialized = True
        s.receipt_address = "Foo"
        s.save()

        self.session = cashdesk_session_before_factory(create_items=False)
        self.troubleshooter = user_factory(
            troubleshooter=True, superuser=False, password="123"
        )
        self.backoffice_user = user_factory(
            troubleshooter=True, backoffice=True, password="123"
        )
        self.cashier1 = user_factory(password="123")
        self.cashier2 = user_factory(password="123")

        self.item_full = Item.objects.create(
            name="Wristband red", description="Full pass", initial_stock=200
        )
        self.item_d1 = Item.objects.create(
            name="Wristband 1", description="Day 1", initial_stock=100
        )
        self.item_d2 = Item.objects.create(
            name="Wristband 2", description="Day 2", initial_stock=100
        )
        self.item_transport = Item.objects.create(
            name="Public transport",
            description="Public transport ticket",
            initial_stock=100,
            is_receipt=True,
        )
        self.prod_full = Product.objects.create(
            name="Full pass", price=100, tax_rate=19
        )
        self.prod_d1 = Product.objects.create(
            name="Day pass Day 1", price=35, tax_rate=19
        )
        self.prod_d2 = Product.objects.create(
            name="Day pass Day 2", price=35, tax_rate=19
        )
        self.prod_transport = Product.objects.create(
            name="Public transport", price=16.7, tax_rate=0
        )
        ProductItem.objects.create(
            product=self.prod_full, item=self.item_full, amount=1
        )
        ProductItem.objects.create(product=self.prod_d1, item=self.item_d1, amount=1)
        ProductItem.objects.create(product=self.prod_d2, item=self.item_d2, amount=1)
        ProductItem.objects.create(
            product=self.prod_transport, item=self.item_transport, amount=1
        )
        self.desk1 = Cashdesk.objects.create(name="Desk 1", ip_address="10.1.1.1")
        self.desk2 = Cashdesk.objects.create(name="Desk 2", ip_address="10.1.1.2")
        # ItemMovement.objects.create(session=session, item=item_1d, amount=10, backoffice_user=buser)

    def _simulate_preorder(self, client, product):
        secret = get_random_string(32)
        p = Preorder.objects.create(order_code=get_random_string(12), is_paid=True)
        p.positions.create(secret=secret, product=product)
        resp = client.post(
            "/api/transactions/",
            json.dumps(
                {
                    "positions": [
                        {
                            "product": product.pk,
                            "price": "0.00",
                            "secret": secret,
                            "type": "redeem",
                            "_title": product.name,
                        }
                    ]
                }
            ),
            content_type="application/json",
        )
        c = json.loads(resp.content.decode("utf-8"))
        assert c["success"]
        return c["id"]

    def _simulate_sale(self, client, product):
        resp = client.post(
            "/api/transactions/",
            json.dumps(
                {
                    "positions": [
                        {
                            "product": product.pk,
                            "price": str(product.price),
                            "type": "sell",
                            "_title": product.name,
                        }
                    ]
                }
            ),
            content_type="application/json",
        )
        c = json.loads(resp.content.decode("utf-8"))
        assert c["success"]
        return c["id"]

    def _simulate_reverse(self, client, tid):
        resp = client.post("/api/transactions/{}/reverse/".format(tid))
        c = json.loads(resp.content.decode("utf-8"))
        assert c["success"]
        return c["id"]

    def _simulate_session(
        self,
        full_sales,
        full_preorders,
        full_reversals,
        full_preorder_reversals,
        d1_sales,
        d1_preorders,
        d1_reversals,
        d1_preorder_reversals,
        d2_sales,
        d2_preorders,
        d2_reversals,
        d2_preorder_reversals,
        d_transport_sales,
        d_transport_preorders,
        d_transport_reversals,
        d_transport_preorder_reversals,
        user,
        cashdesk,
        client,
        buser,
    ):
        client.login(username=self.backoffice_user.username, password="123")
        client.post(
            "/backoffice/session/new/",
            {
                "session-cashdesk": cashdesk.pk,
                "session-user": user.username,
                "session-backoffice_user": buser.username,
                "session-cash_before": "300.00",
                "items-TOTAL_FORMS": "3",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": self.item_full.pk,
                "items-0-amount": "100",
                "items-1-item": self.item_d1.pk,
                "items-1-amount": "50",
                "items-2-item": self.item_d2.pk,
                "items-2-amount": "50",
            },
            follow=True,
        )
        session = (
            CashdeskSession.objects.filter(user=user, cashdesk=cashdesk)
            .order_by("id")
            .last()
        )
        assert session is not None
        client.login(username=self.cashier1.username, password="123")

        for i in range(full_sales):
            tid = self._simulate_sale(client, self.prod_full)
            if i < full_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == full_sales + full_reversals
        old_count = DUMMY_PRINTER_COUNT

        for i in range(d1_sales):
            tid = self._simulate_sale(client, self.prod_d1)
            if i < d1_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count + d1_sales + d1_reversals
        old_count = DUMMY_PRINTER_COUNT

        for i in range(d2_sales):
            tid = self._simulate_sale(client, self.prod_d2)
            if i < d2_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count + d2_sales + d2_reversals
        old_count = DUMMY_PRINTER_COUNT

        for i in range(d_transport_sales):
            tid = self._simulate_sale(client, self.prod_transport)
            if i < d_transport_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count

        for i in range(full_preorders):
            tid = self._simulate_preorder(client, self.prod_full)
            if i < full_preorder_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count

        for i in range(d1_preorders):
            tid = self._simulate_preorder(client, self.prod_d1)
            if i < d1_preorder_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count

        for i in range(d2_preorders):
            tid = self._simulate_preorder(client, self.prod_d2)
            if i < d2_preorder_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count

        for i in range(d_transport_preorders):
            tid = self._simulate_preorder(client, self.prod_transport)
            if i < d_transport_preorder_reversals:
                self._simulate_reverse(client, tid)
        assert DUMMY_PRINTER_COUNT == old_count

        total_cash = round_decimal(
            ((d1_sales - d1_reversals) * self.prod_d1.price)
            + ((d2_sales - d2_reversals) * self.prod_d2.price)
            + ((d_transport_sales - d_transport_reversals) * self.prod_transport.price)
            + ((full_sales - full_reversals) * self.prod_full.price)
        )

        client.login(username=self.backoffice_user.username, password="123")
        client.post(
            "/backoffice/session/{}/end/".format(session.pk),
            {
                "session-cashdesk": cashdesk.pk,
                "session-user": user.username,
                "session-backoffice_user": buser.username,
                "session-cash_before": total_cash,
                "items-TOTAL_FORMS": "3",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
                "items-0-item": self.item_full.pk,
                "items-0-amount": 50
                - full_sales
                + full_reversals
                - full_preorders
                + full_preorder_reversals,
                "items-1-item": self.item_d1.pk,
                "items-1-amount": 50
                - d1_sales
                + d1_reversals
                - d1_preorders
                + d1_preorder_reversals,
                "items-2-item": self.item_d2.pk,
                "items-2-amount": 50
                - d2_sales
                + d2_reversals
                - d2_preorders
                + d2_preorder_reversals,
            },
            follow=True,
        )
        session.refresh_from_db()
        assert session.end

        def keyfunc(d):
            return d["value_single"], d["product"].pk

        sales = [
            {
                "value_total": round_decimal(
                    self.prod_full.price * (full_sales - full_reversals)
                ),
                "sales": full_sales,
                "presales": 0,
                "reversals": full_reversals,
                "value_single": self.prod_full.price,
                "product": self.prod_full,
            },
            {
                "value_total": round_decimal(
                    self.prod_d1.price * (d1_sales - d1_reversals)
                ),
                "sales": d1_sales,
                "presales": 0,
                "reversals": d1_reversals,
                "value_single": self.prod_d1.price,
                "product": self.prod_d1,
            },
            {
                "value_total": round_decimal(
                    self.prod_d2.price * (d2_sales - d2_reversals)
                ),
                "sales": d2_sales,
                "presales": 0,
                "reversals": d2_reversals,
                "value_single": self.prod_d2.price,
                "product": self.prod_d2,
            },
            {
                "value_total": 0,
                "sales": 0,
                "presales": full_preorders,
                "reversals": full_preorder_reversals,
                "value_single": 0,
                "product": self.prod_full,
            },
            {
                "value_total": 0,
                "sales": 0,
                "presales": d1_preorders,
                "reversals": d1_preorder_reversals,
                "value_single": 0,
                "product": self.prod_d1,
            },
            {
                "value_total": 0,
                "sales": 0,
                "presales": d2_preorders,
                "reversals": d2_preorder_reversals,
                "value_single": 0,
                "product": self.prod_d2,
            },
            {
                "value_total": 0,
                "sales": 0,
                "presales": d_transport_preorders,
                "reversals": d_transport_preorder_reversals,
                "value_single": 0,
                "product": self.prod_transport,
            },
            {
                "value_total": round_decimal(
                    self.prod_transport.price
                    * (d_transport_sales - d_transport_reversals)
                ),
                "sales": d_transport_sales,
                "presales": 0,
                "reversals": d_transport_reversals,
                "value_single": self.prod_transport.price,
                "product": self.prod_transport,
            },
        ]

        assert session.get_cash_transaction_total() == total_cash
        assert sorted(session.get_product_sales(), key=keyfunc) == sorted(
            sales, key=keyfunc
        )

    def test_full(self, client, monkeypatch):
        monkeypatch.setattr(
            "postix.core.utils.printing.DummyPrinter", DummyPrinterTesting
        )
        monkeypatch.setattr(
            "postix.core.models.cashdesk.DummyPrinter", DummyPrinterTesting
        )
        self._setup_base()
        self._simulate_session(
            full_sales=20,
            full_preorders=60,
            full_reversals=3,
            full_preorder_reversals=2,
            d1_sales=5,
            d1_preorders=10,
            d1_reversals=0,
            d1_preorder_reversals=1,
            d2_sales=20,
            d2_preorders=30,
            d2_reversals=3,
            d2_preorder_reversals=4,
            d_transport_sales=5,
            d_transport_preorders=3,
            d_transport_reversals=1,
            d_transport_preorder_reversals=1,
            user=self.cashier1,
            cashdesk=self.desk1,
            client=client,
            buser=self.backoffice_user,
        )
