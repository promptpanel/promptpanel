import os
import json
import requests
import logging
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.functions import Coalesce
from django.db.models import Max, Value
from panel.models import File, Message, Panel, Thread
from promptpanel.utils import get_licence

logger = logging.getLogger("app")


def update_stats():
    try:
        with open("/app/updated.log", "r") as file:
            last_updated_str = file.read().strip()
            last_updated = datetime.fromisoformat(last_updated_str)
    except Exception as e:
        last_updated = datetime.min
        pass
    try:
        if datetime.now() - last_updated > timedelta(hours=24):
            licence = get_licence()
            # Telem
            try:
                counter = {}
                counter["app_id"] = settings.APP_ID
                counter["version_id"] = settings.VERSION_ID
                counter["licence_plan"] = licence["plan"]
                plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
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
                response = requests.post(f"{base_url}/api/v1/telemetry/", json=counter)
                data = response.json()
            except Exception as e:
                logger.info("Could not connect to version check: ", str(e))
                pass
            # Check / update licence
            try:
                if licence["email"] != "" and licence["key"] != "":
                    base_url = os.environ.get("PROMPT_OPS_BASE")
                    response = requests.post(
                        f"{base_url}/api/v1/licence/get/",
                        json={
                            "app_id": settings.APP_ID,
                            "email": licence["email"],
                            "key": licence["key"],
                        },
                    )
                    data = response.json()
                    if data["status"] == "deactivated":
                        with open("/app/licence.json", "r") as file:
                            system = json.load(file)
                        system["lic_key"] = ""
                        system["lic_email"] = ""
                        system["lic_expiry"] = ""
                        system["lic_plan"] = "free"
                        system["lic_seats"] = 1
                        system["lic_state"] = "deactivated"
                        with open("/app/licence.json", "w") as file:
                            json.dump(system, file)
                    if data["status"] == "warning":
                        with open("/app/licence.json", "r") as file:
                            system = json.load(file)
                        system["lic_key"] = licence["key"]
                        system["lic_email"] = licence["email"]
                        system["lic_expiry"] = licence_data["expiry"]
                        system["lic_plan"] = licence_data["plan"]
                        system["lic_seats"] = licence_data["seats"]
                        system["lic_state"] = "warning"
                        with open("/app/licence.json", "w") as file:
                            json.dump(system, file)
                    if data["status"] == "success":
                        licence_data = data["data"]
                        with open("/app/licence.json", "r") as file:
                            system = json.load(file)
                        system["lic_key"] = licence["key"]
                        system["lic_email"] = licence["email"]
                        system["lic_expiry"] = licence_data["expiry"]
                        system["lic_plan"] = licence_data["plan"]
                        system["lic_seats"] = licence_data["seats"]
                        system["lic_state"] = "success"
                        with open("/app/licence.json", "w") as file:
                            json.dump(system, file)
                    with open("/app/updated.log", "w") as file:
                        file.write(datetime.now().isoformat())
            except Exception as e:
                logger.info(
                    "❌ Licence check did not succeed. Please contact licence@promptpanel.com to resolve.",
                    str(e),
                )
        else:
            pass
    except Exception as e:
        logger.error(e, exc_info=True)


def global_context(request):
    update_stats()
    user = request.user
    now = datetime.now()
    formatted_now = now.strftime("%Y%m%d%H%M%S")
    licence = get_licence()
    if user.is_authenticated:
        context = {
            "version_id": settings.VERSION_ID,
            "app_id": settings.APP_ID,
            "current_datetime": formatted_now,
            "color_primary": os.getenv("PROMPT_BRAND_COLOR"),
            "env_pro": os.getenv("PROMPT_DISTRO") == "PRO",
            "env_head": os.getenv("PROMPT_HEAD") == "ENABLED",
            "env_ollama": os.getenv("PROMPT_OLLAMA_HOST") != "",
            "user_id": user.id,
            "user_username": user.username,
            "user_email": user.email,
            "user_is_admin": user.is_staff,
            "licence_key": licence["key"],
            "licence_email": licence["email"],
            "licence_plan": licence["plan"],
            "licence_seats": licence["seats"],
            "licence_expiry": licence["expiry"],
            "licence_state": licence["state"],
        }
    else:
        context = {
            "app_id": settings.APP_ID,
            "current_datetime": formatted_now,
            "env_head": os.getenv("PROMPT_HEAD") == "ENABLED",
        }
    return context
