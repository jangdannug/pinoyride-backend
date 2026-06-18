from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import PromoViewSet

router = DefaultRouter()
router.register(r'', PromoViewSet, basename='Promo')

urlpatterns = [
    path('', include(router.urls)),
]
