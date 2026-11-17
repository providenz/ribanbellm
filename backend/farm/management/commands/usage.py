from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum

from farm.models import Conversation


class Command(BaseCommand):
    help = 'Token consumption and cost of all conversations, per engine and model.'

    def handle(self, *args, **options):
        rows = (
            Conversation.objects.values('engine', 'model_name')
            .annotate(
                conversations=Count('id'),
                input_tokens=Sum('input_tokens'),
                output_tokens=Sum('output_tokens'),
                cost=Sum('cost_usd'),
                unpriced=Count('id', filter=Q(cost_usd__isnull=True)),
            )
            .order_by('engine', 'model_name')
        )
        self.stdout.write(f"{'engine':<10}{'model':<28}{'convs':>7}{'in':>10}{'out':>10}{'cost':>12}")
        for row in rows:
            if row['cost'] is None:
                cost = 'inconnu'
            else:
                cost = f"${row['cost']:.4f}" + ('*' if row['unpriced'] else '')
            self.stdout.write(
                f"{row['engine']:<10}{row['model_name'] or '?':<28}{row['conversations']:>7}"
                f"{row['input_tokens']:>10}{row['output_tokens']:>10}{cost:>12}"
            )
        if any(row['unpriced'] and row['cost'] is not None for row in rows):
            self.stdout.write('* some conversations of this engine and model have no known price')
