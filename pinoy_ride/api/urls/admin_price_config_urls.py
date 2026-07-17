from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import PriceConfigViewSet

router = DefaultRouter()
router.register(r'', PriceConfigViewSet, basename='price-config')

urlpatterns = [
    path('', include(router.urls)),
]
