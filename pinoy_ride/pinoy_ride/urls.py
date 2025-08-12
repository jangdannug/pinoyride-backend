from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from django.conf import settings
from django.conf.urls.static import static

schema_view = SpectacularAPIView.as_view()


urlpatterns = [
    path('api/', include('api.urls.base_urls')), 
]



if settings.ENV != 'production':
    urlpatterns += [
        path('schema/', SpectacularAPIView.as_view(), name='schema'),  # Endpoint for the schema
        path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),  # Swagger UI
        path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  # Redoc UI
    ]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)