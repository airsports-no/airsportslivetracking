from django.core.management.base import BaseCommand
from display.models import MyUser
from django.db.models import Count

class Command(BaseCommand):
    help = 'Displays the status of the authentication migration from Django to Firebase.'

    def handle(self, *args, **options):
        total_users = MyUser.objects.count()
        # Users with usable passwords are NOT migrated
        unmigrated_users = [u for u in MyUser.objects.all() if not u.is_migrated]
        migrated_users_count = total_users - len(unmigrated_users)
        
        self.stdout.write(self.style.SUCCESS('--- Authentication Migration Status ---'))
        self.stdout.write(f'Total Users in Database: {total_users}')
        self.stdout.write(self.style.SUCCESS(f'Migrated to Firebase:   {migrated_users_count}'))
        self.stdout.write(self.style.WARNING(f'Remaining in Django:    {len(unmigrated_users)}'))
        
        if total_users > 0:
            percentage = (migrated_users_count / total_users) * 100
            self.stdout.write(f'Migration Progress:      {percentage:.2f}%')
        
        if len(unmigrated_users) > 0 and len(unmigrated_users) < 20:
            self.stdout.write('\nUnmigrated Users:')
            for user in unmigrated_users:
                self.stdout.write(f' - {user.email}')
        elif len(unmigrated_users) >= 20:
            self.stdout.write('\n(List of unmigrated users hidden due to volume)')
