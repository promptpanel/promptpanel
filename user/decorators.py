import jwt
from django.contrib.auth.models import User
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from functools import wraps
from urllib.parse import urlencode


def api_authenticated(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        header = request.headers.get("Authorization")
        if not header:
            return JsonResponse(
                {"status": "error", "message": "No token provided."}, status=401
            )
        token = header.split(" ")[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload["user_id"]
            user = User.objects.get(id=user_id)

            if not user.is_active:
                return JsonResponse(
                    {"status": "error", "message": "User is not active."}, status=403
                )
        except jwt.ExpiredSignatureError:
            return JsonResponse(
                {"status": "error", "message": "Token has expired."}, status=401
            )
        except jwt.InvalidTokenError:
            return JsonResponse(
                {"status": "error", "message": "Invalid token."}, status=401
            )
        except User.DoesNotExist:
            return JsonResponse(
                {"status": "error", "message": "User does not exist."}, status=404
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def view_authenticated(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        token = request.COOKIES.get("authToken")
        query_string = urlencode({"next": request.get_full_path()})
        if not token:
            return HttpResponseRedirect(f"/login/?{query_string}")
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload["user_id"]
            user = User.objects.get(id=user_id)
            if not user.is_active:
                return HttpResponseRedirect(f"/login/?{query_string}")
        except jwt.ExpiredSignatureError:
            return HttpResponseRedirect(f"/login/?{query_string}")
        except jwt.InvalidTokenError:
            return HttpResponseRedirect(f"/login/?{query_string}")
        except User.DoesNotExist:
            return HttpResponseRedirect(f"/login/?{query_string}")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
