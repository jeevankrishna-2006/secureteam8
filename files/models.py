from django.db import models
import uuid
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User


def default_expiry():
    return timezone.now() + timedelta(minutes=10)


class SharedFile(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    uploader = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    filename = models.CharField(max_length=255)
    encrypted_data = models.BinaryField()

    uploaded_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiry)

    downloads_used = models.IntegerField(default=0)
    max_downloads = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    receiver_email = models.EmailField(blank=True, null=True)

    # OTP fields
    otp_code = models.CharField(max_length=6, blank=True, null=True)
    otp_verified = models.BooleanField(default=False)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    # Security fields
    verified_ip = models.CharField(max_length=100, blank=True, null=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)

    # Brute force protection
    failed_attempts = models.IntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.filename} - {self.token}"


class DownloadLog(models.Model):
    sender_username = models.CharField(max_length=150, blank=True, null=True)   # NEW FIELD
    file_token = models.CharField(max_length=100)
    email = models.EmailField()
    ip_address = models.CharField(max_length=100)
    downloaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender_username} - {self.file_token}"