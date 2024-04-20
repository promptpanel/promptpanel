import json
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class CommonInfo(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
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


class TokenLog(CommonInfo):
    name = models.TextField()
    disabled = models.BooleanField(default=False)
    token = models.TextField()
    token_type = models.TextField()
    expires_at = models.DateTimeField()
