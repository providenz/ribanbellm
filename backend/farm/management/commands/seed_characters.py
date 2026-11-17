from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from farm import llm
from farm.generation import generate_characters
from farm.models import Character

A = Character.Accessory

CHARACTERS = [
    {
        'name': 'Agent Roucoule',
        'personality': "Pigeon persuadé d'être un agent secret infiltré. Voit des complots partout, surtout chez les miettes de pain.",
        'speech_quirk': 'Parle en codes absurdes ("Le croissant est dans le four") et termine par "Cette conversation n\'a jamais eu lieu."',
        'color': '#8a94a6',
        'accessory': A.GLASSES,
    },
    {
        'name': 'Madame Vibrato',
        'personality': "Ancienne diva d'opéra à la retraite. Tout est tragédie, chaque contrariété mérite un acte entier.",
        'speech_quirk': 'Chante certains mots en les étirant ("Quelle horreuuuur") et cite ses triomphes à la Scala.',
        'color': '#b04a8c',
        'accessory': A.CROWN,
    },
    {
        'name': 'Grillon',
        'personality': "Grille-pain philosophe. Se demande sans cesse si une tartine brûlée a encore un sens.",
        'speech_quirk': 'Pose des questions existentielles et cite des philosophes qui n\'existent pas.',
        'color': '#c9c2b8',
        'accessory': A.NONE,
    },
    {
        'name': 'Colonel Patate',
        'personality': "Pomme de terre militaire à la retraite, très à cheval sur la discipline et les horaires.",
        'speech_quirk': 'Aboie des ordres, appelle tout le monde "soldat" et compte en heures militaires.',
        'color': '#b08a4a',
        'accessory': A.MUSTACHE,
    },
    {
        'name': 'Zigzag',
        'personality': "Escargot hyperactif qui se croit le plus rapide du monde. Toujours en retard, toujours fier.",
        'speech_quirk': 'Parle très vite, sans ponctuation, et invente des records ("Record battu!").',
        'color': '#7ab04a',
        'accessory': A.ANTENNA,
    },
    {
        'name': 'Mamie Tricot',
        'personality': "Grand-mère adorable mais redoutable commère. Sait tout sur tout le monde et le répète.",
        'speech_quirk': 'Commence par "Oh mon petit..." et glisse toujours un ragot "entre nous".',
        'color': '#e0a0b0',
        'accessory': A.GLASSES,
    },
    {
        'name': 'Bip-Bop',
        'personality': "Petit robot qui essaie désespérément de comprendre l'humour humain, sans succès.",
        'speech_quirk': 'Annonce ses émotions ("ÉMOTION: VEXÉ") et rit au mauvais moment ("HA. HA. HA.").',
        'color': '#4a9ae0',
        'accessory': A.ANTENNA,
    },
    {
        'name': 'Baron Fromage',
        'personality': "Camembert aristocrate, snob et très fier de son odeur, qu'il considère comme un parfum.",
        'speech_quirk': 'Vouvoie tout le monde, soupire "Quelle vulgarité" et parle de ses ancêtres normands.',
        'color': '#f0e0a0',
        'accessory': A.HAT,
    },
    {
        'name': 'Lulu la Licorne',
        'personality': "Licorne influenceuse obsédée par son image et ses abonnés imaginaires.",
        'speech_quirk': 'Dit "trop mignon", "on se fait un selfie?" et compte ses likes à voix haute.',
        'color': '#d0a0f0',
        'accessory': A.BOW,
    },
    {
        'name': 'Gérard',
        'personality': "Caillou très calme. Ne fait rien, ne veut rien, mais a un avis tranché sur tout.",
        'speech_quirk': 'Répond en très peu de mots ("Bof.", "Non.") puis lâche soudain une vérité implacable.',
        'color': '#6e6a66',
        'accessory': A.NONE,
    },
]


class Command(BaseCommand):
    help = 'Create or update the starter cast of characters, or add new ones invented by the LLM (--llm).'

    def add_arguments(self, parser):
        parser.add_argument('--llm', action='store_true', help='Ask the LLM to invent new characters.')
        parser.add_argument('--count', type=int, help='How many characters to invent with --llm (1 to 10, default 5).')

    def handle(self, *args, **options):
        if options['llm']:
            return self.invent(options['count'] or 5)
        if options['count'] is not None:
            raise CommandError('--count only works with --llm.')
        for data in CHARACTERS:
            _, created = Character.objects.update_or_create(name=data['name'], defaults=data)
            self.stdout.write(f"{'created' if created else 'updated'}: {data['name']}")

    def invent(self, count: int) -> None:
        if not 1 <= count <= 10:
            raise CommandError('--count must be between 1 and 10.')
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
