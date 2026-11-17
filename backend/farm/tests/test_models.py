import pytest
from pydantic import BaseModel

from farm.common import LenientEmotion, ShortText, feeling_label
from farm.models import Character, Feeling, Memory

pytestmark = pytest.mark.django_db


def make(name):
    return Character.objects.create(name=name, personality='p', speech_quirk='q')


def test_feeling_is_one_sided():
    a, b = make('Alice'), make('Bob')

    Feeling.of(a, b).apply_delta(3)

    assert Feeling.of(a, b).score == 3
    assert Feeling.of(b, a).score == 0
    assert Feeling.objects.count() == 2


def test_feeling_apply_delta_clamps_to_bounds():
    feeling = Feeling.of(make('Alice'), make('Bob'))

    feeling.apply_delta(50)
    assert feeling.score == Feeling.MAX_SCORE

    feeling.apply_delta(-50)
    assert feeling.score == Feeling.MIN_SCORE

    feeling.refresh_from_db()
    assert feeling.score == Feeling.MIN_SCORE


def test_feeling_labels_are_soft():
    labels = [feeling_label(score) for score in range(Feeling.MIN_SCORE, Feeling.MAX_SCORE + 1)]

    assert labels[0] == "pas vraiment sur la même longueur d'onde"
    assert labels[-1] == 'meilleur ami'
    assert not any(word in ' '.join(labels) for word in ('ennemi', 'supporte', 'déteste'))


def test_lenient_schema_trims_text_and_defaults_unknown_emotion():
    class Probe(BaseModel):
        text: ShortText
        emotion: LenientEmotion

    probe = Probe(text='x' * 300, emotion='furious')

    assert len(probe.text) == 200
    assert probe.emotion == 'neutral'
    assert Probe(text='ok', emotion='annoyed').emotion == 'annoyed'


def test_remember_keeps_only_latest_memories():
    alice, bob = make('Alice'), make('Bob')

    for i in range(Memory.MAX_PER_OWNER + 3):
        Memory.remember(owner=alice, about=bob, text=f'souvenir {i}')

    texts = list(Memory.latest_for(alice).values_list('text', flat=True))
    assert len(texts) == Memory.MAX_PER_OWNER
    assert texts[0] == f'souvenir {Memory.MAX_PER_OWNER + 2}'  # newest first
    assert 'souvenir 0' not in texts
