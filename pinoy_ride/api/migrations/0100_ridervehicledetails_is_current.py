# Generated manually for rider current vehicle selection

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0099_message_image_msg'),
    ]

    operations = [
        migrations.AddField(
            model_name='ridervehicledetails',
            name='is_current',
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name='ridervehicledetails',
            constraint=models.UniqueConstraint(
                condition=models.Q(is_current=True, deleted_at__isnull=True),
                fields=('rider',),
                name='one_current_vehicle_per_rider',
            ),
        ),
    ]
