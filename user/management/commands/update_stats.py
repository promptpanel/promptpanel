import os
import datetime
import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.models import User
from django.db.models.functions import Coalesce
from django.db.models import Max, Value
from django.utils import timezone
from panel.models import File, Message, Panel, Thread
from promptpanel.utils import get_licence

logger = logging.getLogger("app")


class Command(BaseCommand):
    help = "Updates stats"

    def handle(self, *args, **options):
        try:
            last_run = cache.get("last_run_time_stats")
            now = timezone.now()
            if last_run:
                next_run = last_run + datetime.timedelta(seconds=86400)
                if now < next_run:
                    # Already run, skip check
                    logger.info("Stat update skipped.")
                    return
            licence = get_licence()
            counter = {}
            counter["app_id"] = settings.APP_ID
            counter["version_id"] = settings.VERSION_ID
            counter["licence_plan"] = licence["plan"]
            plugins_dir = "/app/plugins"
            plugins = [
                name
                for name in os.listdir(plugins_dir)
                if os.path.isdir(os.path.join(plugins_dir, name))
            ]
            counter["count_plugins"] = len(plugins)
            counter["count_panels"] = Panel.objects.aggregate(
                max_id=Coalesce(Max("id"), Value(0))
            )["max_id"]
            counter["count_threads"] = Thread.objects.aggregate(
                max_id=Coalesce(Max("id"), Value(0))
            )["max_id"]
            counter["count_messages"] = Message.objects.aggregate(
                max_id=Coalesce(Max("id"), Value(0))
            )["max_id"]
            counter["count_files"] = File.objects.aggregate(
                max_id=Coalesce(Max("id"), Value(0))
            )["max_id"]
            counter["count_users"] = User.objects.filter(is_active=True).count()
            base_url = os.environ.get("PROMPT_OPS_BASE")
            response = requests.post(
                f"{base_url}/api/v1/telemetry/", json=counter, timeout=4
            )
            data = response.json()
            cache.set("last_run_time_stats", now)
            logger.info("Stats updated successfully.")
        except Exception as e:
            logger.info("Could not process stats: ", str(e))
