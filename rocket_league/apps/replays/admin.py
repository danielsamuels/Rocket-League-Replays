from django.contrib import admin

from .models import Replay, Player, Goal, Map


class PlayerInlineAdmin(admin.StackedInline):
    model = Player
    extra = 0


class GoalInlineAdmin(admin.StackedInline):
    model = Goal
    extra = 0


class ReplayAdmin(admin.ModelAdmin):
    inlines = [PlayerInlineAdmin, GoalInlineAdmin]

admin.site.register(Replay, ReplayAdmin)
admin.site.register(Map)
