# Generated by Django 5.1.2 on 2024-11-15 16:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0003_alter_offersforplacement_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="sellers",
            name="id_auth_user",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]