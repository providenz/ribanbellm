from django.db import models


class Character(models.Model):
    class Accessory(models.TextChoices):
        NONE = 'none', 'Aucun'
        HAT = 'hat', 'Chapeau'
        GLASSES = 'glasses', 'Lunettes'
        BOW = 'bow', 'Noeud'
        ANTENNA = 'antenna', 'Antenne'
        MUSTACHE = 'mustache', 'Moustache'
        CROWN = 'crown', 'Couronne'

    name = models.CharField(max_length=60, unique=True)
    personality = models.TextField(help_text='Short personality blurb, in French.')
    speech_quirk = models.CharField(max_length=200, help_text='Tic, catchphrase or obsession.')
    color = models.CharField(max_length=7, default='#e0604a')
    accessory = models.CharField(max_length=10, choices=Accessory, default=Accessory.NONE)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class Feeling(models.Model):
    """What `owner` feels toward `toward`. One-sided: A can be fond of B while B is lukewarm."""

    MIN_SCORE = -10
    MAX_SCORE = 10

    owner = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='feelings')
    toward = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='+')
    score = models.SmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'toward'], name='unique_feeling'),
            models.CheckConstraint(condition=~models.Q(owner=models.F('toward')), name='feeling_not_self'),
        ]

    def __str__(self):
        return f'{self.owner} -> {self.toward}: {self.score}'

    @classmethod
    def of(cls, owner: Character, toward: Character) -> Feeling:
        feeling, _ = cls.objects.get_or_create(owner=owner, toward=toward)
        return feeling

    def apply_delta(self, delta: int) -> None:
        self.score = max(self.MIN_SCORE, min(self.MAX_SCORE, self.score + delta))
        self.save(update_fields=['score'])


class Memory(models.Model):
    MAX_PER_OWNER = 8

    owner = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='memories')
    about = models.ForeignKey(
        Character, on_delete=models.CASCADE, related_name='+', null=True, blank=True
    )
    text = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.owner}: {self.text}'

    @classmethod
    def latest_for(cls, owner: Character):
        return cls.objects.filter(owner=owner).select_related('about')[: cls.MAX_PER_OWNER]

    @classmethod
    def remember(cls, owner: Character, text: str, about: Character | None = None) -> Memory:
        memory = cls.objects.create(owner=owner, about=about, text=text)
        keep = cls.objects.filter(owner=owner).values_list('pk', flat=True)[: cls.MAX_PER_OWNER]
        cls.objects.filter(owner=owner).exclude(pk__in=list(keep)).delete()
        return memory


class Conversation(models.Model):
    """Log of a conversation, for inspection in the admin."""

    a = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='+')
    b = models.ForeignKey(Character, on_delete=models.CASCADE, related_name='+')
    lines = models.JSONField()
    # a's feeling toward b, and b's toward a, before and after the conversation
    feeling_a_before = models.SmallIntegerField(default=0)
    feeling_a_after = models.SmallIntegerField(default=0)
    feeling_b_before = models.SmallIntegerField(default=0)
    feeling_b_after = models.SmallIntegerField(default=0)
    interrupted = models.BooleanField(default=False, help_text='Stopped by an LLM error: no memories or feelings applied.')
    engine = models.CharField(max_length=10, default='agents')  # older conversations may say 'director'
    error = models.TextField(blank=True, help_text='Why the conversation was interrupted.')
    model_name = models.CharField(max_length=100, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True, help_text='Empty when the model price is unknown.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.a} x {self.b} ({self.created_at:%Y-%m-%d %H:%M})'
