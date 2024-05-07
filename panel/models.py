import json
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class CommonInfo(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meta = models.JSONField(default=dict)
    _metadata = models.TextField(db_column="metadata", default="{}")

    class Meta:
        abstract = True

    @property
    def metadata(self):
        return json.loads(self._metadata)

    @metadata.setter
    def metadata(self, value):
        self._metadata = json.dumps(value)

    def save(self, *args, **kwargs):
        if not isinstance(self._metadata, str):
            self._metadata = json.dumps(self._metadata)
        super().save(*args, **kwargs)


class Panel(CommonInfo):
    name = models.TextField()
    display_image = models.TextField(blank=True, null=True)
    plugin = models.TextField()
    is_global = models.BooleanField(default=False)
    users_with_access = models.ManyToManyField(User, related_name="panel_access")


class Thread(CommonInfo):
    title = models.TextField(null=True, blank=True)
    ## Relationships
    panel = models.ForeignKey(
        Panel, related_name="thread_x_panel", default=None, on_delete=models.CASCADE
    )


class Message(CommonInfo):
    content = models.TextField()
    ## Relationships
    thread = models.ForeignKey(
        Thread,
        related_name="messages_x_thread",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )  # Optional
    panel = models.ForeignKey(
        Panel, related_name="messages_x_panel", on_delete=models.CASCADE
    )


class File(CommonInfo):
    filename = models.TextField(default="")
    filepath = models.TextField(default="")
    ## Relationships
    thread = models.ForeignKey(
        Thread,
        related_name="file_x_thread",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )  # Optional
    panel = models.ForeignKey(
        Panel, related_name="file_x_panel", on_delete=models.CASCADE
    )
