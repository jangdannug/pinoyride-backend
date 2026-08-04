# syntax=docker/dockerfile:1

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DJANGO_SETTINGS_MODULE=pinoy_ride.settings

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/pinoy_ride/media /app/pinoy_ride/api/logs \
    && chmod +x /app/start.sh

EXPOSE 8000

CMD ["sh", "-c", "cd /app/pinoy_ride && python manage.py migrate --noinput && gunicorn pinoy_ride.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --timeout 120"]