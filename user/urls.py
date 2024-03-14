import os
from django.urls import path
from user import endpoints

# fmt: off
urlpatterns = [
    ## Endpoints
    path("login/", endpoints.user_login, name="api_user_login"),
    path("onboard/", endpoints.user_onboard, name="api_user_onboard"),
    path("update/<int:user_id>/", endpoints.user_update, name="api_user_update"),
    path("licence/trial/", endpoints.licence_trial, name="api_licence_trial"),
    path("licence/set/", endpoints.licence_set, name="api_licence_set"),
    path("licence/downgrade/", endpoints.licence_downgrade, name="api_licence_downgrade"),
]

# Add pro routes
if os.path.exists("/app/pro/user_urls.py"):
    from pro.user_urls import pro_urls
    urlpatterns += pro_urls
