from django.contrib import admin
from app import models

admin.site.register(models.Project)
admin.site.register(models.ProjectAccess)
admin.site.register(models.ProjectView)
admin.site.register(models.StandardTier)
