# Generated by Django 5.0.4 on 2024-05-03 01:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0003_panel_users_with_access"),
    ]

    operations = [
        migrations.AddField(
            model_name="file",
            name="filename",
            field=models.TextField(default=""),
        ),
        migrations.AlterField(
            model_name="file",
            name="filepath",
            field=models.TextField(default=""),
        ),
    ]
