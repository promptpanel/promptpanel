import os
import json
import jwt
import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

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


def generate_jwt_login(user, expires_in=None, token_type="access"):
    if expires_in is None:
        if token_type == "access":
            expiry_minutes = int(os.getenv("PROMPT_ACCESS_TOKEN_EXP_MINUTES", 480))
        elif token_type == "refresh":
            expiry_minutes = int(os.getenv("PROMPT_REFRESH_TOKEN_EXP_MINUTES", 43200))
        else:
            raise Exception("Token type not set")
        expires_in = timedelta(minutes=expiry_minutes)
    expires_at = timezone.now() + expires_in
    payload = {
        "user_id": user.id,
        "exp": int(expires_at.timestamp()),
        "iat": int(timezone.now().timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token
