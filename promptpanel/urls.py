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
    ## Media
    re_path(r'^media/(?P<path>.*)$', panel_views.media_protected, name='media_protected'),
]

# Add pro routes
if os.path.exists("/app/pro/base_urls.py"):
    from pro.base_urls import pro_urls
    urlpatterns += pro_urls

# Setup URLs to serve namespaced static files from each plugin
for static_dir in settings.STATICFILES_DIRS:
    plugin_name = os.path.basename(os.path.dirname(static_dir))
    for root, dirs, files in os.walk(static_dir):
        for file in files:
            file_path = os.path.join(root, file).replace(static_dir, "").lstrip(os.sep)
            url_pattern = rf"^{plugin_name}/static/{file_path}$"
            urlpatterns.append(
                re_path(
                    url_pattern,
                    serve,
                    {"path": file_path, "document_root": static_dir},
                    name=f"{plugin_name}_{file_path.replace(os.sep, '_')}",
                )
            )
