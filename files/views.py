import io
import random
from datetime import timedelta
import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from .models import SharedFile, DownloadLog
from .utils import encrypt_file, decrypt_file


# -------------------------
# AUTHENTICATION
# -------------------------

def signup_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {
                "message": "❌ Username already taken"
            })

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        return redirect("login_page")

    return render(request, "signup.html")


def login_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("dashboard")

        return render(request, "login.html", {
            "message": "❌ Invalid Username or Password"
        })

    return render(request, "login.html")


def logout_page(request):
    logout(request)
    return redirect("login_page")


# -------------------------
# FILE UPLOAD
# -------------------------

@login_required
def upload_file(request):
    file_url = None

    if request.method == "POST":
        uploaded_file = request.FILES.get("file")

        if uploaded_file:
            expiry_minutes = int(request.POST.get("expiry", 10))
            max_downloads = int(request.POST.get("max_downloads", 1))
            receiver_email = request.POST.get("receiver_email")

            file_data = uploaded_file.read()
            encrypted = encrypt_file(file_data)

            obj = SharedFile.objects.create(
    uploader=request.user,   # THIS LINE MUST EXIST
    filename=uploaded_file.name,
    encrypted_data=encrypted,
    expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
    max_downloads=max_downloads,
    receiver_email=receiver_email
)

            file_url = f"/download/{obj.token}/"

    return render(request, "upload.html", {"file_url": file_url})


# -------------------------
# DASHBOARD
# -------------------------

@login_required
def dashboard(request):
    files = SharedFile.objects.filter(
        uploader=request.user,
        is_active=True
    ).order_by("-uploaded_at")

    return render(request, "dashboard.html", {"files": files})


@login_required
def delete_file(request, token):
    obj = get_object_or_404(
        SharedFile,
        token=token,
        uploader=request.user
    )

    if request.method == "POST":
        obj.delete()
        return redirect("dashboard")

    return HttpResponse("Invalid Request")


# -------------------------
# OTP SYSTEM
# -------------------------

def send_otp(request, token):
    obj = get_object_or_404(SharedFile, token=token)

    if request.method == "POST":
        email = request.POST.get("email")

        if email != obj.receiver_email:
            return render(request, "otp_verify.html", {
                "message": "❌ This link is not for your email"
            })

        otp = str(random.randint(100000, 999999))

        obj.otp_code = otp
        obj.otp_verified = False
        obj.otp_created_at = timezone.now()
        obj.session_key = None
        obj.verified_ip = None
        obj.save()

        send_mail(
            "Your OTP for Secure File Download",
            f"Your OTP is: {otp}",
            None,
            [email],
            fail_silently=False
        )

        return redirect("verify_otp", token=token)

    return render(request, "otp_verify.html")

# files/views.py

def verify_otp(request, token):
    obj = get_object_or_404(SharedFile, token=token)

    # 🚫 Block check
    if obj.blocked_until and timezone.now() < obj.blocked_until:
        return render(request, "otp_enter.html", {
            "message": "🚫 Too many attempts. Try again after 5 minutes."
        })

    if request.method == "POST":
        entered_otp = request.POST.get("otp")

        # ⏳ OTP Expiry
        if obj.otp_created_at is None or timezone.now() > obj.otp_created_at + timedelta(minutes=2):
            obj.otp_verified = False
            obj.save()
            return render(request, "otp_enter.html", {
                "message": "❌ OTP Expired. Request again."
            })

        if entered_otp == obj.otp_code:

            obj.failed_attempts = 0
            obj.blocked_until = None

            # 🔥 Strong session reset
            request.session.cycle_key()   # Create fresh session
           

            obj.session_key = request.session.session_key
            obj.verified_ip = request.META.get("REMOTE_ADDR")
            obj.otp_verified = True
            obj.save()
            request.session["verified_token"] = str(obj.token)
            request.session["verified_session"] = request.session.session_key
            

            return redirect("download", token=token)

        else:
            obj.failed_attempts += 1

            if obj.failed_attempts >= 3:
                obj.blocked_until = timezone.now() + timedelta(minutes=5)
                obj.failed_attempts = 0

            obj.save()

            return render(request, "otp_enter.html", {
                "message": "❌ Invalid OTP"
            })

    return render(request, "otp_enter.html")

# -------------------------
# DOWNLOAD SYSTEM
# -------------------------

