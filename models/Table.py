from dataclasses import dataclass
from datetime import datetime
import dateutil.parser
import urllib
from models.Players import PlayerBasic

@dataclass
class TableScore:
    gp_scores: list[int]
    score: int
    multiplier: float
    prev_mmr: int | None
    new_mmr: int | None
    delta: int | None
    player: PlayerBasic
    is_peak: bool = False

    @classmethod
    def from_name_score(cls, name: str, gp_scores: list[int]):
        player = PlayerBasic(0, name, None, None)
        return cls(gp_scores, sum(gp_scores), 1.0, None, None, None, player)
    
    def set_score(self, gp_scores: list[int]):
        self.gp_scores = gp_scores
        self.score = sum(gp_scores)

@dataclass
class TableTeam:
    rank: int
    scores: list[TableScore]

    def get_team_score(self):
        return sum([s.score for s in self.scores])
    
    def __lt__(self, other):
        return self.get_team_score() < other.get_team_score()
    
    def __eq__(self, other):
        return self.get_team_score == other.get_team_score()

@dataclass
class TableBasic:
    size: int
    tier: str
    teams: list[TableTeam]
    author_id: int | None
    parsed_date: datetime | None

    # converts the table into the correct format for the table submission endpoint
    def to_submission_format(self):
        scores = []
        for i, team in enumerate(self.teams):
            for score in team.scores:
                score_body = {
                    "playerName": score.player.name,
                    "team": i,
                }
                if len(score.gp_scores) > 1:
                    score_body["scores"] = score.gp_scores
                else:
                    score_body["score"] = score.score
                scores.append(score_body)

        body = {
            "tier": self.tier,
            "scores": scores,
            "authorId": str(self.author_id)
        }
        if self.parsed_date:
            body["date"] = self.parsed_date.isoformat()
        return body
    
    def score_total(self):
        return sum([team.get_team_score() for team in self.teams])
    
    def get_team(self, name: str) -> TableTeam:
        stripped_name = name.strip().lower()
        for team in self.teams:
            for score in team.scores:
                if score.player.name.lower() == stripped_name:
                    return team
        return None
    
    def get_score(self, name: str) -> TableScore:
        stripped_name = name.strip().lower()
        for team in self.teams:
            for score in team.scores:
                if score.player.name.lower() == stripped_name:
                    return score
        return None
    
    def get_score_from_discord(self, discord_id: int) -> TableScore:
        for team in self.teams:
            for score in team.scores:
                if int(score.player.discord_id) == discord_id:
                    return score
        return None
    
    def get_lorenzi_url(self):
        base_url_lorenzi = "https://gb.hlorenzi.com/table.png?data="
        table_text = f"Tier {self.tier} {'FFA #4A82D0' if self.size == 1 else f'{self.size}v{self.size}'}\n"
        if self.parsed_date:
            table_text += f"#date {self.parsed_date}\n"
        team_colors = ["#1D6ADE", "#4A82D0"]
        for i, team in enumerate(self.teams):
            if self.size > 1:
                table_text += f"{team.rank} {team_colors[i % len(team_colors)]}\n"
            for score in team.scores:
                gp_string = '|'.join(str(gp) for gp in score.gp_scores)
                table_text += f"{score.player.name} {gp_string}\n"
        url_table_text = urllib.parse.quote(table_text)
        image_url = base_url_lorenzi + url_table_text
        return image_url
    
    @classmethod
    def from_text(cls, size: int, tier: str, names: list[str], gp_scores: list[list[int]], author_id: int, date: datetime | None):
        teams: list[TableTeam] = []
        for i in range(0, len(names), size):
            team_scores = []
            for j in range(i, i+size):
                team_scores.append(TableScore.from_name_score(names[j], gp_scores[j]))
            teams.append(TableTeam(0, team_scores))
        teams.sort(reverse=True)
        for i in range(len(teams)):
            if i > 0 and teams[i] == teams[i-1]:
                teams[i] = teams[i-1].rank
            else:
                teams[i].rank = i+1
        table = cls(size, tier.upper(), teams, author_id, date)
        return table

@dataclass
class Table(TableBasic):
    id: int
    season: int
    created_on: datetime
    verified_on: datetime | None
    deleted_on: datetime | None
    table_message_id: int | None
    update_message_id: int | None

    def get_table_image_url(self):
        return f"/TableImage/{self.id}.png"

    @classmethod
    def from_api_response(cls, body):
        id = body["id"]
        season = body["season"]
        def parse_date(field_name: str):
            if field_name in body:
                return dateutil.parser.isoparse(body[field_name])
            else:
                return None
        created_on = parse_date("createdOn")
        verified_on = parse_date("verifiedOn")
        deleted_on = parse_date("deletedOn")
        table_message_id = None
        if "tableMessageId" in body:
            table_message_id = int(body["tableMessageId"])
        update_message_id = None
        if "updateMessageId" in body:
            update_message_id = int(body["updateMessageId"])
        author_id = int(body["authorId"])
        
        tier = body["tier"]
        teams: list[TableTeam] = []
        num_players = 0
        for t in body["teams"]:
            rank = t["rank"]
            scores: list[TableScore] = []
            for s in t["scores"]:
                num_players += 1
                player = PlayerBasic(s["playerId"], s["playerName"], 
                                     s.get("playerDiscordId", None), s.get("playerCountryCode", None))
                prev_mmr = s.get("prevMmr", None)
                new_mmr = s.get("newMmr", None)
                delta = s.get("delta", None)
                if "score" in s:
                    gp_scores: list[int] = [s["score"]]
                else:
                    gp_scores: list[int] = s["scores"]
                multiplier = s["multiplier"]
                is_peak = s.get("isNewPeakMmr", False)
                scores.append(TableScore(gp_scores, sum(gp_scores), multiplier, prev_mmr, new_mmr,
                                         delta, player, is_peak))
            scores.sort(key=lambda s: s.score, reverse=True)
            teams.append(TableTeam(rank, scores))
        size = int(num_players / body["numTeams"])
        table = cls(size, tier, teams, author_id, None, id, season, created_on, verified_on,
                    deleted_on, table_message_id, update_message_id)
        return table
    
    @classmethod
    def from_list_api_response(cls, body:list):
        tables: list[Table] = []
        for t in body:
            tables.append(Table.from_api_response(t))
        return tables

