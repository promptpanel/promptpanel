import os
from django.urls import path
from panel import endpoints

# fmt: off
urlpatterns = [
    ### Plugins
    path("plugins/", endpoints.plugin_list, name="api_plugin_list"),
    path("plugin/<str:plugin_name>/", endpoints.plugin_detail, name="api_plugin_detail"),
    ### Panels
    path("panels/", endpoints.panel_list, name="api_panel_list"),
    path("panel/<int:panel_id>/", endpoints.panel_detail, name="api_panel_detail"),
    path("panel/create/", endpoints.panel_create, name="api_panel_create"),
    path("panel/update/<int:panel_id>/", endpoints.panel_update, name="api_panel_update"),
    path("panel/retry/<int:panel_id>/", endpoints.panel_retry, name="api_panel_retry"),
    path("panel/delete/<int:panel_id>/", endpoints.panel_delete, name="api_panel_delete"),
    ### Threads
    path("threads/", endpoints.thread_list, name="api_thread_list"),
    path("threads/panel/<int:panel_id>/", endpoints.thread_list_panel, name="api_thread_list_panel"),
    path("thread/<int:thread_id>/", endpoints.thread_detail, name="api_thread_detail"),
    path("thread/create/", endpoints.thread_create, name="api_thread_create"),
    path("thread/duplicate/<int:thread_id>/", endpoints.thread_clone, name="api_thread_clone"),
    path("thread/update/<int:thread_id>/", endpoints.thread_update, name="api_thread_update"),
    path("thread/retry/<int:thread_id>/", endpoints.thread_retry, name="api_thread_retry"),
    path("thread/delete/<int:thread_id>/", endpoints.thread_delete, name="api_thread_delete"),
    ### Messages
    path("messages/panel/<int:panel_id>/", endpoints.message_list_panel, name="api_message_list_panel"),
    path("messages/thread/<int:thread_id>/", endpoints.message_list_thread, name="api_message_list_thread"),
    path("message/create/", endpoints.message_create, name="api_message_create"),
    path("message/update/<int:message_id>/", endpoints.message_update, name="api_message_update"),
    path("message/delete/<int:message_id>/", endpoints.message_delete, name="api_message_delete"),
    ### Files
    path("files/panel/<int:panel_id>/", endpoints.file_list_panel, name="api_file_list_panel"),
    path("files/thread/<int:thread_id>/", endpoints.file_list_thread, name="api_file_list_thread"),
    path("file/create/", endpoints.file_create, name="api_file_create"),
    path("file/update/<int:file_id>/", endpoints.file_update, name="api_file_update"),
    path("file/delete/<int:file_id>/", endpoints.file_delete, name="api_file_delete"),
    ### Ollama Proxy
    path("ollama/<path:route>/", endpoints.ollama_proxy, name="api_ollama_proxy"),
    ### Search
    path("search/", endpoints.search, name="api_Search_global"),
]

# Add pro routes
if os.path.exists("/app/pro/panel_urls.py"):
    from pro.panel_urls import pro_urls
    urlpatterns += pro_urls