# files/views.py

def download_file(request, token):
    obj = get_object_or_404(SharedFile, token=token)
    current_ip = request.META.get("REMOTE_ADDR")

    # -------------------------
    # BASIC CHECKS
    # -------------------------

    if not obj.is_active:
        return render(request, "download_page.html", {
            "error_message": "❌ Link is inactive.",
            "disable_timer": True
        })

    if timezone.now() > obj.expires_at:
        obj.is_active = False
        obj.save()
        return render(request, "download_page.html", {
            "error_message": "⏳ Link expired.",
            "disable_timer": True
        })

    if obj.downloads_used >= obj.max_downloads:
        obj.is_active = False
        obj.save()
        return render(request, "download_page.html", {
            "error_message": "🚫 Download limit completed.",
            "disable_timer": True
        })

    # -------------------------
    # OTP RECHECK
    # -------------------------

    if obj.otp_created_at and timezone.now() > obj.otp_created_at + timedelta(minutes=2):
        obj.otp_verified = False
        obj.save()
        return redirect("send_otp", token=token)

    if not obj.otp_verified:
        return redirect("send_otp", token=token)

    # -------------------------
    # SESSION LOCK
    # -------------------------
# -------------------------
# STRICT SESSION LOCK
# -------------------------

    if request.session.get("verified_token") != str(obj.token):
        return render(request, "download_page.html", {
            "error_message": "❌ Session not authorized.",
            "disable_timer": True
    })

    if request.session.get("verified_session") != request.session.session_key:
        return render(request, "download_page.html", {
            "error_message": "❌ Different session detected.",
            "disable_timer": True
    })

    if obj.session_key != request.session.session_key:
        return render(request, "download_page.html", {
            "error_message": "❌ Session mismatch.",
            "disable_timer": True
    })
    # -------------------------
    # IP LOCK
    # -------------------------

    if obj.verified_ip and obj.verified_ip != current_ip:
        return render(request, "download_page.html", {
            "error_message": "❌ Different network/device detected.",
            "disable_timer": True
        })

    # -------------------------
    # DOWNLOAD (POST ONLY)
    # -------------------------

    if request.method == "POST":

        # 🔥 RATE LIMIT (5 per minute)
        if "rate_limit" not in request.session:
            request.session["rate_limit"] = []

        now = timezone.now().timestamp()

        request.session["rate_limit"] = [
            t for t in request.session["rate_limit"]
            if now - t < 60
        ]

        if len(request.session["rate_limit"]) >= 5:
            return render(request, "download_page.html", {
                "error_message": "🚫 Too many requests. Try again after 1 minute.",
                "disable_timer": True
            })

        request.session["rate_limit"].append(now)

        # Log download
        DownloadLog.objects.create(
    sender_username=obj.uploader.username,
    file_token=str(obj.token),
    email=obj.receiver_email,
    ip_address=current_ip
)
        obj.downloads_used += 1

        if obj.downloads_used >= obj.max_downloads:
            obj.is_active = False

        decrypted_data = decrypt_file(obj.encrypted_data)
        obj.save()

        request.session.pop("verified_token", None)

        return HttpResponse(
            decrypted_data,
            content_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{obj.filename}"'
            }
        )

    # -------------------------
    # GET → SHOW PAGE
    # -------------------------

    remaining_seconds = max(
        int((obj.expires_at - timezone.now()).total_seconds()),
        0
    )

    return render(request, "download_page.html", {
        "filename": obj.filename,
        "remaining_seconds": remaining_seconds,
        "disable_timer": False
    })


def is_team_member(user):
    return user.is_authenticated and user.is_staff
# -------------------------
# ANALYTICS
# -------------------------
from django.http import HttpResponseForbidden

@login_required
def analytics(request):

    if not request.user.is_staff:
        return render(request, "access_denied.html")

    total_files = SharedFile.objects.count()
    logs = DownloadLog.objects.all().order_by("-downloaded_at")
    total_downloads = logs.count()

    return render(request, "analytics.html", {
        "total_files": total_files,
        "total_downloads": total_downloads,
        "logs": logs
    })


@login_required
def export_logs(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="download_logs.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Email", "File Token", "IP Address", "Downloaded At"])

    for log in DownloadLog.objects.all():
        writer.writerow([
            log.email,
            log.file_token,
            log.ip_address,
            log.downloaded_at
        ])

    return response