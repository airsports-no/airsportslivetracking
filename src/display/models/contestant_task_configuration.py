from django.conf import settings
from django.db import models


class ContestantTaskConfiguration(models.Model):
    contestant = models.OneToOneField("Contestant", on_delete=models.CASCADE)
    task_subtype = models.CharField(max_length=100)
    declaration_payload = models.JSONField(default=dict)
    compiled_effective_route_payload = models.JSONField(default=dict)
    compiled_gate_times_payload = models.JSONField(default=dict)
    validation_errors = models.JSONField(default=list)
    is_valid = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def navigation_task(self):
        return self.contestant.navigation_task

    def can_edit(self) -> bool:
        return not self.is_locked

    def lock(self) -> None:
        if not self.is_locked:
            self.is_locked = True
            self.save(update_fields=["is_locked", "updated_at"])

    def clear_compiled_state(self) -> None:
        self.compiled_effective_route_payload = {}
        self.compiled_gate_times_payload = {}
        self.validation_errors = []
        self.is_valid = False
        self.save(
            update_fields=[
                "compiled_effective_route_payload",
                "compiled_gate_times_payload",
                "validation_errors",
                "is_valid",
                "updated_at",
            ]
        )
