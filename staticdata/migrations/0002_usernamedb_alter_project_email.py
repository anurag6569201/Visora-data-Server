# Generated by Django 5.1.7 on 2025-03-18 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("staticdata", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserNameDb",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("username", models.CharField(max_length=100)),
                ("email", models.CharField(default="visora@gmail.com", max_length=100)),
            ],
        ),
        migrations.AlterField(
            model_name="project",
            name="email",
            field=models.CharField(default="visora@gmail.com", max_length=100),
        ),
    ]
