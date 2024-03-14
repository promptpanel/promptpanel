import os
import json
import logging

logger = logging.getLogger("app")


def get_licence():
    try:
        with open("/app/licence.json", "r") as file:
            licence_file = json.load(file)
        licence = {}
        licence["key"] = licence_file["lic_key"]
        licence["email"] = licence_file["lic_email"]
        licence["seats"] = licence_file["lic_seats"]
        licence["plan"] = licence_file["lic_plan"]
        licence["expiry"] = licence_file["lic_expiry"]
        licence["state"] = licence_file["lic_state"]
        return licence
    except Exception as e:
        logger.error(e, exc_info=True)
        licence = {}
        licence["key"] = ""
        licence["email"] = ""
        licence["seats"] = 1
        licence["plan"] = "free"
        licence["expiry"] = ""
        return licence


def get_system():
    try:
        with open("/app/system.json", "r") as file:
            system_file = json.load(file)
        system = {}
        system["app_id"] = system_file["app_id"]
        return system
    except Exception as e:
        logger.error(e, exc_info=True)
