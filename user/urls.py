import os
from django.urls import path
from user import endpoints

# fmt: off
urlpatterns = [
    ## Endpoints
    path("login/", endpoints.user_login, name="api_user_login"),
    path("onboard/", endpoints.user_onboard, name="api_user_onboard"),
    path("create/", endpoints.user_create, name="api_user_create"),
    path("list/", endpoints.user_list, name="api_user_list"),
    path("update/<int:user_id>/", endpoints.user_update, name="api_user_update"),
    path("licence/set/", endpoints.licence_set, name="api_licence_set"),
    path("licence/downgrade/", endpoints.licence_downgrade, name="api_licence_downgrade"),
]

# Add pro routes
if os.path.exists("/app/pro/user_urls.py"):
    from pro.user_urls import pro_urls
    urlpatterns += pro_urls
