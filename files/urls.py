from django.urls import path
from . import views

urlpatterns = [

    # 🔹 HOME PAGE (IMPORTANT)
    path("", views.home, name="home"),

    # 🔹 Upload
    path("upload/", views.upload_file, name="upload"),

    # 🔹 Dashboard & File Management
    path("dashboard/", views.dashboard, name="dashboard"),
    path("delete/<uuid:token>/", views.delete_file, name="delete_file"),

    # 🔹 Download Flow
    path("download/<uuid:token>/", views.download_file, name="download"),
    path("send-otp/<uuid:token>/", views.send_otp, name="send_otp"),
    path("verify-otp/<uuid:token>/", views.verify_otp, name="verify_otp"),

    # 🔹 Authentication
    path("login/", views.login_page, name="login_page"),
    path("signup/", views.signup_page, name="signup_page"),
    path("logout/", views.logout_page, name="logout_page"),

    # 🔹 Analytics
    path("analytics/", views.analytics, name="analytics"),
    path("export-logs/", views.export_logs, name="export_logs"),
]