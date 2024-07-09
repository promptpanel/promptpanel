import os
import json
import jwt
import requests
import logging
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_http_methods
from user.decorators import user_authenticated, user_is_staff
from user.models import AccountActivationToken, PasswordResetToken
from promptpanel.utils import generate_jwt_login


logger = logging.getLogger("app")


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
                access_token = generate_jwt_login(user, None, "access")
                refresh_token = generate_jwt_login(user, None, "refresh")
                response = HttpResponseRedirect("/app/")
                response.set_cookie("authToken", access_token, httponly=True, path="/")
                response.set_cookie(
                    "refreshToken", refresh_token, httponly=True, path="/"
                )
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
            access_token = generate_jwt_login(user, None, "access")
            refresh_token = generate_jwt_login(user, None, "refresh")
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
            response.set_cookie("authToken", access_token, httponly=True, path="/")
            response.set_cookie("refreshToken", refresh_token, httponly=True, path="/")
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


@require_http_methods(["POST"])
def user_create(request):
    ## Checks if public signup is disabled
    if (
        not request.user.is_staff
        and os.environ.get("PROMPT_USER_SIGNUP", "DISABLED").strip().upper()
        != "ENABLED"
    ):
        return JsonResponse(
            {
                "status": "error",
                "message": "Admin permissions are required for creating a new user.",
            },
            status=403,
        )
    try:
        data = json.loads(request.body.decode("utf-8"))
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        send_verification = data.get("sendVerification", False)
        # Only allow is_staff and is_active if user is an admin
        is_staff = False
        is_active = False
        if request.user.is_staff:
            is_staff = data.get("is_staff", False)
            is_active = data.get("is_active", False)
        ## Check: if username already exists
        if User.objects.filter(username=username).exists():
            return JsonResponse(
                {
                    "status": "error",
                    "message": "An account with that username already exists",
                },
                status=400,
            )
        ## Check: if email already exists
        if User.objects.filter(email=email).exists():
            return JsonResponse(
                {
                    "status": "error",
                    "message": "An account with that email already exists",
                },
                status=400,
            )
        ## Check: if email is allowed before creating
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
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=is_staff,
            is_active=is_active,
        )
        ## Verification / activation >
        ## Check: if SMTP config is set for email verification + activation
        try:
            smtp_url = os.getenv("PROMPT_SMTP_HOST")
            if (
                os.getenv("PROMPT_USER_SIGNUP_ACTIVATE") == "ENABLED"
                and send_verification
                and smtp_url.strip().upper() != "DISABLED"
            ):
                token = get_random_string(32)
                expires_at = timezone.now() + timedelta(days=30)
                AccountActivationToken.objects.create(
                    user=user, token=token, expires_at=expires_at
                )
                verification_link = f"{request.build_absolute_uri('/user_activate/')}?token={token}&email={user.email}"
                logger.info("Activation Token: " + token)
                logger.info("Activation Link: " + verification_link)
                context = {
                    "username": username,
                    "verification_link": verification_link,
                }
                subject = "PromptPanel: Verify Your Email"
                html_message = render_to_string("email_activation.html", context)
                send_mail(
                    subject,
                    "",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    html_message=html_message,
                )
                response_message = (
                    "User created. Please check your email to verify your account."
                )
                return JsonResponse(
                    {"status": "success", "message": response_message},
                    status=201,
                )
        except Exception as e:
            logger.error(e, exc_info=True)
            return JsonResponse(
                {
                    "status": "error",
                    "message": "There was a problem sending your account activation email: "
                    + str(e),
                },
                status=400,
            )

        ## Return if user not activating now
        return JsonResponse(
            {"status": "success", "message": "User created successfully."},
            status=201,
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
        # Check if the requesting user is the target user or an admin.
        if request.user != target_user and not request.user.is_staff:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "You do not have permission to edit this user. Please contact your administrator.",
                },
                status=403,
            )
        # Emails, usernames, etc. can only be updated by administrators.
        # Passwords are updateable by their own users.
        if "password" in data:
            target_user.set_password(data["password"])
        if request.user.is_staff:
            updated_email = data.get("email", False)
            if updated_email:
                allowed_endings = os.getenv("PROMPT_USER_ALLOWED_DOMAINS", "")
                allowed_endings = [
                    ending.strip().lower()
                    for ending in allowed_endings.split(",")
                    if ending.strip()
                ]
                if allowed_endings and not any(
                    updated_email.endswith(ending) for ending in allowed_endings
                ):
                    return JsonResponse(
                        {
                            "status": "error",
                            "message": "PROMPT_USER_ALLOWED_DOMAINS is active. The account email does not end with any allowed domains or emails.",
                        },
                        status=400,
                    )
                target_user.email = updated_email
            target_user.username = data.get("username", target_user.username)
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
@require_http_methods(["GET"])
def user_list(request):
    if not request.user.is_staff:
        return JsonResponse(
            {
                "status": "error",
                "message": "User accounts do not have to access to user info. Please contact your administrator.",
            },
            status=403,
        )
    try:
        users = User.objects.all().values(
            "id", "username", "email", "is_staff", "is_active"
        )
        users_list = [
            {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "is_admin": user["is_staff"],
                "is_active": user["is_active"],
            }
            for user in users
        ]
        return JsonResponse(users_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@require_http_methods(["POST"])
def password_reset_request(request):
    if os.getenv("PROMPT_USER_RESET_PASSWORD") != "ENABLED":
        return JsonResponse(
            {
                "status": "error",
                "message": "Password reset is not supported by your application. Please contact your administrator.",
            },
            status=403,
        )
    try:
        data = json.loads(request.body.decode("utf-8"))
        email = data.get("email")
        user = get_object_or_404(User, email=email)
        token = get_random_string(32)
        expires_at = timezone.now() + timedelta(minutes=15)
        PasswordResetToken.objects.create(user=user, token=token, expires_at=expires_at)
        reset_link = f"{request.build_absolute_uri('/reset_password/')}?token={token}&email={email}"
        logger.info("Reset Token: " + token)
        logger.info("Reset Link: " + reset_link)
        context = {
            "username": user.username,
            "reset_link": reset_link,
        }
        subject = "Your Password Reset Request"
        html_message = render_to_string("email_password_reset.html", context)
        send_mail(
            subject, "", settings.DEFAULT_FROM_EMAIL, [email], html_message=html_message
        )
        return JsonResponse(
            {
                "status": "success",
                "message": "Password reset link has been sent to the provided email if your account exists.",
            },
            status=200,
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse(
            {
                "status": "success",
                "message": "Password reset link has been sent to the provided email if your account exists.",
            },
            status=200,
        )


@require_http_methods(["POST"])
def password_reset(request):
    if os.getenv("PROMPT_USER_RESET_PASSWORD") != "ENABLED":
        return JsonResponse(
            {
                "status": "error",
                "message": "Password reset is not supported by your application. Please contact your administrator.",
            },
            status=403,
        )
    try:
        data = json.loads(request.body.decode("utf-8"))
        email = data.get("email")
        token = data.get("token")
        new_password = data.get("new_password")
        reset_token = get_object_or_404(
            PasswordResetToken, token=token, user__email=email
        )
        if reset_token.expires_at < timezone.now():
            reset_token.delete()
            return JsonResponse(
                {"status": "error", "message": "The reset link has expired."},
                status=400,
            )
        user = reset_token.user
        user.set_password(new_password)
        user.save()
        reset_token.delete()
        return JsonResponse(
            {"status": "success", "message": "Password has been reset successfully."},
            status=200,
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse(
            {
                "status": "error",
                "message": "There was a problem with your password reset token, please try again.",
            },
            status=400,
        )


@require_http_methods(["POST"])
def user_info(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        user_id = data.get("user_id")
        token = data.get("token")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        token_user_id = payload.get("user_id")
        if token_user_id != user_id:
            return JsonResponse(
                {"status": "error", "message": "User ID mismatch"}, status=403
            )
        user = get_user_model().objects.get(id=user_id)
        if not user.is_active:
            return JsonResponse(
                {"status": "error", "message": "Account is not active"}, status=403
            )
        user_info = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
        }
        return JsonResponse({"status": "success", "data": user_info}, status=200)
    except Exception as e:
        logger.error(str(e), exc_info=True)
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
