import os
from django.conf import settings
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from user import views as user_views
from panel import views as panel_views

# fmt: off
urlpatterns = [
    ## Users
    path("login/", user_views.login, name="view_user_login"),
    path("onboarding/", user_views.onboarding, name="view_user_onboarding"),
    path("onboarding/first/", user_views.onboarding_first, name="view_user_onboarding_first"),
    path("profile/", user_views.profile, name="view_user_profile"),
    path("update_password/", user_views.update_password, name="view_update_password"),
    path("logout/", user_views.logout, name="view_user_logout"),
    path("users/", user_views.user_list, name="view_user_list"),
    path("reset_password_request/", user_views.user_reset_password_request, name="view_reset_password_request"),
    path("reset_password/", user_views.user_reset_password, name="view_reset_password"),
    path("user_activate/", user_views.user_activate, name="view_user_activate"),
    path("signup/", user_views.user_signup, name="view_user_signup"),
    path("oauth/login/", user_views.oauth_login, name="view_oauth_login"),
    path("oauth/callback/", user_views.oauth_callback, name="view_oauth_callback"),
    ## System settings
    path("system/", user_views.system, name="view_system"),
    path("system/ollama/", user_views.ollama_model, name="view_ollama"),
    ## App Frame
    path("", panel_views.panel_frame, name="view_frame_home"),
    path("app/", panel_views.panel_frame, name="view_frame"),
    path("app/<int:panel_id>/", panel_views.panel_frame, name="view_frame_panel"),
    path("app/<int:panel_id>/<int:thread_id>/", panel_views.panel_frame, name="view_frame_thread"),
    path("app/<int:panel_id>/<int:thread_id>/<int:message_id>/", panel_views.panel_frame, name="view_frame_message"),
    ## Panels
    path("panel/create/", panel_views.panels_create, name="view_panels_create"),
    path("panel/edit/<int:panel_id>/", panel_views.panels_edit, name="view_panels_edit"),
    ## Plugins
    path("panel/<int:panel_id>/", panel_views.panel_expanded, name="view_panel_panel"),
    path("panel/<int:panel_id>/<int:thread_id>/", panel_views.thread_expanded, name="view_panel_thread"),
    path("panel/<int:panel_id>/<int:thread_id>/<int:message_id>/", panel_views.message_expanded, name="view_panel_message"),
    ## API URLs
    path("api/v1/users/", include("user.urls")),
    path("api/v1/app/", include("panel.urls")),
    ## Media / Static Serving
    re_path(r'^media/(?P<path>.*)$', panel_views.media_protected, name='media_protected'),
    re_path(r'^plugins/(?P<path>.*)$', panel_views.plugin_static, name='dynamic_static'),
]

# Add pro routes
if os.path.exists("/app/pro/base_urls.py"):
    from pro.base_urls import pro_urls
    urlpatterns += pro_urls
