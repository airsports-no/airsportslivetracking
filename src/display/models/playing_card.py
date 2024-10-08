import datetime
import random
import typing

import eval7
from django.db import models

from display.poker.poker_cards import PLAYING_CARDS

if typing.TYPE_CHECKING:
    from display.models import Contestant


class PlayingCard(models.Model):
    """
    Holds the playing cards received by contestant in a poker run navigation task.
    """

    contestant = models.ForeignKey("Contestant", on_delete=models.CASCADE)
    card = models.CharField(max_length=2, choices=PLAYING_CARDS)
    waypoint_name = models.CharField(max_length=50, blank=True, null=True)
    waypoint_index = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.card} for {self.contestant} at {self.waypoint_name} (waypoint {self.waypoint_index})"

    @classmethod
    def get_random_unique_card(cls, contestant: "Contestant") -> str:
        """
        Returns a random card that has not already been assigned to the contestant.  A card is represented by a two
        letter string the first letter is the card value and the second letter is the card suit, e.g. 5s.
        """
        cards = [item[0] for item in PLAYING_CARDS]
        existing_cards = contestant.playingcard_set.all().values_list("card", flat=True)
        available_cards = set(cards) - set(existing_cards)
        if len(available_cards) == 0:
            raise ValueError(
                f"There are no available cards to choose for the contestant, he/she already has {len(existing_cards)}."
            )
        random_card = random.choice(list(available_cards))
        while contestant.playingcard_set.filter(card=random_card).exists():
            random_card = random.choice([item[0] for item in PLAYING_CARDS])
        return random_card

    @classmethod
    def evaluate_hand(cls, contestant: "Contestant") -> tuple[int, str]:
        """
        Returns the score value of the hand, as well as a string description of the hand (e.g. "pair")
        """
        hand = [eval7.Card(s.card) for s in cls.objects.filter(contestant=contestant)]
        score = eval7.evaluate(hand)
        return score, eval7.handtype(score)

    @classmethod
    def maximum_score(cls) -> int:
        """
        This is the maximum score returned by eval7
        """
        return 135004160

    @classmethod
    def get_relative_score(cls, contestant: "Contestant") -> tuple[float, str]:
        """
        Returns a relative score for the current hand held by the contestant with a resolution of 1/100 percent. The
        reason for this resolution is to avoid decimal places in the score display while maintaining sufficient scoring
        resolution.
        """
        score, hand_type = cls.evaluate_hand(contestant)
        return 10000 * score / cls.maximum_score(), hand_type

    @classmethod
    def clear_cards(cls, contestant: "Contestant"):
        """
        Removes all the cards from the hand of the contestant and resets the score to 0. Pushes the playing card update
        to the front end
        """
        from display.models import ScoreLogEntry

        contestant.playingcard_set.all().delete()

        relative_score, hand_description = cls.get_relative_score(contestant)
        try:
            waypoint = contestant.navigation_task.route.waypoints[-1].name
        except IndexError:
            waypoint = ""
        message = "Removed card all cards"
        ScoreLogEntry.create_and_push(
            contestant=contestant,
            time=datetime.datetime.now(datetime.timezone.utc),
            gate=waypoint,
            message=message,
            points=relative_score,
            string="{}: {}".format(waypoint, message),
        )

        if hasattr(contestant, "contestanttrack"):
            contestant.contestanttrack.update_score(relative_score)
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_playing_cards(contestant)

    @classmethod
    def remove_contestant_card(cls, contestant: "Contestant", card_pk: int):
        """
        Removes a specific playing card from the contestant, updates the score, and pushes the update to the front end
        """
        from display.models import ScoreLogEntry

        card = contestant.playingcard_set.filter(pk=card_pk).first()
        if card is not None:
            card.delete()
            relative_score, hand_description = cls.get_relative_score(contestant)
            waypoint = contestant.navigation_task.route.waypoints[-1].name
            message = "Removed card {}, current hand is {}".format(card.get_card_display(), hand_description)
            ScoreLogEntry.create_and_push(
                contestant=contestant,
                time=datetime.datetime.now(datetime.timezone.utc),
                gate=waypoint,
                message=message,
                points=relative_score,
                string="{}: {}".format(waypoint, message),
            )

            contestant.contestanttrack.update_score(relative_score)
            from websocket_channels import WebsocketFacade

            ws = WebsocketFacade()
            ws.transmit_playing_cards(contestant)

    @classmethod
    def add_contestant_card(cls, contestant: "Contestant", card: str, waypoint: str, waypoint_index: int):
        """
        Adds a specific card to the contestant, updates the score, and pushes this to the front end. Requires the
        waypoint index to identify at which waypoint the card was dealt.
        """
        from display.models import ScoreLogEntry, ANOMALY, TrackAnnotation

        poker_card = cls.objects.create(
            contestant=contestant,
            card=card,
            waypoint_name=waypoint,
            waypoint_index=waypoint_index,
        )
        relative_score, hand_description = cls.get_relative_score(contestant)
        message = "Received card {}, current hand is {}".format(poker_card.get_card_display(), hand_description)
        entry = ScoreLogEntry.create_and_push(
            contestant=contestant,
            time=datetime.datetime.now(datetime.timezone.utc),
            gate=waypoint,
            message=message,
            points=relative_score,
            type=ANOMALY,
            string="{}: {}".format(waypoint, message),
        )

        pos = contestant.get_latest_position()
        longitude = 0
        latitude = 0
        if pos:
            latitude = pos.latitude
            longitude = pos.longitude
        TrackAnnotation.create_and_push(
            contestant=contestant,
            latitude=latitude,
            longitude=longitude,
            message=entry.string,
            type=ANOMALY,
            time=datetime.datetime.now(datetime.timezone.utc),
            score_log_entry=entry,
        )
        contestant.contestanttrack.update_score(relative_score)
        from websocket_channels import WebsocketFacade

        ws = WebsocketFacade()
        ws.transmit_playing_cards(contestant)
