# Generated by Django 5.0.4 on 2024-05-05 15:32
# Migrates deprecated metadata field (to be deleted earlier) to new meta field

from django.db import migrations
import json


def forward_copy_metadata_to_meta(apps, schema_editor):
    Panel = apps.get_model("panel", "Panel")
    for panel in Panel.objects.all():
        if not panel.meta:
            try:
                metadata_content = json.loads(panel._metadata)
            except json.JSONDecodeError:
                metadata_content = {}
            if metadata_content:
                panel.meta = metadata_content
                panel.save()

    Thread = apps.get_model("panel", "Thread")
    for thread in Thread.objects.all():
        if not thread.meta:
            try:
                metadata_content = json.loads(thread._metadata)
            except json.JSONDecodeError:
                metadata_content = {}
            if metadata_content:
                thread.meta = metadata_content
                thread.save()

    Message = apps.get_model("panel", "Message")
    for message in Message.objects.all():
        if not message.meta:
            try:
                metadata_content = json.loads(message._metadata)
            except json.JSONDecodeError:
                metadata_content = {}
            if metadata_content:
                message.meta = metadata_content
                message.save()

    File = apps.get_model("panel", "File")
    for file in File.objects.all():
        if not file.meta:
            try:
                metadata_content = json.loads(file._metadata)
            except json.JSONDecodeError:
                metadata_content = {}
            if metadata_content:
                file.meta = metadata_content
                file.save()


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0005_file_meta_message_meta_panel_meta_thread_meta"),
    ]

    operations = [
        migrations.RunPython(forward_copy_metadata_to_meta),
    ]
