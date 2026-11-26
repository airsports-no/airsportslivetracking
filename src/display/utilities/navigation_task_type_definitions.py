PRECISION = "precision"
ANR_CORRIDOR = "anr_corridor"
AIRSPORTS = "airsports"
AIRSPORT_CHALLENGE = "airsportchallenge"
POKER = "poker"
LANDING = "landing"
NAVIGATION_TASK_TYPES = (
    (PRECISION, "Precision"),
    (ANR_CORRIDOR, "ANR Corridor"),
    (AIRSPORTS, "Air Sports Race"),
    (AIRSPORT_CHALLENGE, "Air Sport Challenge"),
    (POKER, "Poker run"),
    (LANDING, "Landing"),
)

# The scorecard (by shortcut_name) a new task of a family is given unless the organiser picks another one: it is listed
# first in the scorecard picker, which preselects the first entry. A family without an entry lists the newest scorecard
# first (Scorecard.Meta.ordering).
DEFAULT_SCORECARD_SHORTCUT_NAMES = {
    AIRSPORTS: "Air Sports Race 2025",
}
