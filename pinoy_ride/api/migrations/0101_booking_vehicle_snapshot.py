# Generated manually for booking vehicle snapshot at accept

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0100_ridervehicledetails_is_current'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='rider_vehicle',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='api.ridervehicledetails',
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='vehicle_plate_number',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='vehicle_brand',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='vehicle_model',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='vehicle_color',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='vehicle_type',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
