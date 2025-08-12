from django.urls import path, include

urlpatterns = [
    path('test_api/', include('api.urls.test_urls')),

    path('riders/', include('api.urls.rider_urls')),
    path('customers/', include('api.urls.customer_urls')),
    path('otp/', include('api.urls.otp_urls')),

    path('admin/', include('api.urls.auth_urls')),
    path('admin/rider/', include('api.urls.admin_rider_urls')),
    path('admin/promo/', include('api.urls.admin_promo_urls')),
    path('admin/price/', include('api.urls.admin_price_urls')),
]