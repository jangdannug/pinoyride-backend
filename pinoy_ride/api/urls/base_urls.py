from django.urls import path, include

urlpatterns = [
    path('test_api/', include('api.urls.test_urls')),

    path('riders/', include('api.urls.rider_urls')),
    path('customers/', include('api.urls.customer_urls')),
    path('otp/', include('api.urls.otp_urls')),
    path('booking/', include('api.urls.booking_urls')),
    path('qrph/', include('api.urls.qrph_urls')),
    path('ekyc/', include('api.urls.ekyc_urls')),
    path('cash_out/', include('api.urls.cash_out_urls')),
    path('promo/', include('api.urls.promo_urls')),

    # URL for payment gateway
    path('request/', include('api.urls.internal_request_urls')),
    path('response/', include('api.urls.internal_response_urls')),
    path('backend/', include('api.urls.internal_backend_urls')),

    path('admin/', include('api.urls.auth_urls')),
    path('admin/rider/', include('api.urls.admin_rider_urls')),
    path('admin/customer/', include('api.urls.admin_customer_urls')),
    path('admin/promo/', include('api.urls.admin_promo_urls')),
    path('admin/price/', include('api.urls.admin_price_urls')),
    path('admin/task/', include('api.urls.admin_task_urls')),
    path('admin/dashboard/', include('api.urls.admin_dashboard_urls')),
]