from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from api.utils.app_response import AppResponse
from django.db import connection
from datetime import datetime, timedelta
from calendar import monthrange
import pytz

class AdminDashboardViewSet(viewsets.ViewSet):
    """
    ViewSet for Admin Dashboard
    """
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='stats')
    def dashboard_stats(self, request):
        """Get dashboard statistics using raw SQL queries for performance"""

        try:
            # Get current date/time in Philippines timezone
            ph_tz = pytz.timezone('Asia/Manila')
            now = datetime.now(ph_tz)

            # This month dates
            first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_this_month = now.replace(day=monthrange(now.year, now.month)[1], hour=23, minute=59, second=59)

            # This year dates
            first_day_this_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_this_year = now.replace(month=12, day=31, hour=23, minute=59, second=59)

            # Last year dates
            first_day_last_year = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day_last_year = now.replace(year=now.year - 1, month=12, day=31, hour=23, minute=59, second=59)

            stats = {}

            with connection.cursor() as cursor:
                # 1. Active Riders (application_status=1, status=1, deleted_at IS NULL)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM riders
                    WHERE application_status = 1
                      AND status = 1
                      AND deleted_at IS NULL
                """)
                stats['active_riders'] = cursor.fetchone()[0]

                # 2. Total Customers (deleted_at IS NULL)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM customer
                    WHERE deleted_at IS NULL
                """)
                stats['total_customers'] = cursor.fetchone()[0]

                # 3. New Rider Signups (This Month)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM riders
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND deleted_at IS NULL
                """, [first_day_this_month, last_day_this_month])
                stats['new_rider_signups_this_month'] = cursor.fetchone()[0]

                # 4. New Customer Signups (This Month)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM customer
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND deleted_at IS NULL
                """, [first_day_this_month, last_day_this_month])
                stats['new_customer_signups_this_month'] = cursor.fetchone()[0]

                # 5. Monthly Bookings (Per month for current year)
                cursor.execute("""
                    SELECT
                        EXTRACT(MONTH FROM created_at) as month_num,
                        COUNT(*) as booking_count
                    FROM booking
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND deleted_at IS NULL
                    GROUP BY EXTRACT(MONTH FROM created_at)
                    ORDER BY month_num
                """, [first_day_this_year, last_day_this_year])

                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

                monthly_bookings = []
                for row in cursor.fetchall():
                    month_num = int(row[0])
                    booking_count = row[1]
                    monthly_bookings.append({
                        'month': month_names[month_num - 1],
                        'count': booking_count
                    })
                stats['monthly_bookings'] = monthly_bookings

                # 6. Rider Location Breakdown (Grouped by Province/Region with percentages)
                # First, get total count of riders with locations
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM riders
                    WHERE current_location IS NOT NULL
                      AND current_location != ''
                      AND deleted_at IS NULL
                """)
                total_riders_with_location = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT current_location, COUNT(*) as rider_count
                    FROM riders
                    WHERE current_location IS NOT NULL
                      AND current_location != ''
                      AND deleted_at IS NULL
                    GROUP BY current_location
                    ORDER BY rider_count DESC
                """)

                def extract_province_or_region(location_string):
                    """Extract province/region from location string"""
                    if not location_string:
                        return "Unknown"

                    parts = [p.strip() for p in location_string.split(',')]

                    # Format: "street, barangay, city, province/state"
                    # The last part is usually the province/region
                    if len(parts) >= 1:
                        province_region = parts[-1].strip()

                        # Clean up common prefixes/suffixes
                        if province_region.startswith('Province of '):
                            province_region = province_region.replace('Province of ', '')
                        if province_region.endswith(' Province'):
                            province_region = province_region.replace(' Province', '')

                        return province_region

                    return location_string

                # Group by province/region
                province_counts = {}
                for row in cursor.fetchall():
                    full_location = row[0]
                    count = row[1]
                    province_region = extract_province_or_region(full_location)

                    if province_region in province_counts:
                        province_counts[province_region] += count
                    else:
                        province_counts[province_region] = count

                # Convert to sorted list and calculate percentages
                rider_locations = []
                sorted_provinces = sorted(province_counts.items(), key=lambda x: x[1], reverse=True)

                for province_region, count in sorted_provinces[:10]:  # Top 10
                    percentage = (count / total_riders_with_location * 100) if total_riders_with_location > 0 else 0
                    rider_locations.append({
                        'location': province_region,
                        'count': count,
                        'percentage': round(percentage, 1)
                    })
                stats['rider_location_breakdown'] = rider_locations

                # 7. Total Users (Customers + Riders)
                cursor.execute("""
                    SELECT (
                        (SELECT COUNT(*) FROM customer WHERE deleted_at IS NULL) +
                        (SELECT COUNT(*) FROM riders WHERE deleted_at IS NULL)
                    )
                """)
                stats['total_users'] = cursor.fetchone()[0]

                # 7.1 Total Users This Year
                cursor.execute("""
                    SELECT (
                        (SELECT COUNT(*) FROM customer WHERE created_at >= %s AND created_at <= %s AND deleted_at IS NULL) +
                        (SELECT COUNT(*) FROM riders WHERE created_at >= %s AND created_at <= %s AND deleted_at IS NULL)
                    )
                """, [first_day_this_year, last_day_this_year, first_day_this_year, last_day_this_year])
                stats['total_users_this_year'] = cursor.fetchone()[0]

                # 7.2 Total Users Last Year
                cursor.execute("""
                    SELECT (
                        (SELECT COUNT(*) FROM customer WHERE created_at >= %s AND created_at <= %s AND deleted_at IS NULL) +
                        (SELECT COUNT(*) FROM riders WHERE created_at >= %s AND created_at <= %s AND deleted_at IS NULL)
                    )
                """, [first_day_last_year, last_day_last_year, first_day_last_year, last_day_last_year])
                stats['total_users_last_year'] = cursor.fetchone()[0]

                # 8. Total Projects - Not applicable, set to 0
                stats['total_projects'] = 0

                # 8.1 Total Projects This Year - Not applicable, set to 0
                stats['total_projects_this_year'] = 0

                # 8.2 Total Projects Last Year - Not applicable, set to 0
                stats['total_projects_last_year'] = 0

                # 9. Operating Status - Set to "Active"
                stats['operating_status'] = "Active"

                # 10. This Year - Total Bookings This Year
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM booking
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND deleted_at IS NULL
                """, [first_day_this_year, last_day_this_year])
                stats['this_year_bookings'] = cursor.fetchone()[0]

                # 11. Last Year - Total Bookings Last Year
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM booking
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND deleted_at IS NULL
                """, [first_day_last_year, last_day_last_year])
                stats['last_year_bookings'] = cursor.fetchone()[0]

                # Additional useful stats
                # 12. Total Revenue This Month (from booking payments)
                cursor.execute("""
                    SELECT COALESCE(SUM(total_amount), 0)
                    FROM booking_payment
                    WHERE created_at >= %s
                      AND created_at <= %s
                      AND deleted_at IS NULL
                      AND status = 1
                """, [first_day_this_month, last_day_this_month])
                stats['monthly_revenue'] = cursor.fetchone()[0]

                # 13. Online Riders (is_online=1)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM riders
                    WHERE is_online = 1
                      AND deleted_at IS NULL
                """)
                stats['online_riders'] = cursor.fetchone()[0]

                # 14. Available Riders (is_available=1)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM riders
                    WHERE is_available = 1
                      AND deleted_at IS NULL
                """)
                stats['available_riders'] = cursor.fetchone()[0]

                # 15. Completed Bookings (status=4)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM booking
                    WHERE status = 4
                      AND deleted_at IS NULL
                """)
                stats['completed_bookings'] = cursor.fetchone()[0]

                # 16. Pending Bookings (status=0)
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM booking
                    WHERE status = 0
                      AND deleted_at IS NULL
                """)
                stats['pending_bookings'] = cursor.fetchone()[0]

            return AppResponse.send_success(
                data=stats,
                message="Dashboard statistics retrieved successfully"
            )

        except Exception as e:
            return AppResponse.send_error(
                message=str(e),
                code=500
            )
