from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AdminPriceViewSet


router = DefaultRouter()
router.register(r'',AdminPriceViewSet, basename='Admin Price' )

urlpatterns = [
    path('', include(router.urls)),
]