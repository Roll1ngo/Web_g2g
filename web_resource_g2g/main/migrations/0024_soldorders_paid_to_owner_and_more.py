# Generated by Django 5.1.2 on 2025-01-17 13:57

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0023_rename_paid_in_seller_salary_soldorders_paid_in_salary"),
    ]

    operations = [
        migrations.AddField(
            model_name="soldorders",
            name="paid_to_owner",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="soldorders",
            name="paid_to_technical",
            field=models.BooleanField(default=False),
        ),
    ]
