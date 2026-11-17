from django.contrib import admin

from .models import Character, Conversation, Memory, Relationship


class MemoryInline(admin.TabularInline):
    model = Memory
    fk_name = 'owner'
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'accessory', 'color']
    list_editable = ['is_active']
    inlines = [MemoryInline]


@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ['a', 'b', 'score']
    list_editable = ['score']


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ['owner', 'about', 'text', 'created_at']
    list_filter = ['owner']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'score_before', 'score_after', 'model_name', 'input_tokens', 'output_tokens', 'cost_usd']
    list_filter = ['model_name']
    readonly_fields = [
        'a', 'b', 'lines', 'score_before', 'score_after',
        'model_name', 'input_tokens', 'output_tokens', 'cost_usd', 'created_at',
    ]
