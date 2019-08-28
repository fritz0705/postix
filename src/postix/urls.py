from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from django.views.i18n import JavaScriptCatalog

admin.autodiscover()

js_info_dict = {"packages": ()}

urlpatterns = [
    url(r"^jsi18n/$", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("admin/", admin.site.urls),
    url(r"^api/", include("postix.api.urls", namespace="api")),
    url(r"^backoffice/", include("postix.backoffice.urls", namespace="backoffice")),
    url(
        r"^troubleshooter/",
        include("postix.troubleshooter.urls", namespace="troubleshooter"),
    ),
    url(r"", include("postix.desk.urls", namespace="desk")),
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns.append(url(r"^__debug__/", include(debug_toolbar.urls)))
    except ImportError:
        pass
