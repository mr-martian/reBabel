from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    fields = models.JSONField(default=list)

    def __str__(self):
        return self.name

    @property
    def backend_id(self):
        return f'project{self.id}'

class ProjectAccess(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # True = all fields
    # False = no fields
    # [{"tier": "...", "field": "..."}, ...] = specific fields
    read_fields = models.JSONField(default=True)
    write_fields = models.JSONField(default=False)
    admin = models.BooleanField(default=False)

class StandardTier(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    description = models.TextField()
    fields = models.JSONField()

