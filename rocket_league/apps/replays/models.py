import re
from itertools import zip_longest

import bitstring
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.timezone import now
from social.apps.django_app.default.fields import JSONField

from pyrope import Replay as Pyrope
from .parser import parse_replay_header, parse_replay_netstream

PRIVACY_PRIVATE = 1
PRIVACY_UNLISTED = 2
PRIVACY_PUBLIC = 3

PLATFORM_STEAM = 1
PLATFORM_PSN = 2

PLATFORMS = {
    'Steam': PLATFORM_STEAM,
    'PlayStation': PLATFORM_PSN,
}


class Season(models.Model):

    title = models.CharField(
        max_length=100,
        unique=True,
    )

    start_date = models.DateTimeField()

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-start_date']


def get_default_season():
    if Season.objects.count() == 0:
        season = Season.objects.create(
            title='Season 1',
            start_date='2015-07-07'  # Game release date
        )

        return season.pk

    return Season.objects.filter(
        start_date__lte=now(),
    )[0].pk


class Map(models.Model):

    title = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    slug = models.CharField(
        max_length=100,
    )

    image = models.FileField(
        upload_to='uploads/files',
        blank=True,
        null=True,
    )

    def __str__(self):
        return self.title or self.slug

    class Meta:
        ordering = ['title']


