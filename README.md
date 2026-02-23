# Pinoy Ride API

A ride-hailing platform API built for the Philippine market. Handles customer bookings, rider management, payments via QRPH national payment system, E-KYC verification, and wallet management.

## Tech Stack

- **Framework:** Django 5.1.4 + Django REST Framework
- **Language:** Python 3.11
- **Database:** PostgreSQL
- **Cache/Queue:** Redis (caching, Celery broker)
- **Storage:** AWS S3
- **Server:** Gunicorn (production)
- **Deployment:** Vercel

## Key Integrations

- **QRPH** - Philippine national payment system
- **TOP PH E-KYC** - Digital identity verification
- **iTextMo/Twilio** - SMS services
- **Cash Out API** - Rider withdrawal system

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- AWS S3 account (for file storage)

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd pinoy-ride-api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the appropriate environment file:

```bash
# For development
cp .env.dev .env

# For production
cp .env.production .env
```

Key environment variables to configure:

```bash
ENV=development                    # or 'production'
DEBUG=True                         # Set False in production
DATABASE_URL=postgresql://...      # PostgreSQL connection
SECRET_KEY=your-secret-key
CUSTOM_API_KEY=your-api-key
CALLBACK_API_KEY=your-webhook-key
JWT_EXPIRES_IN_MINUTES=30
JWT_REFRESH_EXPIRES_IN_DAYS=7
```

### 3. Database Setup

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser

```bash
python manage.py createsuperuser
```

### 5. Run Development Server

```bash
python manage.py runserver 8001
```

The API will be available at `http://localhost:8001`

## API Documentation

When running in non-production mode, API documentation is available:

- **Swagger UI:** `http://localhost:8001/docs/`
- **ReDoc:** `http://localhost:8001/redoc/`
- **OpenAPI Schema:** `http://localhost:8001/schema/`

## API Endpoints

Base URL: `/api/`

### Public Routes
- `/api/test_api/` - Test endpoints
- `/api/otp/` - OTP authentication

### Customer Routes
- `/api/customers/` - Customer management
- `/api/booking/` - Booking operations

### Rider Routes
- `/api/riders/` - Rider management
- `/api/cash_out/` - Rider cash out

### Integration Routes
- `/api/qrph/` - QRPH payment integration
- `/api/ekyc/` - E-KYC verification

### Admin Routes
- `/api/admin/` - Admin authentication
- `/api/admin/rider/` - Admin rider management
- `/api/admin/customer/` - Admin customer management
- `/api/admin/promo/` - Promo management
- `/api/admin/price/` - Pricing management
- `/api/admin/task/` - Admin tasks

## Authentication

JWT-based authentication using `drf-simplejwt`:

- **Access Token Lifetime:** 30 minutes
- **Refresh Token Lifetime:** 7 days
- **Custom User Model:** `api.User`
- **Token Blacklisting:** Enabled after rotation

Include the access token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## API Keys

Main API routes require an `X-API-KEY` header:
```
X-API-KEY: <your-custom-api-key>
```

Callback webhooks require an `api-key` header:
```
api-key: <your-callback-api-key>
```

> **Note:** API key enforcement is disabled in development mode.

## Booking Status Flow

| Status | Value | Description |
|--------|-------|-------------|
| Pending | 0 | Booking created, awaiting rider |
| Accepted | 1 | Rider accepted the booking |
| Arrived | 2 | Rider arrived at pickup location |
| Started | 3 | Trip in progress |
| Completed | 4 | Trip completed |
| Cancelled | 9 | Booking cancelled/deleted |

## Architecture

The project follows a strict layered architecture:

```
Models (domain layer)
    ↓
Repositories (data access layer)
    ↓
Services (business logic layer)
    ↓
Views (API endpoints)
    ↓
Serializers (serialization/deserialization)
```

### Key Patterns

- **Soft Delete:** Most models use `SoftDeleteModel` - use `Model.objects` for active records, `Model.all_objects` to include deleted
- **Repository Pattern:** All database queries go through repositories
- **Service Layer:** Business logic wrapped in `@transaction.atomic`
- **Custom Exceptions:** Use `NotFoundError`, `ValidationError` from `api.utils.custom_error`

## Development

### Running Tests

```bash
python manage.py test
```

### Collecting Static Files

```bash
python manage.py collectstatic
```

### Logging

Logs are stored in `api/logs/` with daily rotation (format: `YYYY-MM-DD.log`).

```python
import logging
logger = logging.getLogger('myapp')
logger.info('message')
```

## Deployment

### Production with Gunicorn

```bash
gunicorn pinoy_ride.pinoy_ride.wsgi:application
```

### Using the Startup Script

```bash
./start_all.sh
```

### Vercel Deployment

The project is configured for Vercel deployment via `vercel.json` and `Procfile`.

**Configuration:**
- **WSGI Entry Point:** `pinoy_ride/pinoy_ride/wsgi.py`
- **Timezone:** `Asia/Manila` (Philippine time)
- **CORS Origins:**
  - `https://pinoy-ride.vercel.app` (production)
  - `http://localhost:3000`, `http://localhost:3001` (development)
  - `http://192.168.100.40:3000` (network testing)

## Database Indexes

The Booking model has indexed fields for optimized geolocation queries:

- `pickup_lat`, `pickup_long` - Pickup location
- `dropoff_lat`, `dropoff_long` - Dropoff location
- `status`, `customer_id`, `rider_id` - Query optimization

## Support

For issues, questions, or contributions, please refer to the project repository.
