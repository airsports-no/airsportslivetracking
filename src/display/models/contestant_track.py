from django.core.exceptions import ObjectDoesNotExist
from django.db import models


class ContestantTrack(models.Model):
    """
    Has a one-to-one relationship with a contestant. Used to store metadata related to calculator status.

    TODO: Possibly remove and merge with Contestant
    """

    contestant = models.OneToOneField("Contestant", on_delete=models.CASCADE)
    score = models.FloatField(default=0)
    current_state = models.CharField(max_length=200, default="Waiting...")
    current_leg = models.CharField(max_length=100, default="")
    last_gate = models.CharField(max_length=100, default="")
    last_gate_time_offset = models.FloatField(default=0)
    passed_starting_gate = models.BooleanField(default=False)
    passed_finish_gate = models.BooleanField(default=False)
    calculator_finished = models.BooleanField(default=False)
    calculator_started = models.BooleanField(default=False)

    def reset(self):
        self.score = 0
        self.current_state = "Waiting..."
        self.current_leg = ""
        self.last_gate = ""
        self.last_gate_time_offset = 0
        self.passed_starting_gate = False
        self.passed_finish_gate = False
        self.calculator_finished = False
        self.calculator_started = False
        self.save()
        self.__push_change()

    @property
    def contest_summary(self):
        from display.models import ContestSummary

        try:
            return ContestSummary.objects.get(
                team=self.contestant.team,
                contest=self.contestant.navigation_task.contest,
            ).points
        except ObjectDoesNotExist:
            return None

    def update_last_gate(self, gate_name, time_difference):
        self.refresh_from_db()
        self.last_gate = gate_name
        self.last_gate_time_offset = time_difference
        self.save(update_fields=["last_gate", "last_gate_time_offset"])
        self.__push_change()

    def update_score(self, score):
        from display.models import TeamTestScore

        self.refresh_from_db()
        if self.score != score:
            self.score = score
            self.save(update_fields=["score"])
            # Update task test score if it exists
            if hasattr(self.contestant.navigation_task, "tasktest"):
                entry, _ = TeamTestScore.objects.update_or_create(
                    team=self.contestant.team,
                    task_test=self.contestant.navigation_task.tasktest,
                    defaults={"points": score},
                )
            self.__push_change()

    def increment_score(self, score_increment):
        from display.models import TeamTestScore

        self.refresh_from_db()
        if score_increment != 0:
            self.score += score_increment
            self.save(update_fields=["score"])
            # Update task test score if it exists
            if hasattr(self.contestant.navigation_task, "tasktest"):
                entry, _ = TeamTestScore.objects.update_or_create(
                    team=self.contestant.team,
                    task_test=self.contestant.navigation_task.tasktest,
                    defaults={"points": self.score},
                )
            self.__push_change()

    def updates_current_state(self, state: str):
        self.refresh_from_db()
        if self.current_state != state:
            self.current_state = state
            self.save(update_fields=["current_state"])
            self.__push_change()

    def update_current_leg(self, current_leg: str):
        self.refresh_from_db()
        if self.current_leg != current_leg:
            self.current_leg = current_leg
            self.save(update_fields=["current_leg"])
            self.__push_change()

    def set_calculator_finished(self):
        self.calculator_finished = True
        self.current_state = "Finished"
        self.save(update_fields=["calculator_finished", "current_state"])
        self.__push_change()

    def set_calculator_started(self):
        self.calculator_started = True
        self.save(update_fields=["calculator_started"])
        self.__push_change()

    def set_passed_starting_gate(self):
        self.refresh_from_db()
        self.passed_starting_gate = True
        self.save(update_fields=["passed_starting_gate"])
        self.__push_change()

    def set_passed_finish_gate(self):
        self.refresh_from_db()
        self.passed_finish_gate = True
        self.save(update_fields=["passed_finish_gate"])
        self.__push_change()

    def __push_change(self):
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_basic_information(self.contestant)
