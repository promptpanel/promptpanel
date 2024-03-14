import os
import json
import jwt
import requests
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, get_user_model
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from user.decorators import api_authenticated

logger = logging.getLogger("app")


def generate_jwt_token(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(days=365),
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@require_http_methods(["POST"])
def user_login(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        username = data.get("username")
        password = data.get("password")
        user = authenticate(request, username=username, password=password)
        # Check email login if username not found
        if user is None:
            try:
                user_obj = get_object_or_404(User, email=username)
                user = authenticate(
                    request, username=user_obj.username, password=password
                )
            except:
                return JsonResponse(
                    {"status": "error", "message": "Invalid credentials"}, status=400
                )
        # User is good, return token
        if user is not None:
            if user.is_active:
                auth_login(request, user)
                token = generate_jwt_token(user)
                return JsonResponse(
                    {
                        "status": "success",
                        "message": "Logged in successfully",
                        "token": token,
                    }
                )
            else:
                return JsonResponse(
                    {"status": "error", "message": "Account is not active"}, status=403
                )
        else:
            return JsonResponse(
                {"status": "error", "message": "Invalid credentials"}, status=400
            )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["POST"])
def user_onboard(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        if get_user_model().objects.filter(username=username).exists():
            return JsonResponse(
                {"status": "error", "message": "Username already exists"}, status=400
            )
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
            auth_login(request, user)
            token = generate_jwt_token(user)
            try:
                app_id = settings.APP_ID
                base_url = os.environ.get("PROMPT_OPS_BASE")
                response = requests.post(
                    f"{base_url}/api/v1/onboard/",
                    json={"app_id": settings.APP_ID, "email": email},
                )
                data = response.json()
            except Exception as e:
                logger.info("Could not connect to ops host")
                pass
            return JsonResponse(
                {
                    "status": "success",
                    "message": "User onboarded and activated",
                    "token": token,
                }
            )
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


@api_authenticated
@require_http_methods(["PUT"])
def user_update(request, user_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        target_user = get_user_model().objects.get(pk=user_id)
        # Check if the requesting user is the target user or an admin
        if request.user != target_user and not request.user.is_staff:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "You do not have permission to edit this user.",
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


@api_authenticated
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
            f"{base_url}/api/v1/licence/trial/",
            json=lic_trial,
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


@api_authenticated
@require_http_methods(["POST"])
def licence_set(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        lic_new = {}
        lic_new["app_id"] = settings.APP_ID
        lic_new["email"] = data["email"]
        lic_new["key"] = data["licence_key"]
        base_url = os.environ.get("PROMPT_OPS_BASE")
        response = requests.post(f"{base_url}/api/v1/licence/get/", json=lic_new)
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


@api_authenticated
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
