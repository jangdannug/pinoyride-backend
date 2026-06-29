from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import MessageViewSet


router = DefaultRouter()
router.register(r'', MessageViewSet, basename='Message')

urlpatterns = [
    path('', include(router.urls)),
]
