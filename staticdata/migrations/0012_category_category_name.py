# Generated by Django 5.1.7 on 2025-03-28 04:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staticdata", "0011_alter_category_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="category_name",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
