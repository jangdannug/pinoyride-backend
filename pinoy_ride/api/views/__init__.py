from .test_view import TestViewSet
from .rider_view import RiderViewSet
from .auth_view import AuthViewSet
from .customer_view import CustomerViewSet
from .otp_view import OtpViewSet
from .booking_view import BookingViewSet
from .qrph_view import QrphViewSet
from .ekyc_view import EkycViewSet
from .cash_out_view import CashOutViewSet

# Views for Payment Gateway API
from .internal_request_view import InternalRequestViewSet
from .internal_response_view import InternalResponseViewSet
from .internal_backend_view import InternalBackendViewSet

from .admin_promo_view import AdminPromoViewSet
from .admin_price_view import AdminPriceViewSet
from .price_config_view import PriceConfigViewSet
from .admin_rider_view import AdminRiderViewSet
from .admin_customer_view import AdminCustomerViewSet
from .admin_task_view import AdminTaskViewSet
from .admin_dashboard_view import AdminDashboardViewSet
from .promo_view import PromoViewSet
from .message_view import MessageViewSet