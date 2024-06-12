import json
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class CommonInfo(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    meta = models.JSONField(default=dict)

    class Meta:
        abstract = True


class AccountActivationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.TextField()
    expires_at = models.DateTimeField()


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.TextField()
    expires_at = models.DateTimeField()


class TokenLog(CommonInfo):
    name = models.TextField()
    token = models.TextField()
    token_type = models.TextField()
    expires_at = models.DateTimeField()


class TokenBlacklist(CommonInfo):
    name = models.TextField()
    token = models.TextField()
    expires_at = models.DateTimeField()
