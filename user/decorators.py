import os
import logging
import jwt
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from functools import wraps
from urllib.parse import urlencode
from user.models import TokenBlacklist
from promptpanel.utils import get_licence, generate_jwt_login

logger = logging.getLogger("app")


def user_authenticated(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        ## Get token from header or get token from cookie
        header = request.headers.get("Authorization")
        token = None
        if header:
            parts = header.split(" ")
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
        if not token:
            token = request.COOKIES.get("authToken")
            refresh_token = request.COOKIES.get("refreshToken")
        if not token:
            if "api" in request.path:
                return JsonResponse(
                    {"status": "error", "message": "Authentication required."},
                    status=401,
                )
            else:
                query_string = urlencode({"next": request.get_full_path()})
                return HttpResponseRedirect(f"/login/?{query_string}")
        ## Check: Make sure token is active
        if TokenBlacklist.objects.filter(token=token).exists():
            if "api" in request.path:
                return JsonResponse(
                    {"status": "error", "message": "API token is disabled."},
                    status=401,
                )
            else:
                query_string = urlencode({"next": request.get_full_path()})
                return HttpResponseRedirect(f"/login/?{query_string}")
        ## Do user lookup
        try:
            access_payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            user_id = access_payload["user_id"]
            user = get_user_model().objects.get(id=user_id)
            ## Check: Make sure user is active
            if not user.is_active:
                if "api" in request.path:
                    return JsonResponse(
                        {"status": "error", "message": "User account not active."},
                        status=403,
                    )
                else:
                    logger.error("User account is not active.")
                    query_string = urlencode({"next": request.get_full_path()})
                    return HttpResponseRedirect(f"/login/?{query_string}")
            ## Renew expiries if close before returning
            ### Get access remaining time
            access_expiry_time = datetime.fromtimestamp(access_payload["exp"])
            access_remaining_time = access_expiry_time - datetime.now()
            ### Get refresh payload / remaining time
            refresh_payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
            )
            refresh_expiry_time = datetime.fromtimestamp(refresh_payload["exp"])
            refresh_remaining_time = refresh_expiry_time - datetime.now()
            ## Get view response
            request.user = user
            response = view_func(request, *args, **kwargs)
            if access_remaining_time < timedelta(hours=2):
                new_access_token = generate_jwt_login(user, None, "access")
                response.set_cookie(
                    "authToken", new_access_token, httponly=True, path="/"
                )
            if refresh_remaining_time < timedelta(hours=2):
                new_refresh_token = generate_jwt_login(user, None, "refresh")
                response.set_cookie(
                    "refreshToken", new_refresh_token, httponly=True, path="/"
                )
            return response
        ## Handle expired access token by trying to refresh it
        except jwt.ExpiredSignatureError:
            refresh_token = request.COOKIES.get("refreshToken")
            if refresh_token:
                if TokenBlacklist.objects.filter(token=refresh_token).exists():
                    if "api" in request.path:
                        return JsonResponse(
                            {
                                "status": "error",
                                "message": "Refresh token is disabled.",
                            },
                            status=401,
                        )
                    else:
                        query_string = urlencode({"next": request.get_full_path()})
                        return HttpResponseRedirect(f"/login/?{query_string}")
                try:
                    logger.info("Renewing access token")
                    refresh_payload = jwt.decode(
                        refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
                    )
                    user_id = refresh_payload["user_id"]
                    user = get_user_model().objects.get(id=user_id)
                    access_token = generate_jwt_login(user, None, "access")
                    response = view_func(request, *args, **kwargs)
                    response.set_cookie(
                        "authToken", access_token, httponly=True, path="/"
                    )
                    return response
                except Exception as e:
                    logger.error(str(e), exc_info=True)
                    if "api" in request.path:
                        return JsonResponse(
                            {
                                "status": "error",
                                "message": "Token refresh failure: " + str(e),
                            },
                            status=401,
                        )
                    query_string = urlencode({"next": request.get_full_path()})
                    return HttpResponseRedirect(f"/login/?{query_string}")
        ## Failed, revert to login
        except Exception as e:
            logger.error(str(e), exc_info=True)
            if "api" in request.path:
                return JsonResponse(
                    {"status": "error", "message": "Authentication failure: " + str(e)},
                    status=401,
                )
            query_string = urlencode({"next": request.get_full_path()})
            return HttpResponseRedirect(f"/login/?{query_string}")

    return _wrapped_view


def user_is_staff(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Admin permissions are required for accessing or updating this content.",
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def licence_active(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        licence = get_licence()
        allowed_plans = ["trial", "pro", "team", "business"]
        if licence["plan"] not in allowed_plans:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "A licence is required to access this content. Please go to Settings to view your current status.",
                },
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view
