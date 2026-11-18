from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from farm import llm
from farm.generation import generate_characters
from farm.models import Character


class Command(BaseCommand):
    help = 'Invent new characters with the LLM and add them to the farm.'

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=5, help='How many characters to invent (1 to 10, default 5).')
        parser.add_argument('--if-empty', action='store_true', help='Do nothing if the farm already has characters.')

    def handle(self, *args, **options):
        count = options['count']
        if not 1 <= count <= 10:
            raise CommandError('--count must be between 1 and 10.')
        if options['if_empty'] and Character.objects.exists():
            self.stdout.write('The farm already has characters, none invented.')
            return
        try:
            model = llm.build_model()
        except ImproperlyConfigured as exc:
            raise CommandError(str(exc)) from exc
        existing = list(Character.objects.values_list('name', flat=True))
        ideas = generate_characters(count, model=model, existing=existing)
        for data in ideas:
            Character.objects.create(**data)
            self.stdout.write(f"created: {data['name']}")
        if len(ideas) < count:
            self.stdout.write(f'Only {len(ideas)} of {count} were new; the others had taken names.')
