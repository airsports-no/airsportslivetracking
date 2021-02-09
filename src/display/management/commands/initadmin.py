from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from live_tracking_map import settings


class Command(BaseCommand):

    def handle(self, *args, **options):
        if get_user_model().objects.count() == 0:
            for user in settings.ADMINS:
                email = user[1]
                password = 'admin'
                print('Creating account for %s ' % ( email))
                admin = get_user_model().objects.create_superuser(email=email, password=password)
                admin.save()
        else:
            print('Admin accounts can only be initialized if no Accounts exist')
