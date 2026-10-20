# Hand-written 2026-10-19: rider early Advance Booking reminder (1 hour before pickup).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0105_booking_contact_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='early_reminder_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
