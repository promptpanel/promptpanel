import logging
import jwt
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from functools import wraps
from urllib.parse import urlencode
from user.models import TokenLog

logger = logging.getLogger("app")


def user_authenticated(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Get token from header or get token from cookie
        header = request.headers.get("Authorization")
        token = None
        if header:
            parts = header.split(" ")
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
        if not token:
            token = request.COOKIES.get("authToken")
        if not token:
            if "api" in request.path:
                return JsonResponse(
                    {"status": "error", "message": "Authentication required."},
                    status=401,
                )
            else:
                query_string = urlencode({"next": request.get_full_path()})
                return HttpResponseRedirect(f"/login/?{query_string}")
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            # Get user:
            user_id = payload["user_id"]
            user = get_user_model().objects.get(id=user_id)
            # Check user isn't disabled:
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
            # Check token isn't disabled:
            token_log = TokenLog.objects.get(token=token)
            if token_log.disabled:
                if "api" in request.path:
                    return JsonResponse(
                        {"status": "error", "message": "Token is not active."},
                        status=403,
                    )
                else:
                    logger.error("Token is not active.")
                    query_string = urlencode({"next": request.get_full_path()})
                    return HttpResponseRedirect(f"/login/?{query_string}")
            request.user = user
            return view_func(request, *args, **kwargs)
        except Exception as e:
            if "api" in request.path:
                return JsonResponse(
                    {"status": "error", "message": "Authentication failure: " + str(e)},
                    status=401,
                )
            logger.error(str(e), exc_info=True)
            query_string = urlencode({"next": request.get_full_path()})
            return HttpResponseRedirect(f"/login/?{query_string}")

    return _wrapped_view
