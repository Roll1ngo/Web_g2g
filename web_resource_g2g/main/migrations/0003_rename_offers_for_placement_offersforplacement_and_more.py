# Generated by Django 5.1.2 on 2024-10-15 19:12

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0002_rename_offersforplacement_offers_for_placement"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="offers_for_placement",
            new_name="OffersForPlacement",
        ),
        migrations.AlterModelTable(
            name="offersforplacement",
            table="offers_for_placement",
        ),
    ]