# Generated by Django 5.1.7 on 2025-04-24 05:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("visoraai", "0003_userproject"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="userproject",
            unique_together=set(),
        ),
        migrations.DeleteModel(
            name="IframeResponse",
        ),
        migrations.RemoveField(
            model_name="userproject",
            name="user",
        ),
    ]
