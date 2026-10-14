from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0102_booking_advance_eta'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='returned_to_pool_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
