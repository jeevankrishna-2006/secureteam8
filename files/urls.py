from django.urls import path
from . import views

urlpatterns = [
    path("", views.upload_file, name="upload"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("delete/<uuid:token>/", views.delete_file, name="delete_file"),

    path("download/<uuid:token>/", views.download_file, name="download"),
    path("send-otp/<uuid:token>/", views.send_otp, name="send_otp"),
    path("verify-otp/<uuid:token>/", views.verify_otp, name="verify_otp"),
    path("login/", views.login_page, name="login_page"),
    path("signup/", views.signup_page, name="signup_page"),
    path("logout/", views.logout_page, name="logout_page"),
    path("analytics/", views.analytics, name="analytics"),
path("export-logs/", views.export_logs, name="export_logs"),


]
