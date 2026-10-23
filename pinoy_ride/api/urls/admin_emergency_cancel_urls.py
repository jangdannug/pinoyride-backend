from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AdminEmergencyCancelViewSet


router = DefaultRouter()
router.register(r'', AdminEmergencyCancelViewSet, basename='Admin Emergency Cancel')

urlpatterns = [
    path('', include(router.urls)),
]
