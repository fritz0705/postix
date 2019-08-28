from django.conf.urls import url

from . import views

app_name = "backoffice"
urlpatterns = [
    url("^login/$", views.LoginView.as_view(), name="login"),
    url("^logout/$", views.logout_view, name="logout"),
    url("^switch-user/$", views.switch_user, name="switch-user"),
    url("^create_user/$", views.create_user_view, name="create-user"),
    url(
        "^users/reset_password/(?P<pk>[0-9]+)/$",
        views.ResetPasswordView.as_view(),
        name="reset-password",
    ),
    url("^users/$", views.UserListView.as_view(), name="user-list"),
    url("^session/new/$", views.NewSessionView.as_view(), name="new-session"),
    url(
        "^session/(?P<pk>[0-9]+)/end/$",
        views.EndSessionView.as_view(),
        name="end-session",
    ),
    url(
        "^session/(?P<pk>[0-9]+)/resupply/$",
        views.resupply_session,
        name="resupply-session",
    ),
    url("^session/(?P<pk>[0-9]+)/move/$", views.move_session, name="move-session"),
    url(
        "^session/(?P<pk>[0-9]+)/reverse/$",
        views.reverse_session_view,
        name="reverse-session",
    ),
    url(
        "^session/(?P<pk>[0-9]+)/$",
        views.SessionDetailView.as_view(),
        name="session-detail",
    ),
    url("^session/$", views.SessionListView.as_view(), name="session-list"),
    url("^reports/$", views.ReportListView.as_view(), name="report-list"),
    url("^records/$", views.RecordListView.as_view(), name="record-list"),
    url("^records/balance/$", views.RecordBalanceView.as_view(), name="record-balance"),
    url("^records/new/$", views.RecordCreateView.as_view(), name="new-record"),
    url("^records/blank/$", views.record_print, name="blank-record"),
    url(
        "^records/(?P<pk>[0-9]+)/$",
        views.RecordDetailView.as_view(),
        name="record-detail",
    ),
    url("^records/(?P<pk>[0-9]+)/print/$", views.record_print, name="record-print"),
    url(
        "^records/entity/$",
        views.RecordEntityListView.as_view(),
        name="record-entity-list",
    ),
    url(
        "^records/entity/new/$",
        views.RecordEntityCreateView.as_view(),
        name="new-record-entity",
    ),
    url(
        "^records/entity/(?P<pk>[0-9]+)/$",
        views.RecordEntityDetailView.as_view(),
        name="record-entity-detail",
    ),
    url(
        "^records/entity/(?P<pk>[0-9]+)/delete/$",
        views.RecordEntityDeleteView.as_view(),
        name="record-entity-delete",
    ),
    url("^assets/$", views.AssetListView.as_view(), name="asset-list"),
    url("^assets/new/$", views.AssetCreateView.as_view(), name="new-asset"),
    url(
        "^assets/(?P<pk>[0-9]+)/$", views.AssetUpdateView.as_view(), name="asset-detail"
    ),
    url("^assets/move/$", views.AssetMoveView.as_view(), name="move-asset"),
    url("^assets/history/$", views.AssetHistoryView.as_view(), name="history-asset"),
    url("^supplies/$", views.SupplyListView.as_view(), name="supply-list"),
    url("^supplies/create/$", views.SupplyCreateView.as_view(), name="supply-create"),
    url("^supplies/out/$", views.SupplyMoveOutView.as_view(), name="supply-out"),
    url("^supplies/in/$", views.SupplyMoveInView.as_view(), name="supply-in"),
    url("^supplies/away/$", views.SupplyMoveAwayView.as_view(), name="supply-away"),
    # These are called 'wizard' cause they're only for wizards (erm, superusers)
    url("^wizard/users/$", views.WizardUsersView.as_view(), name="wizard-users"),
    url(
        "^wizard/settings/$", views.WizardSettingsView.as_view(), name="wizard-settings"
    ),
    url(
        "^wizard/settings/export$",
        views.WizardSettingsExportView.as_view(),
        name="wizard-settings-export",
    ),
    url(
        "^wizard/settings/import$",
        views.WizardSettingsImportView.as_view(),
        name="wizard-settings-import",
    ),
    url(
        "^wizard/cashdesks/$",
        views.WizardCashdesksView.as_view(),
        name="wizard-cashdesks",
    ),
    url(
        "^wizard/cashdesks/new$",
        views.WizardCashdeskCreateView.as_view(),
        name="wizard-cashdesk-create",
    ),
    url(
        "^wizard/cashdesks/(?P<pk>[0-9]+)/$",
        views.WizardCashdeskEditView.as_view(),
        name="wizard-cashdesk-edit",
    ),
    url(
        "^wizard/import/$", views.WizardPretixImportView.as_view(), name="wizard-import"
    ),
    url(
        "^wizard/items/$", views.WizardItemListView.as_view(), name="wizard-items-list"
    ),
    url(
        "^wizard/items/new$",
        views.WizardItemCreateView.as_view(),
        name="wizard-items-create",
    ),
    url(
        "^wizard/items/(?P<pk>[0-9]+)/$",
        views.WizardItemEditView.as_view(),
        name="wizard-items-edit",
    ),
    url("^$", views.MainView.as_view(), name="main"),
]
