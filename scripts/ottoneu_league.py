from datetime import date

import requests
from bs4 import BeautifulSoup


# @dataclass
class ottoneuLeague:
    """docstring for ottoneuLeague"""

    def __init__(self, league_id):
        self.league_id = league_id
        self.scoring_system = None
        self.league_year = None
        self.league_url = f"https://ottoneu.fangraphs.com/{league_id}"
        self.auction_url = f"{self.league_url}/auctions"
        self.waivers_url = f"{self.league_url}/waiverclaim"

    def _get_league_year(self):
        today = date.today()
        league_year = today.year - 1 if today.month < 4 else today.year
        return league_year

    def _get_scoring_system(self):
        # need to add 5x5
        scoring_map = {
            "FanGraphs Points": "FGP",
            "H2H FanGraphs Points": "H2H FGP",
        }
        r = requests.get(f"{self.league_url}/settings")
        soup = BeautifulSoup(r.content, "html.parser")
        rows = soup.find("main").find("table").find_all("tr")[1:]
        settings = {
            row.find_all("td")[0]
            .get_text()
            .strip(): row.find_all("td")[1]
            .get_text()
            .strip()
            for row in rows
        }
        scoring_system = settings.get("Scoring System")
        return scoring_map.get(scoring_system)

    def setup_league_params(self):
        self.scoring_system = self._get_scoring_system()
        self.league_year = self._get_league_year()

    def get_players(self, is_waiver):
        url = self.waivers_url if is_waiver else self.auction_url
        resp = requests.get(url)
        soup = BeautifulSoup(resp.content, "html.parser")
        players = (
            soup.find("main")
            .find("section")
            .find("div", {"class": "table-container"})
            .find("table")
            .find_all("tr")
        )
        # pop the headers off
        players.pop(0)
        return players
