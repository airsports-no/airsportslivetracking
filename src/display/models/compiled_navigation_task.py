from django.db import models


class CompiledNavigationTask(models.Model):
    navigation_task = models.OneToOneField("NavigationTask", on_delete=models.CASCADE)
    compiled_family_route = models.OneToOneField("Route", on_delete=models.SET_NULL, null=True, blank=True)
    task_subtype = models.CharField(max_length=100)
    compiled_payload = models.JSONField(default=dict)
    source_signature = models.CharField(max_length=128, blank=True, default="")
    compiled_at = models.DateTimeField(auto_now=True)

    @property
    def is_stale(self) -> bool:
        return False

    def get_compiled_sequence(self) -> list[dict]:
        payload = self.compiled_payload or {}
        return payload.get("compiled_sequence", [])

    def get_compiled_primitives(self) -> dict:
        payload = self.compiled_payload or {}
        return payload.get("compiled_primitives", {})
