from django.core.management.base import BaseCommand
from django.db import transaction

from farm.models import Conversation, Feeling, Memory


class Command(BaseCommand):
    help = 'Erase what the farm has lived (conversations, memories, feelings). Characters are kept.'

    def add_arguments(self, parser):
        parser.add_argument('--yes', action='store_true', help='Do not ask for confirmation.')

    def handle(self, *args, **options):
        if not options['yes'] and input('Erase all conversations, memories and feelings? [y/N] ').lower() != 'y':
            self.stdout.write('Nothing erased.')
            return
        with transaction.atomic():
            counts = {label: model.objects.all().delete()[0] for label, model in (
                ('conversation(s)', Conversation), ('memory(ies)', Memory), ('feeling(s)', Feeling)
            )}
        self.stdout.write('Erased: ' + ', '.join(f'{n} {label}' for label, n in counts.items()))
