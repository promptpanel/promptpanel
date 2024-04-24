from django.apps import AppConfig


class UserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "user"

    # Import the signal receiver function inside ready() to avoid AppRegistryNotReady exception
    def ready(self):
        import os
        import json
        import requests
        import logging
        from django.conf import settings

        logger = logging.getLogger("app")
        try:
            lic_email = os.environ.get("PROMPT_LICENSE_EMAIL", "")
            lic_key = os.environ.get("PROMPT_LICENSE_KEY", "")
            if lic_email != "" and lic_key != "":
                base_url = os.environ.get("PROMPT_OPS_BASE")
                response = requests.post(
                    f"{base_url}/api/v1/licence/get/",
                    json={
                        "app_id": settings.APP_ID,
                        "email": lic_email,
                        "key": lic_key,
                    },
                    timeout=4,
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
                    system["lic_key"] = lic_key
                    system["lic_email"] = lic_email
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
                    system["lic_key"] = lic_key
                    system["lic_email"] = lic_email
                    system["lic_expiry"] = licence_data["expiry"]
                    system["lic_plan"] = licence_data["plan"]
                    system["lic_seats"] = licence_data["seats"]
                    system["lic_state"] = "success"
                    with open("/app/licence.json", "w") as file:
                        json.dump(system, file)
        except Exception as e:
            logger.info("There was an issue with system startup (@startup).")
