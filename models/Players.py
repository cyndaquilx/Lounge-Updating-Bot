from dataclasses import dataclass
from datetime import datetime
import dateutil.parser
import msgspec

@dataclass
class PlayerBasic:
    id: int
    name: str
    discord_id: str | None
    country_code: str | None

@dataclass
class Player(PlayerBasic):
    mkc_id: int | None
    registry_id: int | None
    fc: str | None
    is_hidden: bool
    mmr: int | None
    peak_mmr: int | None

    @classmethod
    def from_api_response(cls, body: dict, detailed=False):
        if detailed:
            id = body['playerId']
        else:
            id = body['id']
        name = body['name']
        discord_id = body.get('discordId', None)
        if discord_id is not None:
            discord_id = str(discord_id)
        country_code = body.get('countryCode', None)
        mkc_id = body.get('mkcId', None)
        registry_id = body.get('registryId', None)
        fc = body.get('switchFc', None)
        is_hidden = body['isHidden']
        mmr = body.get('mmr', None)
        peak_mmr = body.get('maxMmr', None)
        player = cls(id, name, discord_id, country_code, mkc_id, registry_id, fc, is_hidden, mmr, peak_mmr)
        return player
    
@dataclass
class PlayerMMRChange:
    id: int | None
    new_mmr: int
    delta: int
    reason: str
    time: datetime
    score: int | None
    partner_scores: list[int] | None
    partner_ids: list[int] | None
    rank: int | None
    tier: str | None
    num_teams: int | None

    @classmethod
    def from_api_response(cls, body: dict):
        id = body.get('id', None)
        new_mmr = body['newMmr']
        delta = body['mmrDelta']
        reason = body['reason']
        def parse_date(field_name: str):
            return dateutil.parser.isoparse(body[field_name])
        time = parse_date('time')
        score = body.get('score', None)
        partner_scores = body.get('partnerScores', None)
        partner_ids = body.get('partnerIds', None)
        rank = body.get('rank', None)
        tier = body.get('tier', None)
        num_teams = body.get('numTeams', None)
        mmr_change = cls(id, new_mmr, delta, reason, time, score, partner_scores, partner_ids, rank, tier, num_teams)
        return mmr_change

    
@dataclass
class PlayerStats:
    season: int
    rank: int
    events_played: int
    win_rate: float | None
    wins_last_10: int | None
    losses_last_10: int | None
    gain_loss_last_10: int | None
    largest_gain: int | None
    largest_gain_table_id: int | None
    largest_loss: int | None
    largest_loss_table_id: int | None
    average_score: float | None
    average_score_no_sq: float | None
    average_last_10: float | None
    partner_average: float | None
    partner_average_no_sq: float | None
    mmr_changes: list[PlayerMMRChange]

    @classmethod
    def from_api_response(cls, body: dict):
        season = body['season']
        rank = body['overallRank']
        events_played = body['eventsPlayed']
        win_rate = body.get('winRate', None)
        wins_last_10 = body.get('winsLastTen', None)
        losses_last_10 = body.get('lossesLastTen', None)
        gain_loss_last_10 = body.get('gainLossLastTen', None)
        largest_gain = body.get('largestGain', None)
        largest_gain_table_id = body.get('largestGainTableId', None)
        largest_loss = body.get('largestLoss', None)
        largest_loss_table_id = body.get('largestLossTableId', None)
        average_score = body.get('averageScore', None)
        average_score_no_sq = body.get('noSQAverageScore', None)
        average_last_10 = body.get('averageLastTen', None)
        partner_average = body.get('partnerAverage', None)
        partner_average_no_sq = body.get('noSQPartnerAverage', None)
        mmr_changes: list[PlayerMMRChange] = []
        mmr_changes_resp: list = body['mmrChanges']
        for change in mmr_changes_resp:
            mmr_changes.append(PlayerMMRChange.from_api_response(change))
        stats = cls(season, rank, events_played, win_rate, wins_last_10, losses_last_10,
                    gain_loss_last_10, largest_gain, largest_gain_table_id, largest_loss,
                    largest_loss_table_id, average_score, average_score_no_sq,
                    average_last_10, partner_average, partner_average_no_sq, mmr_changes)
        return stats

@dataclass
class PlayerNameChange:
    name: str
    changed_on: datetime

    @classmethod
    def from_api_response(cls, body: dict):
        name = body['name']
        def parse_date(field_name: str):
            return dateutil.parser.isoparse(body[field_name])
        changed_on = parse_date('changedOn')
        change = cls(name, changed_on)
        return change

@dataclass
class PlayerDetailed(Player):
    stats: PlayerStats
    name_history: list[PlayerNameChange]

    @classmethod
    def from_api_response(cls, body):
        data = Player.from_api_response(body, detailed=True)
        stats = PlayerStats.from_api_response(body)
        name_history: list[PlayerNameChange] = []
        name_resp: list = body['nameHistory']
        for change in name_resp:
            name_history.append(PlayerNameChange.from_api_response(change))
        player = cls(data.id, data.name, data.discord_id, data.country_code,
                     data.mkc_id, data.registry_id, data.fc, data.is_hidden, 
                     data.mmr, data.peak_mmr, stats, name_history)
        return player
    
@dataclass
class ListPlayer:
    name: str
    mkc_id: int | None
    mmr: int | None
    discord_id: int | None
    events_played: int
    
    @classmethod
    def from_api_response(cls, body: dict):
        name = body.get('name')
        mkc_id = body.get('mkcId', None)
        mmr = body.get('mmr', None)
        discord_id = body.get('discordId', None)
        events_played = body.get('eventsPlayed', 0)
        return cls(str(name), mkc_id, mmr, discord_id, int(events_played))
    
    @classmethod
    def from_list_api_response(cls, body: dict):
        player_list: list[ListPlayer] = []
        players: list[dict] = body['players']
        for player in players:
            player_list.append(ListPlayer.from_api_response(player))
        return player_list

@dataclass
class PlayerPlacement:
    name: str
    mmr: int