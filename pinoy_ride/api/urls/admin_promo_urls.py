from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AdminPromoViewSet


router = DefaultRouter()
router.register(r'',AdminPromoViewSet, basename='Admin Promo' )

urlpatterns = [
    path('', include(router.urls)),
]