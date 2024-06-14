# Remove current implementation of tokenlog in-lieu of a token blacklist (to remove bloat)
# > Will use tokenlog later for API key access.

from django.db import migrations


def delete_all_tokenlog_records(apps, schema_editor):
    TokenLog = apps.get_model("user", "TokenLog")
    TokenLog.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("user", "0001_initial"),
    ]

    operations = [migrations.RunPython(delete_all_tokenlog_records)]
