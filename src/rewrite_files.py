from django.core.exceptions import ValidationError

from display.models import Person, Contest, Club, Aeroplane, Team

for contest in Contest.objects.all():
    contest.header_image = contest.header_image.field.attr_class(contest, contest.header_image.field, str(contest.header_image).split("/")[-1])
    contest.logo = contest.logo.field.attr_class(contest, contest.logo.field, str(contest.logo).split("/")[-1])
    print(contest.header_image)
    contest.save()

for person in Person.objects.all():
    person.picture = person.picture.field.attr_class(person, person.picture.field, str(person.picture).split("/")[-1])
    try:
        person.save()
    except:
        print(person)
        
for contest in Club.objects.all():
    contest.logo = contest.logo.field.attr_class(contest, contest.logo.field, str(contest.logo).split("/")[-1])
    contest.save()


for contest in Aeroplane.objects.all():
    contest.picture = contest.picture.field.attr_class(contest, contest.picture.field, str(contest.picture).split("/")[-1])
    contest.save()

for contest in Team.objects.all():
    contest.logo = contest.logo.field.attr_class(contest, contest.logo.field, str(contest.logo).split("/")[-1])
    contest.save()
