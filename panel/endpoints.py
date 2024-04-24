import json
import logging
import shutil
import os
import requests
from importlib import import_module
from panel.models import File, Message, Panel, Thread
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import FileSystemStorage
from django.db.models import Q, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from markdown import markdown
from user.decorators import user_authenticated, user_is_staff
from promptpanel.utils import get_licence

logger = logging.getLogger("app")


## -- Utility
def run_plugin_function(context_type, payload, thread, panel):
    plugin_name = panel.plugin
    if context_type == "message":
        imported_plugin = import_module(f"plugins.{plugin_name}.handler", "")
        func = getattr(imported_plugin, "message_handler")
        return func(payload, thread, panel)
    if context_type == "file":
        imported_plugin = import_module(f"plugins.{plugin_name}.handler", "")
        func = getattr(imported_plugin, "file_handler")
        return func(payload, thread, panel)


## -- Endpoints
@user_authenticated
@require_http_methods(["GET"])
def plugin_list(request):
    try:
        plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
        plugin_names = [
            name
            for name in os.listdir(plugins_dir)
            if os.path.isdir(os.path.join(plugins_dir, name))
        ]
        plugin_list = []
        for plugin_name in plugin_names:
            licence = get_licence()
            if not licence["plan"] in [
                "trial",
                "pro",
                "team",
                "business",
            ] and plugin_name.startswith("pro__"):
                continue
            plugin_dir = os.path.join(plugins_dir, plugin_name)
            readme_path = os.path.join(plugin_dir, "readme.md")
            manifest_path = os.path.join(plugin_dir, "manifest.json")
            # Skip this plugin as it doesn't have a manifest.json file
            if not os.path.exists(manifest_path):
                continue
            if os.path.exists(readme_path):
                with open(readme_path, "r") as readme_file:
                    readme_content = readme_file.read()
                    readme_html = markdown(
                        readme_content, extensions=["fenced_code", "nl2br"]
                    )
            else:
                readme_html = ""
            with open(manifest_path, "r") as file:
                manifest_data = json.load(file)
                plugin_data = {
                    "id": plugin_name,
                    "name": manifest_data.get("name", ""),
                    "category": manifest_data.get("category", ""),
                    "description": readme_html,
                    "settings": manifest_data.get("settings", []),
                }
                plugin_list.append(plugin_data)
        sorted_plugin_list = sorted(plugin_list, key=lambda x: x["name"])
        return JsonResponse(sorted_plugin_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def plugin_detail(request, plugin_name):
    try:
        plugin_dir = os.path.join(
            os.path.dirname(__file__), "..", "plugins", plugin_name
        )
        if not os.path.isdir(plugin_dir):
            return JsonResponse(
                {"status": "error", "message": "Plugin not found"}, status=404
            )
        readme_path = os.path.join(plugin_dir, "readme.md")
        if os.path.exists(readme_path):
            with open(readme_path, "r") as readme_file:
                readme_content = readme_file.read()
                readme_html = markdown(
                    readme_content, extensions=["fenced_code", "nl2br"]
                )
        else:
            readme_html = ""
        with open(os.path.join(plugin_dir, "manifest.json"), "r") as file:
            manifest_data = json.load(file)
            plugin_data = {
                "id": plugin_name,
                "name": manifest_data.get("name", ""),
                "category": manifest_data.get("category", ""),
                "description": readme_html,
                "settings": manifest_data.get("settings", []),
            }
        return JsonResponse(plugin_data, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def panel_list(request):
    try:
        if request.user.is_staff:
            panels = Panel.objects.all()
        else:
            panels = Panel.objects.filter(
                Q(is_global=True)
                | Q(created_by=request.user)
                | Q(users_with_access=request.user)
            ).distinct()
        panel_data_list = []
        for panel in panels:
            # Plugin info and settings
            plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
            plugin_dir = os.path.join(plugins_dir, panel.plugin)
            manifest_path = os.path.join(plugin_dir, "manifest.json")
            plugin_name = "Plugin not found"
            private_settings = []
            licence = get_licence()
            if panel.plugin.startswith("pro__") and licence["plan"] not in [
                "trial",
                "pro",
                "team",
                "business",
            ]:
                continue
            if os.path.exists(manifest_path):
                with open(manifest_path, "r") as file:
                    manifest_data = json.load(file)
                    plugin_name = manifest_data.get("name", "Unnamed Plugin")
                    for setting in manifest_data.get("settings", []):
                        if setting.get("private", False):
                            private_settings.append(setting.get("name"))

            filtered_metadata = {
                key: value
                for key, value in panel.metadata.items()
                if key not in private_settings
            }
            # Display image
            display_image = (
                panel.display_image
                if panel.display_image
                else "/static/promptpanel/img/default-chat.png"
            )
            plugin_icon_path = os.path.join(plugin_dir, "static", "icon.png")
            if not panel.display_image and os.path.exists(plugin_icon_path):
                display_image = f"/plugins/{panel.plugin}/static/icon.png"
            # Calculate last_active
            last_message = panel.messages_x_panel.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            last_file = panel.file_x_panel.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            last_active = max(
                last_message if last_message else panel.updated_at,
                last_file if last_file else panel.updated_at,
            )
            panel_data = {
                "id": panel.id,
                "name": panel.name,
                "plugin": panel.plugin,
                "plugin_name": plugin_name,
                "is_global": panel.is_global,
                "created_by": panel.created_by.username,
                "created_on": panel.created_on,
                "updated_at": panel.updated_at,
                "metadata": filtered_metadata,
                "last_active": last_active,
                "display_image": display_image,
            }
            if request.user.is_staff:
                panel_data["users_with_access"] = [
                    {"id": user.id, "username": user.username}
                    for user in panel.users_with_access.all()
                ]
            panel_data_list.append(panel_data)
        # Sort panels by last active timestamp before response
        sorted_panels = sorted(
            panel_data_list, key=lambda x: x["last_active"], reverse=True
        )
        return JsonResponse(sorted_panels, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def panel_detail(request, panel_id):
    try:
        if request.user.is_staff:
            panel = get_object_or_404(Panel, id=panel_id)
        else:
            panel = get_object_or_404(
                Panel,
                Q(id=panel_id)
                & (
                    Q(is_global=True)
                    | Q(created_by=request.user)
                    | Q(users_with_access=request.user)
                ),
            )
        # Plugin info and settings
        plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
        plugin_dir = os.path.join(plugins_dir, panel.plugin)
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        plugin_name = "Plugin not found"
        private_settings = []
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as file:
                manifest_data = json.load(file)
                plugin_name = manifest_data.get("name", "Unnamed Plugin")
                for setting in manifest_data.get("settings", []):
                    if setting.get("private", False):
                        private_settings.append(setting.get("name"))
        # Display image logic
        display_image = panel.display_image if panel.display_image else None
        plugin_icon_path = os.path.join(plugin_dir, "static", "icon.png")
        if not display_image and os.path.exists(plugin_icon_path):
            display_image = f"/plugins/{panel.plugin}/static/icon.png"
        elif not display_image:
            display_image = "/static/promptpanel/img/default-chat.png"
        filtered_metadata = {
            key: value
            for key, value in panel.metadata.items()
            if key not in private_settings
        }
        panel_data = {
            "id": panel.id,
            "name": panel.name,
            "display_image": display_image,
            "plugin": panel.plugin,
            "plugin_name": plugin_name,
            "is_global": panel.is_global,
            "created_by": panel.created_by.username,
            "created_on": panel.created_on,
            "updated_at": panel.updated_at,
            "metadata": filtered_metadata,
        }
        if request.user.is_staff:
            panel_data["users_with_access"] = [
                {"id": user.id, "username": user.username}
                for user in panel.users_with_access.all()
            ]
        return JsonResponse(panel_data, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@user_is_staff
@require_http_methods(["POST"])
def panel_create(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        name = data.get("name", None)
        plugin = data.get("plugin", None)
        display_image = data.get("display_image", None)
        is_global = data.get("is_global", False)
        metadata = data.get("metadata", False)
        new_panel = Panel(
            name=name,
            plugin=plugin,
            display_image=display_image,
            is_global=is_global,
            metadata=metadata,
            created_by=request.user,
        )
        new_panel.save()
        # Update panel with access controls
        user_ids = data.get("user_access_ids", [])
        users_with_access = User.objects.filter(id__in=user_ids)
        if users_with_access.count() != len(user_ids):
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Error setting panel permissions. One or more user IDs are invalid.",
                },
                status=400,
            )
        new_panel.users_with_access.set(users_with_access)
        users_with_access_data = [
            {"id": user.id, "username": user.username}
            for user in new_panel.users_with_access.all()
        ]
        response_data = {
            "status": "success",
            "message": "Panel created successfully",
            "id": new_panel.id,
            "name": new_panel.name,
            "display_image": new_panel.display_image,
            "plugin": new_panel.plugin,
            "is_global": new_panel.is_global,
            "created_by": new_panel.created_by.username,
            "created_on": new_panel.created_on,
            "updated_at": new_panel.updated_at,
            "users_with_access": users_with_access_data,
            "metadata": new_panel.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@user_is_staff
@require_http_methods(["PUT"])
def panel_update(request, panel_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        panel = get_object_or_404(Panel, id=panel_id, created_by=request.user)
        panel.name = data.get("name", panel.name)
        panel.plugin = data.get("plugin", panel.plugin)
        panel.display_image = data.get("display_image", panel.display_image)
        panel.is_global = data.get("is_global", panel.is_global)
        panel.metadata = data.get("metadata", panel.metadata)
        user_ids = data.get("user_access_ids")
        panel.save()
        if user_ids is not None:
            users_with_access = User.objects.filter(id__in=user_ids)
            if users_with_access.count() != len(user_ids):
                return JsonResponse(
                    {"status": "error", "message": "One or more user IDs are invalid"},
                    status=400,
                )
            panel.users_with_access.set(users_with_access)
        users_with_access_data = [
            {"id": user.id, "username": user.username}
            for user in panel.users_with_access.all()
        ]
        response_data = {
            "status": "success",
            "message": "Panel updated successfully",
            "id": panel.id,
            "name": panel.name,
            "plugin": panel.plugin,
            "display_image": panel.display_image,
            "is_global": panel.is_global,
            "created_by": panel.created_by.username,
            "created_on": panel.created_on,
            "updated_at": panel.updated_at,
            "users_with_access": users_with_access_data,
            "metadata": panel.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@user_is_staff
@require_http_methods(["DELETE"])
def panel_delete(request, panel_id):
    try:
        panel = get_object_or_404(Panel, id=panel_id)
        panel.delete()
        return JsonResponse(
            {"status": "success", "message": "Panel deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["POST"])
def panel_retry(request, panel_id):
    try:
        if request.user.is_staff:
            panel = get_object_or_404(Panel, id=panel_id)
        else:
            panel = get_object_or_404(
                Panel,
                Q(id=panel_id)
                & (
                    Q(is_global=True)
                    | Q(created_by=request.user)
                    | Q(users_with_access=request.user)
                ),
            )
        messages = Message.objects.filter(panel=panel).order_by("-created_on")[:2]
        if not messages:
            return JsonResponse(
                {"status": "error", "message": "No messages found in the panel"},
                status=404,
            )
        # Check if there's more than one message
        if len(messages) > 1:
            messages[0].delete()
            message_to_use = messages[1]
        else:
            message_to_use = messages[0]
        response = run_plugin_function(message_to_use, None, panel)
        return response
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def thread_list(request):
    try:
        show_all = request.GET.get("show_all") == "true"
        if request.user.is_staff and show_all:
            threads = Thread.objects.all()
        elif request.user.is_staff:
            threads = Thread.objects.filter(created_by=request.user)
        else:
            threads = Thread.objects.filter(
                Q(panel__is_global=True)
                | Q(created_by=request.user)
                | Q(panel__users_with_access=request.user)
            ).distinct()
        for thread in threads:
            last_message = thread.messages_x_thread.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            last_file = thread.file_x_thread.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            if last_message and last_file:
                thread.last_active = max(last_message, last_file)
            elif last_message:
                thread.last_active = last_message
            elif last_file:
                thread.last_active = last_file
            else:
                thread.last_active = thread.updated_at
        sorted_threads = sorted(threads, key=lambda x: x.last_active, reverse=True)
        thread_list = [
            {
                "id": thread.id,
                "title": thread.title,
                "panel_id": thread.panel.id,
                "created_by": thread.created_by.username,
                "created_on": thread.created_on,
                "updated_at": thread.updated_at,
                "metadata": thread.metadata,
                "last_active": thread.last_active,
            }
            for thread in sorted_threads
        ]
        return JsonResponse(thread_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def thread_list_panel(request, panel_id):
    try:
        show_all = request.GET.get("show_all") == "true"
        if request.user.is_staff and show_all:
            threads = Thread.objects.filter(panel_id=panel_id)
        elif request.user.is_staff:
            threads = Thread.objects.filter(created_by=request.user, panel_id=panel_id)
        else:
            threads = Thread.objects.filter(
                Q(panel__is_global=True)
                | Q(created_by=request.user)
                | Q(panel__users_with_access=request.user),
                panel_id=panel_id,
            ).distinct()
        for thread in threads:
            last_message = thread.messages_x_thread.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            last_file = thread.file_x_thread.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            if last_message and last_file:
                thread.last_active = max(last_message, last_file)
            elif last_message:
                thread.last_active = last_message
            elif last_file:
                thread.last_active = last_file
            else:
                thread.last_active = thread.updated_at
        sorted_threads = sorted(threads, key=lambda x: x.last_active, reverse=True)
        thread_list = [
            {
                "id": thread.id,
                "title": thread.title,
                "panel_id": thread.panel.id,
                "created_by": thread.created_by.username,
                "created_on": thread.created_on,
                "updated_at": thread.updated_at,
                "metadata": thread.metadata,
                "last_active": thread.last_active,
            }
            for thread in sorted_threads
        ]
        return JsonResponse(thread_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def thread_detail(request, thread_id):
    try:
        if request.user.is_staff:
            thread = get_object_or_404(Thread, id=thread_id)
        else:
            thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        thread_data = {
            "id": thread.id,
            "title": thread.title,
            "panel_id": thread.panel.id,
            "created_by": thread.created_by.username,
            "created_on": thread.created_on,
            "updated_at": thread.updated_at,
            "metadata": thread.metadata,
        }
        return JsonResponse(thread_data, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["POST"])
def thread_create(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        title = data.get("title", None)
        panel_id = data.get("panel_id", None)
        if request.user.is_staff:
            panel = get_object_or_404(Panel, id=panel_id)
        else:
            panel = get_object_or_404(
                Panel,
                Q(id=panel_id)
                & (
                    Q(is_global=True)
                    | Q(created_by=request.user)
                    | Q(users_with_access=request.user)
                ),
            )
        metadata = data.get("metadata", None)
        new_thread = Thread(
            title=title,
            panel=panel,
            metadata=metadata,
            created_by=request.user,
        )
        new_thread.save()
        response_data = {
            "status": "success",
            "message": "Thread created successfully",
            "id": new_thread.id,
            "title": new_thread.title,
            "panel_id": new_thread.panel.id,
            "created_by": new_thread.created_by.username,
            "created_on": new_thread.created_on,
            "updated_at": new_thread.updated_at,
            "metadata": new_thread.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["POST"])
def thread_clone(request, thread_id):
    try:
        if request.user.is_staff:
            original_thread = get_object_or_404(Thread, id=thread_id)
        else:
            original_thread = get_object_or_404(
                Thread, id=thread_id, created_by=request.user
            )
        new_thread = Thread(
            title=original_thread.title + " (Duplicated)",
            panel=original_thread.panel,
            metadata=original_thread.metadata,
            created_by=request.user,
        )
        new_thread.save()
        original_messages = Message.objects.filter(
            thread=original_thread, created_by=request.user
        )
        for message in original_messages:
            Message.objects.create(
                content=message.content,
                thread=new_thread,
                panel=message.panel,
                metadata=message.metadata,
                created_by=request.user,
            )
        original_files = File.objects.filter(thread=original_thread)
        for file in original_files:
            old_file_path = file.filepath
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(old_file_path)))
            new_file_dir = os.path.join(
                base_dir, str(new_thread.panel.id), str(new_thread.id)
            )
            os.makedirs(new_file_dir, exist_ok=True)
            new_file_path = os.path.join(new_file_dir, os.path.basename(old_file_path))
            logger.info(old_file_path)
            logger.info(new_file_path)
            # Copy the file
            shutil.copy2(old_file_path, new_file_path)
            # Create new File object
            File.objects.create(
                filepath=new_file_path,
                thread=new_thread,
                panel=file.panel,
                metadata=file.metadata,
                created_by=request.user,
            )
        return JsonResponse(
            {
                "status": "success",
                "message": "Thread duplicated successfully",
                "new_thread_id": new_thread.id,
            }
        )
    except Thread.DoesNotExist:
        return JsonResponse(
            {"status": "error", "message": "Original thread not found"}, status=404
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["PUT"])
def thread_update(request, thread_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        panel_id = data.get("panel_id", thread.panel.id)
        if request.user.is_staff:
            panel = get_object_or_404(Panel, id=panel_id)
        else:
            panel = get_object_or_404(
                Panel,
                Q(id=panel_id)
                & (
                    Q(is_global=True)
                    | Q(created_by=request.user)
                    | Q(users_with_access=request.user),
                ),
            )
        thread.panel = panel
        thread.title = data.get("title", thread.title)
        thread.metadata = data.get("metadata", thread.metadata)
        thread.save()
        response_data = {
            "status": "success",
            "message": "Thread updated successfully",
            "id": thread.id,
            "title": thread.title,
            "panel_id": thread.panel.id,
            "created_by": thread.created_by.username,
            "created_on": thread.created_on,
            "updated_at": thread.updated_at,
            "metadata": thread.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["POST"])
def thread_retry(request, thread_id):
    try:
        if request.user.is_staff:
            thread = get_object_or_404(Thread, id=thread_id)
        else:
            thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        messages = Message.objects.filter(thread=thread).order_by("-created_on")[:2]
        if not messages:
            return JsonResponse(
                {"status": "error", "message": "No messages found in the thread"},
                status=404,
            )
        # Check if there's more than one message
        if len(messages) > 1:
            messages[0].delete()
            message_to_use = messages[1]
        else:
            message_to_use = messages[0]
        response = run_plugin_function("message", message_to_use, thread, thread.panel)
        return response
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["DELETE"])
def thread_delete(request, thread_id):
    try:
        if request.user.is_staff:
            thread = get_object_or_404(Thread, id=thread_id)
        else:
            thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        thread.delete()
        return JsonResponse(
            {"status": "success", "message": "Thread deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def message_list_panel(request, panel_id):
    try:
        show_all = request.GET.get("show_all") == "true"
        if request.user.is_staff and show_all:
            panel_messages = Message.objects.filter(panel_id=panel_id)
        elif request.user.is_staff:
            panel_messages = Message.objects.filter(
                created_by=request.user, panel_id=panel_id
            )
        else:
            panel_messages = Message.objects.filter(
                Q(panel__is_global=True)
                | Q(created_by=request.user)
                | Q(panel__users_with_access=request.user),
                panel_id=panel_id,
            ).distinct()
        message_list = [
            {
                "id": message.id,
                "content": markdown(
                    message.content, extensions=["fenced_code", "nl2br"]
                ),
                "content_md": message.content,
                "thread_id": message.thread_id,
                "panel_id": message.panel_id,
                "created_by": message.created_by.username,
                "created_on": message.created_on,
                "updated_at": message.updated_at,
                "metadata": message.metadata,
            }
            for message in panel_messages
        ]
        return JsonResponse(message_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def message_list_thread(request, thread_id):
    try:
        show_all = request.GET.get("show_all") == "true"
        if request.user.is_staff and show_all:
            thread_messages = Message.objects.filter(thread_id=thread_id)
        elif request.user.is_staff:
            thread_messages = Message.objects.filter(
                created_by=request.user, thread_id=thread_id
            )
        else:
            thread_messages = Message.objects.filter(
                Q(panel__is_global=True)
                | Q(created_by=request.user)
                | Q(panel__users_with_access=request.user),
                thread_id=thread_id,
            ).distinct()
        message_list = [
            {
                "id": message.id,
                "content": markdown(
                    message.content, extensions=["fenced_code", "nl2br"]
                ),
                "content_md": message.content,
                "thread_id": message.thread_id,
                "panel_id": message.panel_id,
                "created_by": message.created_by.username,
                "created_on": message.created_on,
                "updated_at": message.updated_at,
                "metadata": message.metadata,
            }
            for message in thread_messages
        ]
        return JsonResponse(message_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["POST"])
def message_create(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        content = data.get("content", None)
        metadata = data.get("metadata", None)
        thread_id = data.get("thread_id", None)
        panel_id = data.get("panel_id", None)
        thread = None
        if request.user.is_staff:
            panel = get_object_or_404(Panel, id=panel_id)
        else:
            panel = get_object_or_404(
                Panel,
                Q(id=panel_id)
                & (
                    Q(is_global=True)
                    | Q(created_by=request.user)
                    | Q(users_with_access=request.user)
                ),
            )
        if request.user.is_staff:
            thread = get_object_or_404(Thread, id=thread_id)
        else:
            thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        new_message = Message(
            content=content,
            thread=thread,
            panel=panel,
            metadata=metadata,
            created_by=request.user,
        )
        new_message.save()
        response = run_plugin_function("message", new_message, thread, panel)
        return response
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["PUT"])
def message_update(request, message_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        message = get_object_or_404(Message, id=message_id, created_by=request.user)
        panel_id = data.get("panel_id", message.panel.id)
        thread_id = data.get("thread_id", message.thread.id)
        if request.user.is_staff:
            panel = get_object_or_404(Panel, id=panel_id)
        else:
            panel = get_object_or_404(
                Panel,
                Q(id=panel_id)
                & (
                    Q(is_global=True)
                    | Q(created_by=request.user)
                    | Q(users_with_access=request.user)
                ),
            )
        if request.user.is_staff:
            thread = get_object_or_404(Thread, id=thread_id)
        else:
            thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        message.panel = panel
        message.thread = thread
        message.content = data.get("content", message.content)
        message.metadata = data.get("metadata", message.metadata)
        message.save()
        response_data = {
            "status": "success",
            "message": "Message updated successfully",
            "id": message.id,
            "content": message.content,
            "panel_id": message.panel_id,
            "thread_id": message.thread_id,
            "created_by": message.created_by.username,
            "created_on": message.created_on,
            "updated_at": message.updated_at,
            "metadata": message.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["DELETE"])
def message_delete(request, message_id):
    try:
        if request.user.is_staff:
            message = get_object_or_404(Message, id=message_id)
        else:
            message = get_object_or_404(Message, id=message_id, created_by=request.user)
        message.delete()
        return JsonResponse(
            {"status": "success", "message": "Message deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def file_list_panel(request, panel_id):
    try:
        show_all = request.GET.get("show_all") == "true"
        if request.user.is_staff and show_all:
            files = File.objects.filter(panel_id=panel_id)
        elif request.user.is_staff:
            files = File.objects.filter(created_by=request.user, panel_id=panel_id)
        else:
            files = File.objects.filter(
                Q(panel__is_global=True)
                | Q(created_by=request.user)
                | Q(panel__users_with_access=request.user),
                panel_id=panel_id,
            ).distinct()
        file_list = [
            {
                "id": file.id,
                "filepath": file.filepath,
                "panel_id": file.panel_id,
                "thread_id": file.thread_id,
                "created_by": file.created_by.username,
                "created_on": file.created_on,
                "updated_at": file.updated_at,
                "metadata": file.metadata,
            }
            for file in files
        ]
        return JsonResponse(file_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["GET"])
def file_list_thread(request, thread_id):
    try:
        show_all = request.GET.get("show_all") == "true"
        if request.user.is_staff and show_all:
            files = File.objects.filter(thread_id=thread_id)
        elif request.user.is_staff:
            files = File.objects.filter(created_by=request.user, thread_id=thread_id)
        else:
            files = File.objects.filter(
                Q(panel__is_global=True)
                | Q(created_by=request.user)
                | Q(panel__users_with_access=request.user),
                thread_id=thread_id,
            ).distinct()
        file_list = [
            {
                "id": file.id,
                "filepath": file.filepath,
                "panel_id": file.panel_id,
                "thread_id": file.thread_id,
                "created_by": file.created_by.username,
                "created_on": file.created_on,
                "updated_at": file.updated_at,
                "metadata": file.metadata,
            }
            for file in files
        ]
        return JsonResponse(file_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["POST"])
def file_create(request):
    try:
        if "file" in request.FILES:
            # Get other attributes
            panel_id = request.POST.get("panel_id", None)
            thread_id = request.POST.get("thread_id", None)
            metadata = request.POST.get("metadata", None)
            thread = None
            if request.user.is_staff:
                panel = get_object_or_404(Panel, id=panel_id)
            else:
                panel = get_object_or_404(
                    Panel,
                    Q(id=panel_id)
                    & (
                        Q(is_global=True)
                        | Q(created_by=request.user)
                        | Q(users_with_access=request.user)
                    ),
                )
            if thread_id:
                if request.user.is_staff:
                    thread = get_object_or_404(Thread, id=thread_id)
                else:
                    thread = get_object_or_404(
                        Thread, id=thread_id, created_by=request.user
                    )
            # Upload file
            uploaded_file = request.FILES["file"]
            file_name = uploaded_file.name
            save_path_components = [settings.MEDIA_ROOT, str(panel_id)]
            if thread_id:
                save_path_components.append(str(thread_id))
            save_path = os.path.join(*save_path_components)
            os.makedirs(save_path, exist_ok=True)
            file_path = os.path.join(save_path, file_name)
            fs = FileSystemStorage(location=save_path)
            filepath = fs.save(file_name, uploaded_file)
            file_full_path = os.path.join(save_path, filepath)
            # Create db object
            new_file = File(
                filepath=file_full_path,
                thread=thread,
                panel=panel,
                metadata=metadata,
                created_by=request.user,
            )
            new_file.save()
            response_data = {
                "id": new_file.id,
                "filepath": new_file.filepath,
                "panel_id": new_file.panel_id,
                "thread_id": new_file.thread_id,
                "created_by": new_file.created_by.username,
                "created_on": new_file.created_on,
                "updated_at": new_file.updated_at,
                "metadata": new_file.metadata,
            }
            response = run_plugin_function("file", new_file, thread, panel)
            return response
        else:
            return JsonResponse(
                {"status": "error", "message": "No file provided"}, status=400
            )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
@require_http_methods(["DELETE"])
def file_delete(request, file_id):
    try:
        if request.user.is_staff:
            file = get_object_or_404(File, id=file_id)
        else:
            file = get_object_or_404(File, id=file_id, created_by=request.user)
        if os.path.isfile(file.filepath):
            os.remove(file.filepath)
        file.delete()
        return JsonResponse(
            {"status": "success", "message": "File deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@user_authenticated
def ollama_proxy(request, route):
    prompt_ollama_host = os.getenv("PROMPT_OLLAMA_HOST")
    ## Check Ollama host setup
    if not prompt_ollama_host:
        return JsonResponse(
            {
                "status": "error",
                "message": "Ollama is not enabled.",
            },
            status=500,
        )
    ## Permission check
    if request.method != "GET" and not request.user.is_staff:
        return JsonResponse(
            {
                "status": "error",
                "message": "You do not have permission to access this endpoint.",
            },
            status=403,
        )
    target_api_base_url = f"{prompt_ollama_host}/api/"
    target_url = f"{target_api_base_url}{route}"
    if request.META.get("QUERY_STRING"):
        target_url += f"?{request.META.get('QUERY_STRING')}"
    try:
        logger.info(f"Proxying {request.method} request to {target_url}")
        response = requests.request(
            method=request.method,
            url=target_url,
            data=request.body,
            params=request.GET,
            allow_redirects=False,
        )
        return HttpResponse(
            content=response.content,
            status=response.status_code,
            content_type=response.headers["Content-Type"],
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse(
            {"status": "error", "message": "Ollama request failed: " + str(e)},
            status=502,
        )
