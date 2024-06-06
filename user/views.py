import os
import json
import logging
from authlib.integrations.django_client import OAuth
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from user.decorators import user_authenticated
from user.models import TokenLog
from promptpanel.utils import generate_jwt_login

logger = logging.getLogger("app")

client_id = os.getenv("PROMPT_OIDC_CLIENT_ID", "")
client_secret = os.getenv("PROMPT_OIDC_CLIENT_SECRET", "")
authorize_url = os.getenv("PROMPT_OIDC_AUTHORIZE_URL", "")
access_token_url = os.getenv("PROMPT_OIDC_ACCESS_TOKEN_URL", "")
userinfo_url = os.getenv("PROMPT_OIDC_USERINFO_URL", "")
client_kwargs = os.getenv("PROMPT_OIDC_KWARGS", "{}")
# Convert JSON string back to dictionary
if client_kwargs:
    client_kwargs = json.loads(client_kwargs)
else:
    client_kwargs = {}

oauth = OAuth()
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


def logout(request):
    try:
        response = HttpResponseRedirect("/login/?logged_out=true")
        access_token = request.COOKIES.get("authToken")
        refresh_token = request.COOKIES.get("refreshToken")
        access_token_log = TokenLog.objects.get(token=access_token)
        access_token_log.disabled = True
        access_token_log.save()
        response.delete_cookie("authToken", path="/")
        refresh_token_log = TokenLog.objects.get(token=refresh_token)
        refresh_token_log.disabled = True
        refresh_token_log.save()
        response.delete_cookie("refreshToken", path="/")
        return response
    except Exception as e:
        logger.error(str(e), exc_info=True)
        response = HttpResponseRedirect("/login/?logged_out=true")
        response.delete_cookie("authToken", path="/")
        return response


def oauth_login(request):
    try:
        if not all(
            [
                client_id.strip(),
                client_secret.strip(),
                authorize_url.strip(),
                access_token_url.strip(),
                client_kwargs,
                userinfo_url.strip(),
            ]
        ):
            logger.error("One or more configuration variables for OAuth are empty.")
            return HttpResponseRedirect(f"/login/?oauth_failed_login=true")
        redirect_uri = request.build_absolute_uri(reverse("pro_view_oauth_callback"))
        return oauth.oauth_provider.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_login=true")


def oauth_callback(request):
    try:
        token = oauth.oauth_provider.authorize_access_token(request)
        userinfo = oauth.oauth_provider.get(userinfo_url, token=token).json()
        logger.info(userinfo)
        logger.info(userinfo_url)
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
                logger.error("OAuth error: User's Prompt Panel account is deactivated.")
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
