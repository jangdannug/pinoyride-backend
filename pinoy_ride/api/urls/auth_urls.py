from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import AuthViewSet


router = DefaultRouter()
router.register(r'', AuthViewSet, basename='Auth' )

urlpatterns = [
    path('', include(router.urls)),
]