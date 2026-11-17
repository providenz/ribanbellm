import pytest

from farm.models import Character, Memory, Relationship

pytestmark = pytest.mark.django_db


def make(name):
    return Character.objects.create(name=name, personality='p', speech_quirk='q')


def test_relationship_between_is_symmetric():
    a, b = make('Alice'), make('Bob')

    first = Relationship.between(b, a)
    second = Relationship.between(a, b)

    assert first.pk == second.pk
    assert first.score == 0
    assert Relationship.objects.count() == 1


def test_relationship_apply_delta_clamps_to_bounds():
    rel = Relationship.between(make('Alice'), make('Bob'))

    rel.apply_delta(25)
    assert rel.score == Relationship.MAX_SCORE

    rel.apply_delta(-100)
    assert rel.score == Relationship.MIN_SCORE

    rel.refresh_from_db()
    assert rel.score == Relationship.MIN_SCORE


def test_remember_keeps_only_latest_memories():
    alice, bob = make('Alice'), make('Bob')

    for i in range(Memory.MAX_PER_OWNER + 3):
        Memory.remember(owner=alice, about=bob, text=f'souvenir {i}')

    texts = list(Memory.latest_for(alice).values_list('text', flat=True))
    assert len(texts) == Memory.MAX_PER_OWNER
    assert texts[0] == f'souvenir {Memory.MAX_PER_OWNER + 2}'  # newest first
    assert 'souvenir 0' not in texts
