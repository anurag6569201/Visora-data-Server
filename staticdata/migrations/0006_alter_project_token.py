# Generated by Django 5.1.7 on 2025-03-16 06:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staticdata", "0005_alter_projectfile_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="token",
            field=models.CharField(max_length=100),
        ),
    ]
