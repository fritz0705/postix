from django.conf.urls import include, url
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"preorders", views.PreorderViewSet)
router.register(r"preorderpositions", views.PreorderPositionViewSet)
router.register(r"transactions", views.TransactionViewSet)
router.register(r"listconstraints", views.ListConstraintViewSet)
router.register(r"listconstraintentries", views.ListConstraintEntryViewSet)
router.register(r"products", views.ProductViewSet)
router.register(r"cashdesk", views.CashdeskActionViewSet)
router.register(r"pings", views.PingViewSet)

app_name = "api"
urlpatterns = [url(r"", include(router.urls))]
