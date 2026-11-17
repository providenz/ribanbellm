from django.db import migrations, models
import django.db.models.deletion


def copy_scores(apps, schema_editor):
    """Each shared pair score becomes the same score in both directions."""
    Relationship = apps.get_model('farm', 'Relationship')
    Feeling = apps.get_model('farm', 'Feeling')
    Conversation = apps.get_model('farm', 'Conversation')
    for rel in Relationship.objects.all():
        Feeling.objects.create(owner_id=rel.a_id, toward_id=rel.b_id, score=rel.score)
        Feeling.objects.create(owner_id=rel.b_id, toward_id=rel.a_id, score=rel.score)
    for conv in Conversation.objects.all():
        conv.feeling_a_before = conv.feeling_b_before = conv.score_before
        conv.feeling_a_after = conv.feeling_b_after = conv.score_after
        conv.save(update_fields=['feeling_a_before', 'feeling_b_before', 'feeling_a_after', 'feeling_b_after'])


class Migration(migrations.Migration):
    dependencies = [('farm', '0002_conversation_usage')]

    operations = [
        migrations.CreateModel(
            name='Feeling',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.SmallIntegerField(default=0)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feelings', to='farm.character')),
                ('toward', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='farm.character')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('owner', 'toward'), name='unique_feeling'),
                    models.CheckConstraint(condition=models.Q(('owner', models.F('toward')), _negated=True), name='feeling_not_self'),
                ],
            },
        ),
        migrations.AddField('conversation', 'feeling_a_before', models.SmallIntegerField(default=0)),
        migrations.AddField('conversation', 'feeling_a_after', models.SmallIntegerField(default=0)),
        migrations.AddField('conversation', 'feeling_b_before', models.SmallIntegerField(default=0)),
        migrations.AddField('conversation', 'feeling_b_after', models.SmallIntegerField(default=0)),
        migrations.AddField(
            'conversation', 'interrupted',
            models.BooleanField(default=False, help_text='Stopped by an LLM error: no memories or feelings applied.'),
        ),
        migrations.AddField('conversation', 'engine', models.CharField(default='director', max_length=10)),
        migrations.RunPython(copy_scores, migrations.RunPython.noop),
        migrations.RemoveField('conversation', 'score_before'),
        migrations.RemoveField('conversation', 'score_after'),
        migrations.DeleteModel('Relationship'),
    ]
