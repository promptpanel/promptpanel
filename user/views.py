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

# Google OAuth env vars
google_client_id = os.getenv("PROMPT_GOOGLE_CLIENT_ID", "DISABLED")
google_client_secret = os.getenv("PROMPT_GOOGLE_CLIENT_SECRET", "DISABLED")
google_authorize_url = "https://accounts.google.com/o/oauth2/auth"
google_access_token_url = "https://oauth2.googleapis.com/token"
google_userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"

# Microsoft OAuth env vars
microsoft_tenant_id = os.getenv("PROMPT_MICROSOFT_TENANT_ID", "DISABLED")
microsoft_client_id = os.getenv("PROMPT_MICROSOFT_CLIENT_ID", "DISABLED")
microsoft_client_secret = os.getenv("PROMPT_MICROSOFT_CLIENT_SECRET", "DISABLED")
microsoft_authorize_url = (
    "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
)
microsoft_access_token_url = (
    "https://login.microsoftonline.com/common/oauth2/v2.0/token"
)
microsoft_userinfo_url = "https://graph.microsoft.com/v1.0/me"

# Parse client_kwargs
try:
    client_kwargs = (
        json.loads(client_kwargs_str) if client_kwargs_str != "DISABLED" else {}
    )
except json.JSONDecodeError:
    client_kwargs = {}

# Register General OAuth
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
# Register Google OAuth
if google_client_id != "DISABLED" and google_client_secret != "DISABLED":
    oauth.register(
        name="google",
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
            "token_endpoint_auth_method": "client_secret_post",
        },
    )


# Register Microsoft OAuth
if microsoft_client_id != "DISABLED" and microsoft_client_secret != "DISABLED":
    oauth.register(
        name="microsoft",
        client_id=microsoft_client_id,
        client_secret=microsoft_client_secret,
        server_metadata_url=f"https://login.microsoftonline.com/{microsoft_tenant_id}/v2.0/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile User.Read",
            "token_endpoint_auth_method": "client_secret_post",
        },
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


def google_login(request):
    try:
        if google_client_id == "DISABLED" or google_client_secret == "DISABLED":
            logger.error("Google OAuth configuration variables are disabled.")
            return HttpResponseRedirect(f"/login/?oauth_failed_login=true")

        redirect_uri = request.build_absolute_uri(reverse("view_google_callback"))
        return oauth.google.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_login=true")


def microsoft_login(request):
    try:
        if microsoft_client_id == "DISABLED" or microsoft_client_secret == "DISABLED":
            logger.error("Microsoft OAuth configuration variables are disabled.")
            return HttpResponseRedirect(f"/login/?oauth_failed_login=true")

        redirect_uri = request.build_absolute_uri(reverse("view_microsoft_callback"))
        return oauth.microsoft.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_login=true")


def oauth_login(request):
    try:
        if any(
            value == "DISABLED"
            for value in [
                client_id,
                client_secret,
                authorize_url,
                access_token_url,
                userinfo_url,
                client_kwargs,
            ]
        ):
            logger.error("One or more configuration variables for OAuth are disabled.")
            return HttpResponseRedirect(f"/login/?oauth_failed_login=true")
        redirect_uri = request.build_absolute_uri(reverse("view_oauth_callback"))
        return oauth.oauth_provider.authorize_redirect(request, redirect_uri)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_login=true")


def oauth_user_handler(email):
    # User exists - login and push to app
    try:
        user = User.objects.get(email=email)
        if user.is_active:
            access_token = generate_jwt_login(user, None, "access")
            refresh_token = generate_jwt_login(user, None, "refresh")
            response = HttpResponseRedirect("/app/")
            response.set_cookie("authToken", access_token, httponly=True, path="/")
            response.set_cookie("refreshToken", refresh_token, httponly=True, path="/")
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
            response.set_cookie("refreshToken", refresh_token, httponly=True, path="/")
            return response
        else:
            return JsonResponse(
                {"status": "error", "message": "New account is not active"},
                status=403,
            )


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
        return oauth_user_handler(email)
    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")


def google_callback(request):
    try:
        token = oauth.google.authorize_access_token(request)
        userinfo = oauth.google.get(google_userinfo_url, token=token).json()
        email = userinfo.get("email")

        if not email:
            logger.error("Google OAuth error: Email not found in user info.")
            return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")

        return oauth_user_handler(email)

    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")


def microsoft_callback(request):
    try:
        token = oauth.microsoft.authorize_access_token(request)
        resp = oauth.microsoft.get(microsoft_userinfo_url, token=token)
        userinfo = resp.json()
        logger.info(userinfo)
        email = userinfo.get("mail") or userinfo.get("userPrincipalName")

        if not email:
            logger.error("Microsoft OAuth error: Email not found in user info.")
            return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")

        return oauth_user_handler(email)

    except Exception as e:
        logger.error(str(e), exc_info=True)
        return HttpResponseRedirect(f"/login/?oauth_failed_callback=true")
