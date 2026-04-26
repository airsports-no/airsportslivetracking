import logging
from collections import defaultdict
from django.db.models import Q, Count, Avg
from display.models import NavigationTask, Contest, Contestant, Person, Aeroplane, Club, ScoreLogEntry, ContestantReceivedPosition, ANOMALY

logger = logging.getLogger(__name__)

def get_system_statistics():
    """
    Computes system-wide statistics for contestants, competitions, and countries.
    Optimized to minimize database queries and avoid property-driven network lookups.
    """
    stats = {}

    # 1. Base counts
    stats["number_of_persons"] = Person.objects.count()
    stats["number_of_contests"] = Contest.objects.count()
    stats["number_of_tasks"] = NavigationTask.objects.count()
    stats["number_of_contestants"] = Contestant.objects.count()

    # 2. Advanced Scale Metrics
    stats["total_gps_positions"] = ContestantReceivedPosition.objects.count()
    stats["total_anomalies"] = ScoreLogEntry.objects.filter(type=ANOMALY).count()
    stats["average_air_speed"] = Contestant.objects.aggregate(Avg('air_speed'))['air_speed__avg'] or 0

    # 3. Started contestants and those who crossed starting line
    started_qs = Contestant.objects.filter(contestanttrack__calculator_started=True)
    stats["number_of_started_contestants"] = started_qs.count()

    crossed_starting_qs = started_qs.exclude(contestanttrack__current_state="Waiting...")
    stats["number_of_contestants_crossed_starting"] = crossed_starting_qs.count()

    # 4. Unique persons who have actually started a flight
    stats["number_of_persons_crossed_starting"] = Person.objects.filter(
        Q(crewmember_one__team__contestant__in=crossed_starting_qs) |
        Q(crewmember_two__team__contestant__in=crossed_starting_qs)
    ).distinct().count()

    # 5. Top Lists (Clubs and Aircraft)
    stats["top_aircraft_types"] = list(Aeroplane.objects.values('type')
                                       .annotate(count=Count('id'))
                                       .order_by('-count')[:5])
    
    stats["top_clubs"] = list(Club.objects.values('name')
                              .annotate(count=Count('team'))
                              .order_by('-count')[:5])

    # 6. Country statistics
    tasks_data = NavigationTask.objects.values('pk', 'contest_id', '_nominatim')
    
    navigation_task_by_country = defaultdict(int)
    contest_countries = defaultdict(set)
    
    for data in tasks_data:
        nominatim = data.get('_nominatim') or {}
        country = nominatim.get("address", {}).get("country", "Unknown")
        
        navigation_task_by_country[country] += 1
        if data['contest_id']:
            contest_countries[data['contest_id']].add(country)
    
    contest_by_country = defaultdict(int)
    for countries in contest_countries.values():
        for country in countries:
            contest_by_country[country] += 1

    # Format for template/output
    stats["navigation_task_per_country"] = sorted(
        navigation_task_by_country.items(),
        key=lambda k: k[1],
        reverse=True,
    )
    stats["contest_per_country"] = sorted(
        contest_by_country.items(),
        key=lambda k: k[1],
        reverse=True
    )
    
    return stats
