from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("fleet", "0002_truck_truck_year_1900_2100"),
    ]

    operations = [
        BtreeGistExtension(),
    ]
