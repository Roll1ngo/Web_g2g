# Generated by Django 5.1.2 on 2025-01-13 19:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0011_soldorders_charged_to_payment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymenthistory",
            name="amount",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="sellers",
            name="balance",
            field=models.IntegerField(default=0),
        ),
    ]