class Replay(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        db_index=True,
    )

    season = models.ForeignKey(
        Season,
        default=get_default_season,
    )

    title = models.CharField(
        "replay name",
        max_length=64,
        blank=True,
        null=True,
    )

    playlist = models.PositiveIntegerField(
        choices=[(v, k) for k, v in settings.PLAYLISTS.items()],
        default=0,
        blank=True,
        null=True,
    )

    file = models.FileField(
        upload_to='uploads/replay_files',
    )

    heatmap_json_file = models.FileField(
        upload_to='uploads/replay_json_files',
        blank=True,
        null=True,
    )

    location_json_file = models.FileField(
        upload_to='uploads/replay_location_json_files',
        blank=True,
        null=True,
    )

    replay_id = models.CharField(
        "replay ID",
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    player_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    player_team = models.IntegerField(
        default=0,
        blank=True,
        null=True,
    )

    map = models.ForeignKey(
        Map,
        blank=True,
        null=True,
        db_index=True,
    )

    server_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    timestamp = models.DateTimeField(
        blank=True,
        null=True,
    )

    date_created = models.DateTimeField(
        default=now,
    )

    team_sizes = models.PositiveIntegerField(
        blank=True,
        null=True,
        db_index=True,
    )

    team_0_score = models.IntegerField(
        default=0,
        blank=True,
        null=True,
        db_index=True,
    )

    team_1_score = models.IntegerField(
        default=0,
        blank=True,
        null=True,
        db_index=True,
    )

    match_type = models.CharField(
        max_length=7,
        blank=True,
        null=True,
    )

    privacy = models.PositiveIntegerField(
        'replay privacy',
        choices=[
            (PRIVACY_PRIVATE, 'Private'),
            (PRIVACY_UNLISTED, 'Unlisted'),
            (PRIVACY_PUBLIC, 'Public')
        ],
        default=3,
    )

    # Parser V2 values.
    keyframe_delay = models.FloatField(
        blank=True,
        null=True,
    )

    max_channels = models.IntegerField(
        default=1023,
        blank=True,
        null=True,
    )

    max_replay_size_mb = models.IntegerField(
        "max replay size (MB)",
        default=10,
        blank=True,
        null=True,
    )

    num_frames = models.IntegerField(
        blank=True,
        null=True,
    )

    record_fps = models.FloatField(
        "record FPS",
        default=30.0,
        blank=True,
        null=True,
    )

    shot_data = JSONField(
        blank=True,
        null=True,
    )

    excitement_factor = models.FloatField(
        default=0.00,
    )

    show_leaderboard = models.BooleanField(
        default=False,
    )

    average_rating = models.PositiveIntegerField(
        blank=True,
        null=True,
        default=0,
    )

    crashed_heatmap_parser = models.BooleanField(
        default=False,
    )

    processed = models.BooleanField(
        default=False,
    )

    @cached_property
    def uuid(self):
        return re.sub(r'([A-F0-9]{8})(4[A-F0-9]{3})([A-F0-9]{4})([A-F0-9]{4})([A-F0-9]{12})', r'\1-\2-\3-\4-\5', self.replay_id).lower()

    def team_x_player_list(self, team):
        return [
            "{}{}".format(
                player.player_name,
                " ({})".format(player.goal_set.count()) if player.goal_set.count() > 0 else '',
            ) for player in self.player_set.filter(
                team=team,
            )
        ]

    def team_x_players(self, team):
        return ', '.join(self.team_x_player_list(team))

    def team_0_players(self):
        return self.team_x_players(0)

    def team_1_players(self):
        return self.team_x_players(1)

    def team_0_player_list(self):
        return self.team_x_player_list(0)

    def team_1_player_list(self):
        return self.team_x_player_list(1)

    def player_pairs(self):
        return zip_longest(self.team_0_player_list(), self.team_1_player_list())

    @cached_property
    def region(self):
        if not self.server_name:
            return 'N/A'

        match = re.search(settings.SERVER_REGEX, self.server_name).groups()
        return match[1]

    def lag_report_url(self):
        base_url = 'https://psyonixhr.wufoo.com/forms/game-server-performance-report'
        if not self.server_name:
            return base_url

        # Split out the server name.
        match = re.search(r'(EU|USE|USW|OCE|SAM)(\d+)(-([A-Z][a-z]+))?', self.server_name).groups()

        return "{}/def/field1={}&field2={}&field13={}".format(
            base_url,
            *match
        )

    @cached_property
    def match_length(self):
        if not self.num_frames or not self.record_fps:
            return 'N/A'

        calculation = self.num_frames / self.record_fps
        minutes, seconds = divmod(calculation, 60)
        return '%d:%02d' % (
            int(minutes),
            int(seconds),
        )

    def calculate_excitement_factor(self):
        # Multiplers for use in factor tweaking.
        swing_rating_multiplier = 8
        goal_count_multiplier = 1.2

        # Calculate how the swing changed throughout the game.
        swing = 0
        swing_values = []

        for goal in self.goal_set.all():
            if goal.player.team == 0:
                swing -= 1
            else:
                swing += 1

            swing_values.append(swing)

        if self.team_0_score > self.team_1_score:
            # Team 0 won, but were they ever losing?
            deficit_values = [x for x in swing_values if x < 0]

            if deficit_values:
                deficit = max(swing_values)
            else:
                deficit = 0

            score_min_def = self.team_0_score - deficit
        else:
            # Team 1 won, but were they ever losing?
            deficit_values = [x for x in swing_values if x < 0]

            if deficit_values:
                deficit = abs(min(deficit_values))
            else:
                deficit = 0

            score_min_def = self.team_1_score - deficit

        if score_min_def != 0:
            swing_rating = float(deficit) / score_min_def * swing_rating_multiplier
        else:
            swing_rating = 0

        # Now we have the swing rating, adjust it by the total number of goals.
        # This gives us a "base value" for each replay and allows replays with
        # lots of goals but not much swing to get reasonable rating.
        swing_rating += (self.team_0_score + self.team_1_score) * goal_count_multiplier

        # Decay the score based on the number of days since the game was played.
        # This should keep the replay list fresh. Cap at a set number of days.
        days_ago = (now().date() - self.timestamp.date()).days

        day_cap = 75

        if days_ago > day_cap:
            days_ago = day_cap

        # Make sure we're not dividing by zero.
        if days_ago > 0:
            days_ago = float(days_ago)
            swing_rating -= swing_rating * days_ago / 100

        return swing_rating

    def calculate_average_rating(self):
        from ..users.models import LeagueRating

        players = self.player_set.filter(
            platform__in=['OnlinePlatform_Steam', '1'],
        ).exclude(
            online_id__isnull=True,
        )

        team_sizes = self.player_set.count() / 2

        num_player_ratings = 0
        total_player_ratings = 0

        get_season = Season.objects.filter(
            start_date__lte=self.timestamp,
        )

        for player in players:
            # Get the latest rating for this player.
            ratings = LeagueRating.objects.filter(
                steamid=player.online_id,
                season_id=get_season[0].pk if get_season else get_default_season()
            )

            if self.playlist:
                if self.playlist == settings.PLAYLISTS['RankedDuels']:
                    ratings = ratings.exclude(duels=0)
                elif self.playlist == settings.PLAYLISTS['RankedDoubles']:
                    ratings = ratings.exclude(doubles=0)
                elif self.playlist == settings.PLAYLISTS['RankedSoloStandard']:
                    ratings = ratings.exclude(solo_standard=0)
                elif self.playlist == settings.PLAYLISTS['RankedStandard']:
                    ratings = ratings.exclude(standard=0)
            else:
                if team_sizes == 1:
                    ratings = ratings.exclude(duels=0)
                elif team_sizes == 2:
                    ratings = ratings.exclude(doubles=0)
                elif team_sizes == 3:
                    ratings = ratings.exclude(solo_standard=0, standard=0)

                ratings = ratings[:1]

            if len(ratings) > 0:
                rating = ratings[0]
            else:
                continue

            if self.playlist:
                if self.playlist == settings.PLAYLISTS['RankedDuels'] and rating.duels > 0:  # Duels
                    total_player_ratings += rating.duels
                    num_player_ratings += 1
                elif self.playlist == settings.PLAYLISTS['RankedDoubles'] and rating.doubles > 0:  # Doubles
                    total_player_ratings += rating.doubles
                    num_player_ratings += 1
                elif self.playlist == settings.PLAYLISTS['RankedSoloStandard'] and rating.solo_standard > 0:
                    total_player_ratings += rating.solo_standard
                    num_player_ratings += 1
                elif self.playlist == settings.PLAYLISTS['RankedStandard'] and rating.standard > 0:
                    total_player_ratings += rating.standard
                    num_player_ratings += 1
            else:
                if team_sizes == 1 and rating.duels > 0:  # Duels
                    total_player_ratings += rating.duels
                    num_player_ratings += 1
                elif team_sizes == 2 and rating.doubles > 0:  # Doubles
                    total_player_ratings += rating.doubles
                    num_player_ratings += 1
                elif team_sizes == 3 and (rating.solo_standard > 0 or rating.standard > 0):  # Standard or Solo Standard (can't tell which)
                    if rating.solo_standard > 0 and rating.standard <= 0:
                        total_player_ratings += rating.solo_standard
                    elif rating.standard > 0 and rating.solo_standard <= 0:
                        total_player_ratings += rating.standard
                    else:
                        total_player_ratings += (rating.solo_standard + rating.standard) / 2
                    num_player_ratings += 1

        if num_player_ratings > 0:
            return total_player_ratings / num_player_ratings
        return 0

    def eligible_for_feature(self, feature):
        features = {
            'playback': 300,
            'boost_analysis': 1000,
        }

        patreon_amount = features[feature]

        # Import here to avoid circular imports.
        from ..site.templatetags.site import patreon_pledge_amount

        # Is the uploader a patron?
        if self.user:
            pledge_amount = patreon_pledge_amount({}, user=self.user)

            if pledge_amount >= patreon_amount:
                return True

        # Are any of the players patron?
        players = self.player_set.filter(
            platform__in=['OnlinePlatform_Steam', '1'],
        )

        for player in players:
            pledge_amount = patreon_pledge_amount({}, steam_id=player.online_id)

            if pledge_amount >= patreon_amount:
                return True

        return False

    @property
    def queue_priority(self):
        # Returns one of 'tournament', 'priority', 'general', where 'tournament'
        # is the highest priority.

        # TODO: Add tournament logic.

        if self.eligible_for_playback:
            return 'priority'

        return 'general'

    # Feature eligibility checks.
    @cached_property
    def eligible_for_playback(self):
        return self.eligible_for_feature('playback')

    @cached_property
    def show_playback(self):
        # First of all, is there even a JSON file?
        if not self.location_json_file:
            return False

        return self.eligible_for_feature('playback')

    @cached_property
    def eligible_for_boost_analysis(self):
        return self.eligible_for_feature('boost_analysis')

    @cached_property
    def show_boost_analysis(self):
        # Have we got any boost data yet?
        if self.boostdata_set.count() == 0:
            return False

        return self.eligible_for_feature('boost_analysis')

    # Other stuff
    @cached_property
    def get_human_playlist(self):
        if not self.playlist:
            return None

        return settings.HUMAN_PLAYLISTS.get(self.playlist, self.get_playlist_display())

    def get_absolute_url(self):
        return reverse('replay:detail', kwargs={
            'replay_id': re.sub(r'([A-F0-9]{8})(4[A-F0-9]{3})([A-F0-9]{4})([A-F0-9]{4})([A-F0-9]{12})', r'\1-\2-\3-\4-\5', self.replay_id).lower(),
        })

    class Meta:
        ordering = ['-timestamp', '-pk']

    def __str__(self):
        return self.title or str(self.pk) or '[{}] {} {} game on {}. Final score: {}, Uploaded by {}.'.format(
            self.timestamp,
            '{size}v{size}'.format(size=self.team_sizes),
            self.match_type,
            self.map,
            '{}-{}'.format(self.team_0_score, self.team_1_score),
            self.player_name,
        )

    def clean(self):
        if self.pk:
            return

        if self.file:
            # Ensure we're at the start of the file as `clean()` can sometimes
            # be called multiple times (for some reason..)
            self.file.seek(0)

            try:
                replay = Pyrope(self.file.read())
            except bitstring.ReadError:
                raise ValidationError("The file you selected does not seem to be a valid replay file.")

            # Check if this replay has already been uploaded.
            replays = Replay.objects.filter(
                replay_id=replay.header['Id'],
            )

            if replays.count() > 0:
                raise ValidationError(mark_safe("This replay has already been uploaded, <a target='_blank' href='{}'>you can view it here</a>.".format(
                    replays[0].get_absolute_url()
                )))

            self.replay_id = replay.header['Id']

    def save(self, *args, **kwargs):
        parse_netstream = False

        if 'parse_netstream' in kwargs:
            parse_netstream = kwargs.pop('parse_netstream')

        super(Replay, self).save(*args, **kwargs)

        if self.file and not self.processed:
            if parse_netstream:
                # Header parse?
                parse_replay_netstream(self.pk)
            else:
                parse_replay_header(self.pk)


class Player(models.Model):

    replay = models.ForeignKey(
        Replay,
    )

    player_name = models.CharField(
        max_length=100,
        db_index=True,
    )

    team = models.IntegerField()

    # 1.06 data
    score = models.PositiveIntegerField(
        default=0,
        blank=True,
    )

    goals = models.PositiveIntegerField(
        default=0,
        blank=True,
    )

    shots = models.PositiveIntegerField(
        default=0,
        blank=True,
    )

    assists = models.PositiveIntegerField(
        default=0,
        blank=True,
    )

    saves = models.PositiveIntegerField(
        default=0,
        blank=True,
    )

    platform = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    online_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        db_index=True,
    )

    bot = models.BooleanField(
        default=False,
    )

    spectator = models.BooleanField(
        default=False,
    )

    heatmap = models.FileField(
        upload_to='uploads/heatmap_files',
        blank=True,
        null=True,
    )

    user_entered = models.BooleanField(
        default=False,
    )

    # Taken from the netstream.
    actor_id = models.PositiveIntegerField(
        default=0,
        blank=True,
        null=True,
    )

    unique_id = models.CharField(
        max_length=128,
        blank=True,
        null=True,
    )

    party_leader = models.ForeignKey(
        'self',
        blank=True,
        null=True,
    )

    camera_settings = JSONField(
        blank=True,
        null=True,
    )

    vehicle_loadout = JSONField(
        blank=True,
        null=True,
    )

    total_xp = models.PositiveIntegerField(
        default=0,
        blank=True,
        null=True,
    )

    # Other stuff.
    boost_data = JSONField(
        blank=True,
        null=True,
    )

    @cached_property
    def vehicle_data(self):
        if not self.vehicle_loadout:
            return {}

        if 'Body' in self.vehicle_loadout:
            return self.vehicle_loadout

        return {
            'body': Body.objects.get_or_create(id=self.vehicle_loadout[0])[0]
        }

    def __str__(self):
        return '{} on Team {}'.format(
            self.player_name,
            self.team,
        )

    class Meta:
        ordering = ('team', '-score', 'player_name')
        unique_together = [('unique_id', 'replay')]


