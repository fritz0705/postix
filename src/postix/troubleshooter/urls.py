from django.conf.urls import url

from . import views

app_name = "troubleshooter"
urlpatterns = [
    url("^login/$", views.LoginView.as_view(), name="login"),
    url("^logout/$", views.logout_view, name="logout"),
    url("^ping/$", views.PingView.as_view(), name="ping"),
    url("^preorders/$", views.PreorderListView.as_view(), name="preorder-list"),
    url(
        "^preorders/information/$",
        views.PreorderInformationListView.as_view(),
        name="preorder-information-list",
    ),
    url(
        "^preorders/(?P<pk>[0-9]+)/$",
        views.PreorderDetailView.as_view(),
        name="preorder-detail",
    ),
    url(
        "^constraints/(?P<pk>[0-9]+)/$",
        views.ListConstraintDetailView.as_view(),
        name="constraint-detail",
    ),
    url(
        "^constraints/$", views.ListConstraintListView.as_view(), name="constraint-list"
    ),
    url(
        "^information/(?P<pk>[0-9]+)/$",
        views.InformationDetailView.as_view(),
        name="information-detail",
    ),
    url("^information/$", views.InformationListView.as_view(), name="information-list"),
    url(
        "^transactions/(?P<pk>[0-9]+)/reprint/$",
        views.transaction_reprint,
        name="transaction-reprint",
    ),
    url(
        "^transactions/(?P<pk>[0-9]+)/invoice/$",
        views.transaction_invoice,
        name="transaction-invoice",
    ),
    url(
        "^transactions/(?P<pk>[0-9]+)/$",
        views.TransactionDetailView.as_view(),
        name="transaction-detail",
    ),
    url(
        "^transactions/$", views.TransactionListView.as_view(), name="transaction-list"
    ),
    url(
        "^session/(?P<pk>[0-9]+)/resupply/$",
        views.confirm_resupply,
        name="confirm-resupply",
    ),
    url("^session/check_requests$", views.check_requests, name="check-requests"),
    url("^$", views.main_view, name="main"),
]
