from django.contrib import admin

from .models import Character, Conversation, Feeling, Memory


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


@admin.register(Feeling)
class FeelingAdmin(admin.ModelAdmin):
    list_display = ['owner', 'toward', 'score']
    list_editable = ['score']
    list_filter = ['owner']


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ['owner', 'about', 'text', 'created_at']
    list_filter = ['owner']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        '__str__', 'engine', 'interrupted', 'feeling_a_before', 'feeling_a_after', 'feeling_b_before', 'feeling_b_after',
        'model_name', 'input_tokens', 'output_tokens', 'cost_usd',
    ]
    list_filter = ['engine', 'model_name', 'interrupted']
    readonly_fields = [
        'a', 'b', 'lines', 'engine', 'interrupted', 'error',
        'feeling_a_before', 'feeling_a_after', 'feeling_b_before', 'feeling_b_after',
        'model_name', 'input_tokens', 'output_tokens', 'cost_usd', 'created_at',
    ]
