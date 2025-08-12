from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AdminRiderViewSet


router = DefaultRouter()
router.register(r'',AdminRiderViewSet, basename='Admin Promo' )

urlpatterns = [
    path('', include(router.urls)),
]