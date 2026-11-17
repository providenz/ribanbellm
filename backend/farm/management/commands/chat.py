import random

from django.core.management.base import BaseCommand, CommandError

from farm import conversations
from farm.models import Character, Conversation


class Command(BaseCommand):
    help = 'Make two characters meet and print their conversation (random pair if names are omitted).'

    def add_arguments(self, parser):
        parser.add_argument('names', nargs='*', help='Two character names, e.g. "Gérard" "Grillon"')

    def handle(self, *args, names, **options):
        a, b = self._pick(names)
        self.stdout.write(self.style.MIGRATE_HEADING(f'{a.name} croise {b.name}...\n'))

        for event in conversations.stream(a, b):
            if event['type'] == 'line':
                self.stdout.write(f"{self.style.SUCCESS(event['speaker'])}: {event['text']}  ({event['emotion']})")
            elif event['type'] == 'error':
                self.stdout.write(self.style.ERROR(f"Conversation interrompue: {event['message']}"))
            elif event['type'] == 'end':
                self._summary(a, b, Conversation.objects.get(pk=event['conversation_id']))

    def _summary(self, a: Character, b: Character, conversation: Conversation) -> None:
        self.stdout.write('')
        for character in (a, b):
            self.stdout.write(f'{character.name} retient: {character.memories.first().text}')
        self.stdout.write(f'{a.name} -> {b.name}: {conversation.feeling_a_before} -> {conversation.feeling_a_after}')
        self.stdout.write(f'{b.name} -> {a.name}: {conversation.feeling_b_before} -> {conversation.feeling_b_after}')
        cost = 'coût inconnu' if conversation.cost_usd is None else f'coût ${conversation.cost_usd:.4f}'
        self.stdout.write(
            f'Tokens: {conversation.input_tokens} in / {conversation.output_tokens} out'
            f' ({conversation.engine}, {conversation.model_name}, {cost})'
        )

    def _pick(self, names: list[str]) -> tuple[Character, Character]:
        active = Character.objects.filter(is_active=True)
        if not names:
            pool = list(active)
            if len(pool) < 2:
                raise CommandError('Need at least 2 active characters (run seed_characters).')
            return tuple(random.sample(pool, 2))
        if len(names) != 2:
            raise CommandError('Give exactly two names, or none for a random pair.')
        found = []
        for name in names:
            character = active.filter(name__iexact=name).first()
            if character is None:
                raise CommandError(f'Unknown or inactive character: {name}')
            found.append(character)
        if found[0] == found[1]:
            raise CommandError('Pick two different characters.')
        return found[0], found[1]
