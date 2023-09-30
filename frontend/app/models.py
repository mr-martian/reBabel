from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    # feat = {"tier": "...", "feature": "..."} maybe + "type" and "options"
    # {unittype: {"fields": [feat,...], ("list": feat)}, ...}
    fields = models.JSONField(default=dict)

    def __str__(self):
        return self.name

    @property
    def backend_id(self):
        return f'project{self.id}'

class ProjectAccess(models.Model):
    def all_true():
        return True
    def all_false():
        return False
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    # True = all fields
    # False = no fields
    # [{"tier": "...", "feature": "..."}, ...] = specific fields
    read_fields = models.JSONField(default=all_true)
    write_fields = models.JSONField(default=all_false)
    admin = models.BooleanField(default=False)

# TODO: should be a default per root unit type
class ProjectView(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    data = models.JSONField(default=dict)
    name = models.CharField(max_length=100)
    default = models.BooleanField(default=False)

class StandardTier(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, null=True, on_delete=models.DO_NOTHING)
    description = models.TextField()
    fields = models.JSONField()

