from django.db import models
import uuid
from django.utils import timezone
from datetime import timedelta


def default_expiry():
    return timezone.now() + timedelta(minutes=10)


class SharedFile(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    filename = models.CharField(max_length=255)
    encrypted_data = models.BinaryField()
    verified_ip = models.CharField(max_length=50, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    session_key = models.CharField(max_length=100, blank=True, null=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    from django.contrib.auth.models import User
    uploader = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)


    expires_at = models.DateTimeField(default=default_expiry)
    downloads_used = models.IntegerField(default=0)
    max_downloads = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    receiver_email = models.EmailField(blank=True, null=True)
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_verified = models.BooleanField(default=False)

    def __str__(self):
        return str(self.token)


class DownloadLog(models.Model):
    file_token = models.UUIDField()
    email = models.EmailField()
    ip_address = models.CharField(max_length=50)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} - {self.file_token}"
