from django.contrib import admin
from .models import SharedFile, DownloadLog

admin.site.register(SharedFile)
admin.site.register(DownloadLog)
