from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import CustomerViewSet
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register(r'', CustomerViewSet, basename='Customers')

urlpatterns = [
    path('', include(router.urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)