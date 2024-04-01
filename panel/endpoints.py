import json
import logging
import shutil
import os
import requests
from importlib import import_module
from panel.models import File, Message, Panel, Thread
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from markdown import markdown
from user.decorators import api_authenticated
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
@api_authenticated
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


@api_authenticated
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


@api_authenticated
@require_http_methods(["GET"])
def panel_list(request):
    try:
        panels = Panel.objects.filter(created_by=request.user)
        for panel in panels:
            # Get plugin name and settings
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
                    # Extract private settings names
                    for setting in manifest_data.get("settings", []):
                        if setting.get("private", False):
                            private_settings.append(setting.get("name"))
            # Filter metadata to exclude private settings
            filtered_metadata = {
                key: value
                for key, value in panel.metadata.items()
                if key not in private_settings
            }
            # Get display_image
            display_image = panel.display_image if panel.display_image else None
            plugin_icon_path = os.path.join(plugin_dir, "static", "icon.png")
            if not display_image and os.path.exists(plugin_icon_path):
                display_image = f"/plugins/{panel.plugin}/static/icon.png"
            elif not display_image:
                display_image = "/static/promptpanel/img/default-chat.png"
            # Get last_active
            last_message = panel.messages_x_panel.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            last_file = panel.file_x_panel.aggregate(Max("created_on"))[
                "created_on__max"
            ]
            if last_message and last_file:
                panel.last_active = max(last_message, last_file)
            elif last_message:
                panel.last_active = last_message
            elif last_file:
                panel.last_active = last_file
            else:
                panel.last_active = panel.updated_at
        sorted_panels = sorted(panels, key=lambda x: x.last_active, reverse=True)
        panel_list = [
            {
                "id": panel.id,
                "name": panel.name,
                "plugin": panel.plugin,
                "plugin_name": plugin_name,
                "created_by": panel.created_by.username,
                "created_on": panel.created_on,
                "updated_at": panel.updated_at,
                "metadata": filtered_metadata,
                "last_active": panel.last_active,
                "display_image": display_image,
            }
            for panel in sorted_panels
        ]
        return JsonResponse(panel_list, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_authenticated
@require_http_methods(["GET"])
def panel_detail(request, panel_id):
    try:
        panel = get_object_or_404(Panel, id=panel_id, created_by=request.user)
        # Get plugin name and settings
        plugins_dir = os.path.join(os.path.dirname(__file__), "..", "plugins")
        plugin_dir = os.path.join(plugins_dir, panel.plugin)
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        plugin_name = "Plugin not found"
        private_settings = []
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as file:
                manifest_data = json.load(file)
                plugin_name = manifest_data.get("name", "Unnamed Plugin")
                # Extract private settings names
                for setting in manifest_data.get("settings", []):
                    if setting.get("private", False):
                        private_settings.append(setting.get("name"))
        # Get display_image
        display_image = panel.display_image if panel.display_image else None
        plugin_icon_path = os.path.join(plugin_dir, "static", "icon.png")
        if not display_image and os.path.exists(plugin_icon_path):
            display_image = f"/plugins/{panel.plugin}/static/icon.png"
        elif not display_image:
            display_image = "/static/promptpanel/img/default-chat.png"
        # Filter metadata to exclude private settings
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
            "created_by": panel.created_by.username,
            "created_on": panel.created_on,
            "updated_at": panel.updated_at,
            "metadata": filtered_metadata,
        }
        return JsonResponse(panel_data, safe=False)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": f"{e}"}, status=400)


