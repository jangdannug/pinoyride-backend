from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AdminDashboardViewSet

router = DefaultRouter()
router.register(r'', AdminDashboardViewSet, basename='Admin Dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
