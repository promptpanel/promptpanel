import os
import logging
from django.utils import timezone
from django.conf import settings
from promptpanel.utils import get_licence

logger = logging.getLogger("app")


def global_context(request):
    user = request.user
    now = timezone.now()
    formatted_now = now.strftime("%Y%m%d%H%M%S")
    licence = get_licence()
    if user.is_authenticated:
        context = {
            "version_id": settings.VERSION_ID,
            "app_id": settings.APP_ID,
            "current_datetime": formatted_now,
            "color_primary": os.getenv("PROMPT_BRAND_COLOR"),
            "env_head": os.getenv("PROMPT_HEAD") == "ENABLED",
            "env_user_signup": os.getenv("PROMPT_USER_SIGNUP") == "ENABLED",
            "env_user_signup_activate": os.getenv("PROMPT_USER_SIGNUP_ACTIVATE")
            == "ENABLED",
            "env_password_reset": os.getenv("PROMPT_USER_RESET_PASSWORD") == "ENABLED",
            "env_oidc_display": os.getenv("PROMPT_OIDC_DISPLAY_NAME"),
            "env_ollama": os.getenv("PROMPT_OLLAMA_HOST") != "DISABLED",
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
            "version_id": settings.VERSION_ID,
            "app_id": settings.APP_ID,
            "current_datetime": formatted_now,
            "color_primary": os.getenv("PROMPT_BRAND_COLOR"),
            "env_head": os.getenv("PROMPT_HEAD") == "ENABLED",
            "env_user_signup": os.getenv("PROMPT_USER_SIGNUP") == "ENABLED",
            "env_user_signup_activate": os.getenv("PROMPT_USER_SIGNUP_ACTIVATE")
            == "ENABLED",
            "env_password_reset": os.getenv("PROMPT_USER_RESET_PASSWORD") == "ENABLED",
            "env_oidc_display": os.getenv("PROMPT_OIDC_DISPLAY_NAME"),
            "env_ollama": os.getenv("PROMPT_OLLAMA_HOST") != "DISABLED",
        }
    return context
