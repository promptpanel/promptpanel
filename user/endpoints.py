import os
import json
import jwt
import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from user.decorators import user_authenticated, user_is_staff
from user.models import TokenLog

logger = logging.getLogger("app")


def generate_jwt_login(user):
    expires_at = timezone.now() + timedelta(days=365)
    payload = {
        "user_id": user.id,
        "exp": int(expires_at.timestamp()),
        "iat": int(timezone.now().timestamp()),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    TokenLog.objects.create(
        token=token,
        token_type="login",
        created_by=user,
        expires_at=expires_at,
    )
    return token


@require_http_methods(["POST"])
def user_login(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        username = data.get("username")
        password = data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is None:
            try:
                user_obj = get_object_or_404(get_user_model(), email=username)
                user = authenticate(
                    request, username=user_obj.username, password=password
                )
            except:
                return JsonResponse(
                    {"status": "error", "message": "Invalid credentials"}, status=400
                )
        if user is not None:
            if user.is_active:
                token = generate_jwt_login(user)
                response = HttpResponseRedirect("/app/")
                response.set_cookie("authToken", token, httponly=True, path="/")
                return response
            else:
                return JsonResponse(
                    {"status": "error", "message": "Account is not active"}, status=403
                )
        else:
            return JsonResponse(
                {"status": "error", "message": "Invalid credentials"}, status=400
            )
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["POST"])
def user_onboard(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        # Check if email is allowed
        allowed_endings = os.getenv("PROMPT_USER_ALLOWED_DOMAINS", "")
        allowed_endings = [
            ending.strip().lower()
            for ending in allowed_endings.split(",")
            if ending.strip()
        ]
        if allowed_endings and not any(
            email.endswith(ending) for ending in allowed_endings
        ):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "PROMPT_USER_ALLOWED_DOMAINS is active. The account email does not end with any allowed domains or emails.",
                },
                status=400,
            )
        # Create if first user
        is_first_user = get_user_model().objects.count() == 0
        if is_first_user:
            user_create = get_user_model().objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=is_first_user,
                is_active=is_first_user,
            )
            user = authenticate(request, username=username, password=password)
            token = generate_jwt_login(user)
            try:
                app_id = settings.APP_ID
                base_url = os.environ.get("PROMPT_OPS_BASE")
                response = requests.post(
                    f"{base_url}/api/v1/onboard/",
                    json={"app_id": settings.APP_ID, "email": email},
                    timeout=2,
                )
                data = response.json()
            except Exception as e:
                logger.info("Could not connect to ops host")
                pass
            response = HttpResponseRedirect("/onboarding/first/")
            response.set_cookie("authToken", token, httponly=True, path="/")
            return response
        else:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Onboarding has already been completed.",
                },
                status=403,
            )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["PUT"])
def user_update(request, user_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        target_user = get_user_model().objects.get(pk=user_id)
        # Check if the updated email is allowed
        new_email = data.get("email", target_user.email)
        allowed_endings = os.getenv("PROMPT_USER_ALLOWED_DOMAINS", "")
        allowed_endings = [
            ending.strip().lower()
            for ending in allowed_endings.split(",")
            if ending.strip()
        ]
        if allowed_endings and not any(
            new_email.endswith(ending) for ending in allowed_endings
        ):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "PROMPT_USER_ALLOWED_DOMAINS is active. The account email does not end with any allowed domains or emails.",
                },
                status=400,
            )
        # Check if the requesting user is the target user or an admin
        if request.user != target_user and not request.user.is_staff:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "You do not have permission to edit this user. Please contact your administrator.",
                },
                status=403,
            )
        target_user.username = data.get("username", target_user.username)
        target_user.email = data.get("email", target_user.email)
        if "password" in data:
            target_user.set_password(data["password"])
        if request.user.is_staff:
            target_user.is_active = data.get("is_active", target_user.is_active)
            target_user.is_staff = data.get("is_staff", target_user.is_staff)
        target_user.save()
        return JsonResponse(
            {"status": "success", "message": "User updated successfully."}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@user_is_staff
@require_http_methods(["POST"])
def licence_trial(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        lic_trial = {}
        lic_trial["app_id"] = settings.APP_ID
        lic_trial["email"] = data["email"]
        base_url = os.environ.get("PROMPT_OPS_BASE")
        logger.info(lic_trial)
        response = requests.post(
            f"{base_url}/api/v1/licence/trial/", json=lic_trial, timeout=4
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
            system["lic_email"] = lic_trial["email"]
            system["lic_key"] = licence_data["key"]
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
            system["lic_email"] = lic_trial["email"]
            system["lic_key"] = licence_data["key"]
            system["lic_expiry"] = licence_data["expiry"]
            system["lic_plan"] = licence_data["plan"]
            system["lic_seats"] = licence_data["seats"]
            system["lic_state"] = "success"
            with open("/app/licence.json", "w") as file:
                json.dump(system, file)
            return JsonResponse(
                {"status": "success", "message": "Licence key updated successfully."}
            )
        else:
            return JsonResponse(
                {"status": "error", "message": "Invalid licence key"}, status=400
            )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@user_is_staff
@require_http_methods(["POST"])
def licence_set(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        lic_new = {}
        lic_new["app_id"] = settings.APP_ID
        lic_new["email"] = data["email"]
        lic_new["key"] = data["licence_key"]
        base_url = os.environ.get("PROMPT_OPS_BASE")
        response = requests.post(
            f"{base_url}/api/v1/licence/get/", json=lic_new, timeout=4
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
            system["lic_key"] = lic_new["key"]
            system["lic_email"] = lic_new["email"]
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
            system["lic_key"] = lic_new["key"]
            system["lic_email"] = lic_new["email"]
            system["lic_expiry"] = licence_data["expiry"]
            system["lic_plan"] = licence_data["plan"]
            system["lic_seats"] = licence_data["seats"]
            system["lic_state"] = "success"
            with open("/app/licence.json", "w") as file:
                json.dump(system, file)
            return JsonResponse(
                {"status": "success", "message": "Licence key updated successfully."}
            )
        else:
            return JsonResponse(
                {"status": "error", "message": "Invalid licence key"}, status=400
            )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@user_is_staff
@require_http_methods(["POST"])
def licence_downgrade(request):
    try:
        with open("/app/licence.json", "r") as file:
            system = json.load(file)
        system["lic_key"] = ""
        system["lic_email"] = ""
        system["lic_expiry"] = ""
        system["lic_plan"] = "free"
        system["lic_seats"] = 1
        system["lic_state"] = ""
        with open("/app/licence.json", "w") as file:
            json.dump(system, file)
        return JsonResponse(
            {"status": "success", "message": "Licence downgraded successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
