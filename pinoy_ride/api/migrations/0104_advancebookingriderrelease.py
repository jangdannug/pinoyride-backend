from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0103_booking_returned_to_pool_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdvanceBookingRiderRelease",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("released_at", models.DateTimeField(auto_now_add=True)),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rider_releases",
                        to="api.booking",
                    ),
                ),
                (
                    "rider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="advance_booking_releases",
                        to="api.rider",
                    ),
                ),
            ],
            options={
                "db_table": "advance_booking_rider_release",
            },
        ),
        migrations.AddIndex(
            model_name="advancebookingriderrelease",
            index=models.Index(fields=["rider_id", "released_at"], name="advance_boo_rider_i_6a8f2d_idx"),
        ),
        migrations.AddIndex(
            model_name="advancebookingriderrelease",
            index=models.Index(fields=["booking_id", "rider_id"], name="advance_boo_booking_91c4e1_idx"),
        ),
    ]
