from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import TestViewSet


router = DefaultRouter()
router.register(r'', TestViewSet)

urlpatterns = [
    path('', include(router.urls)),
]