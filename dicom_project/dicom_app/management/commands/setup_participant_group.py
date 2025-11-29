from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Creates the Participante group'

    def handle(self, *args, **options):
        group, created = Group.objects.get_or_create(name='Participante')
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created group "Participante"'))
        else:
            self.stdout.write(self.style.SUCCESS('Group "Participante" already exists'))