class Goal(models.Model):

    replay = models.ForeignKey(
        Replay,
        db_index=True,
    )

    # Goal 1, 2, 3 etc..
    number = models.PositiveIntegerField()

    player = models.ForeignKey(
        Player,
        db_index=True,
    )

    frame = models.IntegerField(
        blank=True,
        null=True,
    )

    @cached_property
    def goal_time(self):
        if not self.frame or not self.replay.record_fps:
            return 'N/A'

        calculation = self.frame / self.replay.record_fps
        minutes, seconds = divmod(calculation, 60)
        return '%d:%02d' % (
            int(minutes),
            int(seconds),
        )

    def __str__(self):
        return 'Goal {} by {}'.format(
            self.number,
            self.player,
        )

    class Meta:
        ordering = ['number']


class ReplayPack(models.Model):

    title = models.CharField(
        max_length=50,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        db_index=True,
    )

    replays = models.ManyToManyField(
        Replay,
        blank=True,
    )

    file = models.FileField(
        upload_to='uploads/replaypack_files',
        blank=True,
        null=True,
    )

    date_created = models.DateTimeField(
        auto_now_add=True,
    )

    last_updated = models.DateTimeField(
        auto_now=True,
    )

    @cached_property
    def maps(self):
        maps = Map.objects.filter(
            id__in=set(self.replays.values_list('map_id', flat=True))
        ).values_list('title', flat=True)

        return ', '.join(maps)

    @cached_property
    def goals(self):
        if not self.replays.count():
            return 0
        return self.replays.aggregate(
            num_goals=models.Sum(models.F('team_0_score') + models.F('team_1_score'))
        )['num_goals']

    @cached_property
    def players(self):
        return set(Player.objects.filter(
            replay_id__in=self.replays.values_list('id', flat=True),
        ).values_list('player_name', flat=True))

    @cached_property
    def total_duration(self):
        calculation = 0

        if self.replays.count():
            calculation = self.replays.aggregate(models.Sum('num_frames'))['num_frames__sum'] / 30

        minutes, seconds = divmod(calculation, 60)
        hours, minutes = divmod(minutes, 60)

        return '{} {}m {}s'.format(
            '{}h'.format(int(hours)) if hours > 0 else '',
            int(minutes),
            int(seconds),
        )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('replaypack:detail', kwargs={
            'pk': self.pk,
        })

    class Meta:
        ordering = ['-last_updated', '-date_created']


class BoostData(models.Model):

    replay = models.ForeignKey(
        Replay,
        db_index=True,
    )

    player = models.ForeignKey(
        Player,
    )

    frame = models.PositiveIntegerField()

    value = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(255)]
    )

    class Meta:
        ordering = ['player', 'frame']
        # unique_together = [('player', 'frame', 'value')]


class Body(models.Model):

    id = models.PositiveIntegerField(
        unique=True,
        db_index=True,
        primary_key=True,
    )

    name = models.CharField(
        max_length=100,
        default='Unknown',
    )
