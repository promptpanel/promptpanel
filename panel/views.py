import os
import logging
from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import render, get_object_or_404
from django.template import Template, RequestContext
from user.decorators import user_authenticated
from panel.models import File, Message, Panel
from pathlib import Path
from django.views.static import serve

BASE_DIR = Path(__file__).resolve().parent.parent
logger = logging.getLogger("app")


@user_authenticated
def panel_frame(request, panel_id=None, thread_id=None, message_id=None):
    if panel_id is None:
        last_message = (
            Message.objects.filter(created_by=request.user)
            .order_by("-created_on")
            .first()
        )
        if last_message:
            panel_id = last_message.panel.id
        else:
            return render(request, "panels_create.html", {})
    context = {
        "panel_id": panel_id,
        "thread_id": thread_id if thread_id is not None else "",
        "message_id": message_id if message_id is not None else "",
    }
    logger.debug(context)
    return render(request, "frame.html", context)


@user_authenticated
def panels_create(request):
    return render(request, "panels_create.html", {})


@user_authenticated
def panels_edit(request, panel_id):
    context = {"panel_id": panel_id}
    return render(request, "panels_edit.html", context)


@user_authenticated
def panel_expanded(request, panel_id):
    panel = get_object_or_404(Panel, pk=panel_id)
    template_path = os.path.join(
        BASE_DIR, f"plugins/{panel.plugin}/templates/panel.html"
    )
    try:
        with open(template_path, "r") as file:
            template = Template(file.read())
        local_context = {
            "plugin": panel.plugin,
            "panel_name": panel.name,
            "panel_id": panel_id,
            "thread_id": "",
            "message_id": "",
        }
        global_context = RequestContext(request)
        global_context.update(local_context)
        return HttpResponse(template.render(global_context))
    except Exception as e:
        logger.error(e, exc_info=True)
        error_template = "errors/template_not_found.html"
        return render(request, error_template, {})


@user_authenticated
def thread_expanded(request, panel_id, thread_id):
    panel = get_object_or_404(Panel, pk=panel_id)
    template_path = os.path.join(
        BASE_DIR, f"plugins/{panel.plugin}/templates/thread.html"
    )
    try:
        with open(template_path, "r") as file:
            template = Template(file.read())
        local_context = {
            "plugin": panel.plugin,
            "panel_name": panel.name,
            "panel_id": panel_id,
            "thread_id": thread_id,
            "message_id": "",
        }
        global_context = RequestContext(request)
        global_context.update(local_context)
        return HttpResponse(template.render(global_context))
    except Exception as e:
        logger.error(e, exc_info=True)
        error_template = "errors/template_not_found.html"
        return render(request, error_template, {})


@user_authenticated
def message_expanded(request, panel_id, thread_id, message_id):
    panel = get_object_or_404(Panel, pk=panel_id)
    template_path = os.path.join(
        BASE_DIR, f"plugins/{panel.plugin}/templates/message.html"
    )
    try:
        with open(template_path, "r") as file:
            template = Template(file.read())
        local_context = {
            "plugin": panel.plugin,
            "panel_name": panel.name,
            "panel_id": panel_id,
            "thread_id": thread_id,
            "message_id": message_id,
        }
        global_context = RequestContext(request)
        global_context.update(local_context)
        return HttpResponse(template.render(global_context))
    except Exception as e:
        logger.error(e, exc_info=True)
        error_template = "errors/template_not_found.html"
        return render(request, error_template, {})


@user_authenticated
def media_protected(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        file_obj = get_object_or_404(File, filename=file_path)
        with open(file_path, "rb") as file:
            response = HttpResponse(
                file.read(), content_type="application/octet-stream"
            )
            response["Content-Disposition"] = "inline; filename=" + os.path.basename(
                file_path
            )
            return response
    else:
        raise Http404


@user_authenticated
def plugin_static(request, path):
    base_dir = os.path.join(settings.BASE_DIR, "plugins")
    file_path = os.path.join(base_dir, path)
    if not file_path.startswith(base_dir):
        raise Http404
    # Ensure it's part of static directory
    static_dir_path = os.path.join("/static/")
    # OS differences (if app)
    if static_dir_path not in file_path.replace("\\", "/"):
        raise Http404
    return serve(request, os.path.basename(path), os.path.dirname(file_path))
