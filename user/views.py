import os
import json
import jwt
import logging
from authlib.integrations.django_client import OAuth
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from user.decorators import user_authenticated
from user.models import AccountActivationToken, TokenBlacklist
from promptpanel.utils import generate_jwt_login

logger = logging.getLogger("app")

# OAuth setup
oauth = OAuth()
# General oauth env vars
client_id = os.getenv("PROMPT_OIDC_CLIENT_ID", "DISABLED")
client_secret = os.getenv("PROMPT_OIDC_CLIENT_SECRET", "DISABLED")
authorize_url = os.getenv("PROMPT_OIDC_AUTHORIZE_URL", "DISABLED")
access_token_url = os.getenv("PROMPT_OIDC_ACCESS_TOKEN_URL", "DISABLED")
userinfo_url = os.getenv("PROMPT_OIDC_USERINFO_URL", "DISABLED")
client_kwargs_str = os.getenv("PROMPT_OIDC_KWARGS", "DISABLED")

# Parse client_kwargs
try:
    client_kwargs = (
        json.loads(client_kwargs_str) if client_kwargs_str != "DISABLED" else {}
    )
except json.JSONDecodeError:
    client_kwargs = {}

# Register general oauth
if all(
    value != "DISABLED"
    for value in [client_id, client_secret, authorize_url, access_token_url]
):
    oauth.register(
        name="oauth_provider",
        client_id=client_id,
        client_secret=client_secret,
        authorize_url=authorize_url,
        access_token_url=access_token_url,
        client_kwargs=client_kwargs,
    )


def login(request):
    if not User.objects.exists():
        return redirect("/onboarding/")
    context = {}
    return render(request, "login.html", context)


def onboarding(request):
    if User.objects.exists():
        return redirect("/login/")
    context = {}
    return render(request, "onboarding.html", context)


@user_authenticated
def onboarding_first(request):
    context = {}
    return render(request, "onboarding_first.html", context)


@user_authenticated
def profile(request):
    context = {}
    return render(request, "profile.html", context)


@user_authenticated
def user_list(request):
    context = {}
    return render(request, "user_list.html", context)


@user_authenticated
def update_password(request):
    context = {}
    return render(request, "update_password.html", context)


@user_authenticated
def system(request):
    context = {}
    return render(request, "system.html", context)


@user_authenticated
def ollama_model(request):
    context = {}
    return render(request, "ollama_model.html", context)


def user_reset_password_request(request):
    context = {}
    return render(request, "user_reset_password_request.html", context)


def user_reset_password(request):
    context = {}
    return render(request, "user_reset_password.html", context)


def user_signup(request):
    context = {}
    return render(request, "user_signup.html", context)


def user_activate(request):
    token = request.GET.get("token")
    email = request.GET.get("email")
    context = {}
    if not token or not email:
        return redirect("/login?activate_success=false")
    try:
        activation_token = get_object_or_404(AccountActivationToken, token=token)
        if activation_token.user.email != email:
            logger.errpr("Error: Activation token does not match email.")
            return redirect("/login?activate_success=false")
        user = activation_token.user
        user.is_active = True
        user.save()
        activation_token.delete()
        return redirect("/login?activate_success=true")
    except Exception as e:
        logger.error(e, exc_info=True)
        return redirect("/login?activate_success=false")


def logout(request):
    try:
        response = HttpResponseRedirect("/login/?logged_out=true")
        access_token = request.COOKIES.get("authToken")
        refresh_token = request.COOKIES.get("refreshToken")
        access_token_data = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        access_expires_at = datetime.fromtimestamp(
            access_token_data["exp"], tz=timezone.utc
        )
        TokenBlacklist.objects.create(
            token=access_token, expires_at=access_expires_at, comment="Logged out"
        )
        refresh_token_data = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
        )
        refresh_expires_at = datetime.fromtimestamp(
            refresh_token_data["exp"], tz=timezone.utc
        )
        TokenBlacklist.objects.create(
            token=refresh_token, expires_at=refresh_expires_at, comment="Logged out"
        )
        response.delete_cookie("authToken", path="/")
        response.delete_cookie("refreshToken", path="/")
        return response
    except Exception as e:
        logger.error(str(e), exc_info=True)
        response = HttpResponseRedirect("/login/?logged_out=true")
        response.delete_cookie("authToken", path="/")
        response.delete_cookie("refreshToken", path="/")
        return response


def oauth_login(request):
    try:
        if (
            any(
                value == "DISABLED"
                for value in [
                    client_id,
                    client_secret,
                    authorize_url,
                    access_token_url,
                    userinfo_url,
                ]
            )
            or client_kwargs == "DISABLED"
        ):
            logger.error("One or more configuration variables for OAuth are disabled.")
            return HttpResponseRedirect(f"/login/?oauth_failed_login=true")

        # Parse client_kwargs only if it's not disabled
        if client_kwargs != "DISABLED":
            client_kwargs = json.loads(client_kwargs)
        else:
            client_kwargs = {}

        redirect_uri = request.build_absolute_uri(reverse("oauth_callback"))
        return oauth.oauth_provider.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_login=true")


def oauth_callback(request):
    try:
        token = oauth.oauth_provider.authorize_access_token(request)
        userinfo = oauth.oauth_provider.get(userinfo_url, token=token).json()
        # Parse different styles of userinfo
        if isinstance(userinfo, list):
            for item in userinfo:
                if "email" in item:
                    email = item["email"]
                    break
            else:
                email = None
        elif isinstance(userinfo, dict):
            email = userinfo.get("email", None)
        else:
            email = None
        if not email:
            logger.error("OAuth error: User info or email not found in user info.")
            return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")
        # User exists - login and push to app
        try:
            user = User.objects.get(email=email)
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
                logger.error("OAuth error: User's PromptPanel account is deactivated.")
                return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")
        # No user exists - create and onboard
        except User.DoesNotExist:
            # Check if email is allowed before creating
            allowed_endings = os.getenv("PROMPT_USER_ALLOWED_DOMAINS", "")
            allowed_endings = [
                ending.strip().lower()
                for ending in allowed_endings.split(",")
                if ending.strip()
            ]
            if allowed_endings and not any(
                email.endswith(ending) for ending in allowed_endings
            ):
                logger.error(
                    f"OAuth error: Email '{email}' does not end with any allowed domains or emails."
                )
                return HttpResponseRedirect(f"/login/?oauth_failed_domain=true")
            # Create user
            user = User.objects.create(username=email, email=email)
            user.set_unusable_password()
            user.save()
            if user.is_active:
                access_token = generate_jwt_login(user, None, "access")
                refresh_token = generate_jwt_login(user, None, "refresh")
                response = HttpResponseRedirect("/onboarding/first/")
                response.set_cookie("authToken", access_token, httponly=True, path="/")
                response.set_cookie(
                    "refreshToken", refresh_token, httponly=True, path="/"
                )
                return response
            else:
                return JsonResponse(
                    {"status": "error", "message": "New account is not active"},
                    status=403,
                )
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")
