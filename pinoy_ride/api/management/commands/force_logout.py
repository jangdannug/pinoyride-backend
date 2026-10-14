"""Force-logout riders/customers by phone number.

Usage:
    python manage.py force_logout 639170000102 9170000201 [--dry-run]

Matches 63XXXXXXXXXX, 0XXXXXXXXXX and XXXXXXXXXX forms of the same number.
Clears: is_login -> 0, firebase_token -> NULL (both), session_id -> NULL
(customer), is_online -> 0 (rider). Soft-deleted rows are skipped.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models.customer_model import Customer
from api.models.rider_model import Rider


def variants(raw):
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("63"):
        core = digits[2:]
    elif digits.startswith("0"):
        core = digits[1:]
    else:
        core = digits
    if not core:
        return []
    return [core, "0" + core, "63" + core, "+63" + core]


class Command(BaseCommand):
    help = "Force-logout riders and customers by phone number."

    def add_arguments(self, parser):
        parser.add_argument("numbers", nargs="+")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, numbers, dry_run, **opts):
        tag = "[DRY RUN] " if dry_run else ""
        for raw in numbers:
            forms = variants(raw)
            self.stdout.write(f"\n{tag}{raw} -> matching {forms}")
            if not forms:
                self.stdout.write("  invalid number, skipped")
                continue
            riders = Rider.objects.filter(mobile_no__in=forms, deleted_at__isnull=True)
            customers = Customer.objects.filter(mobile__in=forms, deleted_at__isnull=True)
            if not riders.exists() and not customers.exists():
                self.stdout.write("  no rider or customer found")
                continue
            with transaction.atomic():
                for r in riders:
                    before = f"is_login={r.is_login} is_online={r.is_online} firebase_token={'set' if r.firebase_token else 'empty'}"
                    self.stdout.write(f"  rider id={r.id} phone={r.mobile_no}: {before}")
                    if not dry_run:
                        Rider.objects.filter(pk=r.pk).update(is_login=0, is_online=0, firebase_token=None)
                        self.stdout.write("    cleared is_login, is_online, firebase_token")
                for c in customers:
                    before = (f"is_login={c.is_login} firebase_token={'set' if c.firebase_token else 'empty'} "
                              f"session_id={'set' if c.session_id else 'empty'}")
                    self.stdout.write(f"  customer id={c.id} phone={c.mobile}: {before}")
                    if not dry_run:
                        Customer.objects.filter(pk=c.pk).update(is_login=0, firebase_token=None, session_id=None)
                        self.stdout.write("    cleared is_login, firebase_token, session_id")
        if dry_run:
            self.stdout.write("\nDry run: nothing changed.")
