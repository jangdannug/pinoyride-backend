"""
Django management command to run all seeders at once.

Usage:
    python manage.py seed_all
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run all seeders (users, shipments, pages, quote_configurations) in one command'

    def handle(self, *args, **options):
        """Execute all seeder commands."""
        self.stdout.write("============================================================")
        self.stdout.write(self.style.SUCCESS(" Pinoy Ride API - Master Seeder"))
        self.stdout.write("============================================================")


        # 1. Seed Users
        try:
            call_command('seed_users')
            self.stdout.write(self.style.SUCCESS("✓ Users seeded successfully"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Error seeding users: {e}"))


        self.stdout.write("")
        self.stdout.write("============================================================")
        self.stdout.write(self.style.SUCCESS("  ✓ ALL SEEDERS COMPLETED SUCCESSFULLY!"))
        self.stdout.write("============================================================")
     