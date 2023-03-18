from display.models import Person, MyUser

print(MyUser.objects.all().count())
print(Person.objects.all().count())
duplicates = {}
for person in Person.objects.all():
    try:
        duplicates[person.email].append(person)
    except KeyError:
        duplicates[person.email] = [person]

for email, people in duplicates.items():
    if len(people) > 1:
        print(f"{email}: {','.join([f'{item.pk} {item}' for item in people])}")
