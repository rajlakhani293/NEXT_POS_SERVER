from django.contrib import admin

from apps.common.admin import SmartModelAdmin
from apps.settingsapi.models import FailedJob, Job, Option


admin.site.register(Option, SmartModelAdmin)
admin.site.register(Job, SmartModelAdmin)
admin.site.register(FailedJob, SmartModelAdmin)
