from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AdminTaskViewSet


router = DefaultRouter()
router.register(r'',AdminTaskViewSet, basename='Admin Tasks' )

urlpatterns = [
    path('', include(router.urls)),
]