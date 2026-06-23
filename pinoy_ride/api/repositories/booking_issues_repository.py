from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Concat
from api.models.booking_issues_model import BookingIssues
from django.db import transaction
from api.serializers import (
    BookingSerializer
)
from geopy.distance import geodesic
from api.utils.app_logger import app_logger

class BookingIssuesRepository:

    @staticmethod
    def get_all_complaints(page_number=1, page_size=10, search_query=None, filters={}, sort_by="-created_at"):
        """Get all complaints with pagination"""

        # Start with all non-deleted booking issues
        complaints = BookingIssues.objects.all().order_by(sort_by)

        # Apply rider filter if provided
        if filters.get("rider_id"):
            complaints = complaints.filter(booking__rider_id=filters.get("rider_id"))

        # Apply search filter if provided
        if search_query:
            complaints = complaints.filter(
                Q(issue_txt__icontains=search_query)
                # | Q(booking__booking_code__icontains=search_query)
            )

        # Apply additional filters
        if filters.get("status"):
            complaints = complaints.filter(status=filters.get("status"))
        if filters.get("user_type"):
            complaints = complaints.filter(user_type=filters.get("user_type"))

        # Paginate
        paginator = Paginator(complaints, page_size)
        page_obj = paginator.get_page(page_number)

        # Build response data
        complaints_data = []
        for complaint in page_obj:
            complaints_data.append({
                'id': complaint.id,
                'booking_id': complaint.booking.id if complaint.booking else None,
                'issue_txt': complaint.issue_txt,
                'status': complaint.status,
                'user_type': complaint.user_type,
                'reported_by': complaint.reported_by,
                'created_at': complaint.created_at.isoformat() if complaint.created_at else None,
                'updated_at': complaint.updated_at.isoformat() if complaint.updated_at else None,
            })

        return {
            'data': complaints_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'items_per_page': page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        }

    @staticmethod
    @transaction.atomic
    def create(booking_instance, booking_issues):
        new_booking_issues = BookingIssues.objects.create(
            booking=booking_instance,
            issue_txt=booking_issues.get("issue", ""),
            user_type=booking_issues.get("user_type", ""),
            reported_by=booking_issues.get("reported_by", ""),
        )

        new_booking_issues.save()
        return new_booking_issues