@api_authenticated
@require_http_methods(["POST"])
def panel_create(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        name = data.get("name", None)
        plugin = data.get("plugin", None)
        display_image = data.get("display_image", None)
        metadata = data.get("metadata", False)
        new_panel = Panel(
            name=name,
            plugin=plugin,
            display_image=display_image,
            metadata=metadata,
            created_by=request.user,
        )
        new_panel.save()
        response_data = {
            "status": "success",
            "message": "Panel created successfully",
            "id": new_panel.id,
            "name": new_panel.name,
            "display_image": new_panel.display_image,
            "plugin": new_panel.plugin,
            "created_by": new_panel.created_by.username,
            "created_on": new_panel.created_on,
            "updated_at": new_panel.updated_at,
            "metadata": new_panel.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_authenticated
@require_http_methods(["PUT"])
def panel_update(request, panel_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        panel = get_object_or_404(Panel, id=panel_id, created_by=request.user)
        panel.name = data.get("name", panel.name)
        panel.plugin = data.get("plugin", panel.plugin)
        panel.display_image = data.get("display_image", panel.display_image)
        panel.metadata = data.get("metadata", panel.metadata)
        panel.save()
        response_data = {
            "status": "success",
            "message": "Panel updated successfully",
            "id": panel.id,
            "name": panel.name,
            "plugin": panel.plugin,
            "display_image": panel.display_image,
            "created_by": panel.created_by.username,
            "created_on": panel.created_on,
            "updated_at": panel.updated_at,
            "metadata": panel.metadata,
        }
        return JsonResponse(response_data)
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_authenticated
@require_http_methods(["POST"])
def panel_retry(request, panel_id):
    try:
        panel = get_object_or_404(Panel, id=panel_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["DELETE"])
def panel_delete(request, panel_id):
    try:
        panel = get_object_or_404(Panel, id=panel_id, created_by=request.user)
        panel.delete()
        return JsonResponse(
            {"status": "success", "message": "Panel deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_authenticated
@require_http_methods(["GET"])
def thread_list(request):
    try:
        threads = Thread.objects.filter(created_by=request.user)
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


@api_authenticated
@require_http_methods(["GET"])
def thread_list_panel(request, panel_id):
    try:
        threads = Thread.objects.filter(created_by=request.user, panel_id=panel_id)
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


@api_authenticated
@require_http_methods(["GET"])
def thread_detail(request, thread_id):
    try:
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


@api_authenticated
@require_http_methods(["POST"])
def thread_create(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        title = data.get("title", None)
        panel_id = data.get("panel_id", None)
        panel = Panel.objects.get(id=panel_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["POST"])
def thread_clone(request, thread_id):
    try:
        original_thread = Thread.objects.get(id=thread_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["PUT"])
def thread_update(request, thread_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        panel_id = data.get("panel_id", thread.panel.id)
        panel = Panel.objects.get(id=panel_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["POST"])
def thread_retry(request, thread_id):
    try:
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


@api_authenticated
@require_http_methods(["DELETE"])
def thread_delete(request, thread_id):
    try:
        thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        thread.delete()
        return JsonResponse(
            {"status": "success", "message": "Thread deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_authenticated
@require_http_methods(["GET"])
def message_list_panel(request, panel_id):
    try:
        panel_messages = Message.objects.filter(
            created_by=request.user, panel_id=panel_id
        )
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


@api_authenticated
@require_http_methods(["GET"])
def message_list_thread(request, thread_id):
    try:
        thread_messages = Message.objects.filter(
            created_by=request.user, thread_id=thread_id
        )
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


@api_authenticated
@require_http_methods(["POST"])
def message_create(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
        content = data.get("content", None)
        metadata = data.get("metadata", None)
        thread_id = data.get("thread_id", None)
        panel_id = data.get("panel_id", None)
        thread = None
        if thread_id:
            thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
        panel = get_object_or_404(Panel, id=panel_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["PUT"])
def message_update(request, message_id):
    try:
        data = json.loads(request.body.decode("utf-8"))
        message = get_object_or_404(Message, id=message_id, created_by=request.user)
        panel_id = data.get("panel_id", message.panel.id)
        panel = Panel.objects.get(id=panel_id, created_by=request.user)
        message.panel = panel
        thread_id = data.get("thread_id", message.thread.id)
        thread = Thread.objects.get(id=thread_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["DELETE"])
def message_delete(request, message_id):
    try:
        message = get_object_or_404(Message, id=message_id, created_by=request.user)
        message.delete()
        return JsonResponse(
            {"status": "success", "message": "Message deleted successfully"}
        )
    except Exception as e:
        logger.error(e, exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


@api_authenticated
@require_http_methods(["GET"])
def file_list_panel(request, panel_id):
    try:
        files = File.objects.filter(created_by=request.user, panel_id=panel_id)
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


@api_authenticated
@require_http_methods(["GET"])
def file_list_thread(request, thread_id):
    try:
        files = File.objects.filter(created_by=request.user, thread_id=thread_id)
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


@api_authenticated
@require_http_methods(["POST"])
def file_create(request):
    try:
        if "file" in request.FILES:
            # Get other attributes
            panel_id = request.POST.get("panel_id", None)
            thread_id = request.POST.get("thread_id", None)
            metadata = request.POST.get("metadata", None)
            thread = None
            if thread_id:
                thread = get_object_or_404(
                    Thread, id=thread_id, created_by=request.user
                )
            panel = Panel.objects.get(id=panel_id, created_by=request.user)
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


@api_authenticated
@require_http_methods(["DELETE"])
def file_delete(request, file_id):
    try:
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


@api_authenticated
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
