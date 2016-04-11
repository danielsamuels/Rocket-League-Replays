from .models import Goal, Map, Player, Replay, Season

from rest_framework.serializers import HyperlinkedModelSerializer, ReadOnlyField


class GoalSerializer(HyperlinkedModelSerializer):

    goal_time = ReadOnlyField()

    player_id = ReadOnlyField()

    class Meta:
        model = Goal


class PlayerSerializer(HyperlinkedModelSerializer):

    id = ReadOnlyField()

    class Meta:
        model = Player
        exclude = ['replay']


class MapSerializer(HyperlinkedModelSerializer):

    class Meta:
        model = Map


class SeasonSerializer(HyperlinkedModelSerializer):

    class Meta:
        model = Season


class ReplaySerializer(HyperlinkedModelSerializer):

    id = ReadOnlyField()

    goal_set = GoalSerializer(
        many=True,
        read_only=True,
    )

    player_set = PlayerSerializer(
        many=True,
        read_only=True,
    )

    map = MapSerializer(
        many=False,
        read_only=True,
    )

    season = SeasonSerializer(
        many=False,
        read_only=True,
    )

    class Meta:
        model = Replay
        exclude = ['user', 'crashed_heatmap_parser']
        depth = 1


class ReplayCreateSerializer(HyperlinkedModelSerializer):

    def validate(self, attrs):
        instance = Replay(**attrs)
        instance.clean()
        return attrs

    class Meta:
        model = Replay
        fields = ['file', 'url', 'get_absolute_url']
        depth = 0
