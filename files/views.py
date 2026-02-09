import io
import random
from datetime import timedelta
import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from django.core.mail import send_mail

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User

from .models import SharedFile, DownloadLog
from .utils import encrypt_file, decrypt_file


def signup_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {"message": "❌ Username already taken"})

        user = User.objects.create_user(username=username, email=email, password=password)
        user.save()

        return redirect("login_page")

    return render(request, "signup.html")


def login_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        return render(request, "login.html", {"message": "❌ Invalid Username or Password"})

    return render(request, "login.html")


def logout_page(request):
    logout(request)
    return redirect("login_page")


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
                uploader=request.user,
                filename=uploaded_file.name,
                encrypted_data=encrypted,
                expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
                max_downloads=max_downloads,
                receiver_email=receiver_email
            )

            file_url = f"/download/{obj.token}/"

    return render(request, "upload.html", {"file_url": file_url})


@login_required
def dashboard(request):
    all_files = SharedFile.objects.filter(uploader=request.user).order_by("-uploaded_at")
    return render(request, "dashboard.html", {"files": all_files})


@login_required
def delete_file(request, token):
    obj = get_object_or_404(SharedFile, token=token, uploader=request.user)

    if request.method == "POST":
        obj.delete()
        return redirect("dashboard")

    return HttpResponse("Invalid Request")


def send_otp(request, token):
    obj = get_object_or_404(SharedFile, token=token)

    if request.method == "POST":
        email = request.POST.get("email")

        if email != obj.receiver_email:
            return render(request, "otp_verify.html", {"message": "❌ This link is not for your email"})

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


def verify_otp(request, token):
    obj = get_object_or_404(SharedFile, token=token)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")

        if obj.otp_created_at is None or timezone.now() > obj.otp_created_at + timedelta(minutes=2):
            return render(request, "otp_enter.html", {"message": "❌ OTP Expired. Request again."})

        if entered_otp == obj.otp_code:
            if not request.session.session_key:
                request.session.create()

            ip = request.META.get("REMOTE_ADDR")

            obj.verified_ip = ip
            obj.otp_verified = True
            obj.session_key = request.session.session_key
            obj.save()

            request.session["verified_token"] = str(obj.token)

            return redirect("download", token=token)

        return render(request, "otp_enter.html", {"message": "❌ Invalid OTP"})

    return render(request, "otp_enter.html")


def download_file(request, token):
    obj = get_object_or_404(SharedFile, token=token)

    if not obj.is_active:
        return HttpResponse("❌ Link is inactive or already used.")

    if timezone.now() > obj.expires_at:
        obj.is_active = False
        obj.save()
        return HttpResponse("⏳ Link expired.")

    if obj.downloads_used >= obj.max_downloads:
        obj.is_active = False
        obj.save()
        return HttpResponse("🚫 Download limit reached.")

    if not obj.otp_verified:
        return redirect("send_otp", token=token)

    if request.session.get("verified_token") != str(obj.token):
        return HttpResponse("❌ Access denied: OTP session mismatch.")

    if obj.session_key and obj.session_key != request.session.session_key:
        return HttpResponse("❌ Access denied: different session detected.")

    current_ip = request.META.get("REMOTE_ADDR")

    if obj.verified_ip and obj.verified_ip != current_ip:
        return HttpResponse("❌ Access denied: different network/device detected.")

    if request.method == "POST":
        obj.downloads_used += 1
        if obj.downloads_used >= obj.max_downloads:
            obj.is_active = False

        DownloadLog.objects.create(
            file_token=obj.token,
            email=obj.receiver_email,
            ip_address=current_ip
        )

        decrypted = decrypt_file(obj.encrypted_data)

        if not obj.is_active:
            obj.encrypted_data = b""

        obj.save()

        return FileResponse(io.BytesIO(decrypted), as_attachment=True, filename=obj.filename)

    remaining_seconds = int((obj.expires_at - timezone.now()).total_seconds())

    return render(request, "download_page.html", {
        "filename": obj.filename,
        "remaining_seconds": remaining_seconds
    })



@login_required
def analytics(request):
    total_files = SharedFile.objects.filter(uploader=request.user).count()
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
    response["Content-Disposition"] = 'attachment; filename="download_logs.csv"'

    writer = csv.writer(response)
    writer.writerow(["Email", "File Token", "IP Address", "Downloaded At"])

    for log in DownloadLog.objects.all():
        writer.writerow([log.email, log.file_token, log.ip_address, log.downloaded_at])

    return response
