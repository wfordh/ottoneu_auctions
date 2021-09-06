import datetime
import json
import re
from time import sleep

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pybaseball import cache, playerid_lookup
from pybaseball.statcast_batter import (
    statcast_batter_exitvelo_barrels,
    statcast_batter_expected_stats,
    statcast_batter_percentile_ranks,
)
from pybaseball.statcast_pitcher import (
    statcast_pitcher_expected_stats,
    statcast_pitcher_percentile_ranks,
)


def get_player_page(elem, is_waiver=True):
    player_dict = dict()
    player_dict["Player Name"] = elem.find("a").get_text().strip()
    player_page_url = elem.find("a")["href"]
    player_info = elem.find("span").get_text().split()
    # don't love this indentation pattern
    if "N/A" not in player_info:
        player_dict["is_mlb"] = True
        if len(player_info) == 4:
            # either MiLB or IL
            if "IL" in player_info[3]:
                player_info.pop()
            else:
                # MiLB
                player_dict["is_mlb"] = False
                player_info.pop(1)
        player_dict["Hand"] = player_info.pop()
        player_dict["Position"] = player_info.pop()
        # odd case where Puig does not have a team but other released players do
        player_dict["Team"] = player_info.pop() if player_info else "FA"
    else:
        player_dict["is_mlb"] = True
        player_dict["Hand"] = None
        player_dict["Position"] = "UTIL"
        player_dict["Team"] = None

    bid_or_claim = elem.find_all("td")[-1].get_text()
    if is_waiver:
        player_dict["waiver_salary"] = bid_or_claim
    else:
        player_dict["min_bid"] = bid_or_claim
    player_dict["ottoneu_id"] = player_page_url.rsplit("=")[1]
    return player_dict


def get_mlbam_id(player_dict):
    if not player_dict["is_mlb"]:
        return None

    player_name = clean_name(player_dict["Player Name"])
    first_name, last_name = player_name.split(maxsplit=1)

    if "." in first_name:
        # lookup has "A.J." as "A. J." for some reason
        first_name = first_name.replace(".", ". ").strip()
    id_lookup = playerid_lookup(last_name, first_name)
    if id_lookup.shape[0] > 1:
        mlbam_id = id_lookup.loc[
            id_lookup.mlb_played_last == id_lookup.mlb_played_last.max()
        ].key_mlbam.values[0]
    elif id_lookup.shape[0] == 1:
        mlbam_id = id_lookup.key_mlbam.values[0]
    else:
        # how could this happen?
        mlbam_id = None
    return mlbam_id


def get_hitters_statcast(hitters, otto_league, is_waiver):
    if not hitters:
        return hitters  # return nothing?

    hitter_columns = [
        "Player Name",
        "Team",
        "Hand",
        "Position",
        "Hand",
        "is_mlb",
        "pts_g",
        "pa",
        f"{'waiver_salary' if is_waiver else 'min_bid'}",
        f"{otto_league.scoring_system} - Avg",
        f"{otto_league.scoring_system} - Med",
        f"{otto_league.scoring_system} - L10 Avg",
        f"{otto_league.scoring_system} - L10 Med",
        "avg_exit_velo",
        "max_exit_velo",
        "exit_velo_pctl",
        "barrel_pa_rate",
        "barrel_bbe_rate",
        "barrel_bbe_pctl",
        "xwoba",
        "woba_diff",
        "xwoba_pctl",
    ]

    exit_velo_data = statcast_batter_exitvelo_barrels(otto_league.league_year, minBBE=0)
    percentile_ranks = statcast_batter_percentile_ranks(otto_league.league_year)
    exp_stats = statcast_batter_expected_stats(otto_league.league_year, minPA=0)
    for player in hitters:
        if not player["is_mlb"] or not player["mlbam_id"]:
            # avoid index error for minor leaguers
            continue
        exit_velo = exit_velo_data.loc[
            exit_velo_data.player_id == player["mlbam_id"]
        ].to_dict("records")
        # if exit velo doesn't exist, then no statcast data for player and therefore continue?
        if not exit_velo:
            continue
        player_exit_velo = exit_velo.pop()
        # if this works, then don't need the adjustments below?
        pctl_ranks = percentile_ranks.loc[
            percentile_ranks.player_id == player["mlbam_id"]
        ].to_dict("records")
        player_pctl_ranks = pctl_ranks.pop() if pctl_ranks else None
        x_stats = exp_stats.loc[exp_stats.player_id == player["mlbam_id"]].to_dict(
            "records"
        )
        player_exp_stats = x_stats.pop() if x_stats else None
        player["avg_exit_velo"] = player_exit_velo["avg_hit_speed"]
        player["max_exit_velo"] = player_exit_velo["max_hit_speed"]
        player["exit_velo_pctl"] = safe_int(player_pctl_ranks["exit_velocity"])
        player["barrel_pa_rate"] = player_exit_velo["brl_pa"]
        player["barrel_bbe_rate"] = player_exit_velo["brl_percent"]
        player["barrel_bbe_pctl"] = safe_int(player_pctl_ranks["brl_percent"])
        player["xwoba"] = player_exp_stats["est_woba"]
        player["woba_diff"] = player_exp_stats["est_woba_minus_woba_diff"]
        player["xwoba_pctl"] = safe_int(player_pctl_ranks["xwoba"])

    return [
        {k: v for k, v in hitter.items() if k in hitter_columns} for hitter in hitters
    ]


def get_pitchers_statcast(pitchers, otto_league, is_waiver):
    # need to have somethign for waiver vs not
    if not pitchers:
        return pitchers

    pitcher_columns = [
        "Player Name",
        "Team",
        "Hand",
        "Position",
        "Hand",
        "is_mlb",
        "pts_ip",
        "ip",
        f"{'waiver_salary' if is_waiver else 'min_bid'}",
        f"{otto_league.scoring_system} - Avg",
        f"{otto_league.scoring_system} - Med",
        f"{otto_league.scoring_system} - L10 Avg",
        f"{otto_league.scoring_system} - L10 Med",
        "k_pctl",
        "bb_pctl",
        "whiff_pctl",
        "xwoba",
        "woba_diff",
        "era_diff",
    ]

    percentile_ranks = statcast_pitcher_percentile_ranks(otto_league.league_year)
    exp_stats = statcast_pitcher_expected_stats(otto_league.league_year, 0)
    for player in pitchers:
        if not player["is_mlb"] or not player["mlbam_id"]:
            continue
        pctl_ranks = percentile_ranks.loc[
            percentile_ranks.player_id == player["mlbam_id"]
        ].to_dict("records")
        # in case no statcast available
        if not pctl_ranks:
            continue
        player_pctl_ranks = pctl_ranks.pop() if pctl_ranks else None
        x_stats = exp_stats.loc[exp_stats.player_id == player["mlbam_id"]].to_dict(
            "records"
        )
        player_exp_stats = x_stats.pop() if x_stats else None

        player["k_pctl"] = safe_int(player_pctl_ranks["k_percent"])
        player["bb_pctl"] = safe_int(player_pctl_ranks["bb_percent"])
        player["whiff_pctl"] = safe_int(player_pctl_ranks["whiff_percent"])
        player["xwoba"] = player_exp_stats["est_woba"]
        player["woba_diff"] = player_exp_stats["est_woba_minus_woba_diff"]
        player["era_diff"] = player_exp_stats["era_minus_xera_diff"]

    return [
        {k: v for k, v in pitcher.items() if k in pitcher_columns}
        for pitcher in pitchers
    ]


def safe_int(data):
    try:
        data = int(data)
    except ValueError:
        pass
    return data


def dict_to_html(records):
    df = pd.DataFrame.from_records(records)
    return df.to_html().replace("\n", "")


def format_html(auction_players, waiver_players, league_id):
    auction_hitters_html = dict_to_html(auction_players[0])
    auction_pitchers_html = dict_to_html(auction_players[1])

    waiver_hitters_html = dict_to_html(waiver_players[0])
    waiver_pitchers_html = dict_to_html(waiver_players[1])
    html = f"""
    <!doctype html>
    <html>
    <body>
    <h1>Ottoneu Auctions - <a href="https://ottoneu.fangraphs.com/{league_id}/home">League {league_id}</a></h1>
    <h2> Auction Hitters </h2>
    {auction_hitters_html}
    <h2> Auction Pitchers </h2>
    {auction_pitchers_html}
    <h2> Waiver Hitters </h2>
    {waiver_hitters_html}
    <h2> Waiver Pitchers </h2>
    {waiver_pitchers_html}
    <footer><a href="https://wfordh.github.io/ottoneu_auctions">Home</a></footer>
    </body>
    </html>
    """
    return html


def get_ottoneu_player_page(player_dict, otto_league):
    sleep(1.1)
    player_page_dict = dict()
    url = f"{otto_league.league_url}/playercard"
    r = requests.get(url, params={"id": player_dict["ottoneu_id"]})
    soup = BeautifulSoup(r.content, "html.parser")
    header_data = soup.find("main").find("header", {"class": "page-header"})
    level_data = (
        header_data.find("div", {"class": "page-header__section--split"})
        .find("span", {"class": "strong tinytext"})
        .get_text()
    )

    salary_data = header_data.find("div", {"class": "page-header__secondary"})
    player_page_dict["positions"] = (
        salary_data.find("div", {"class": "page-header__section--split"})
        .find("p")
        .get_text()
        .strip()
        .rsplit(maxsplit=1)[1]
    )
    # salary_tags = [tag.get_text() for tag in salary_data.find_all("em")]
    league_points = salary_data.find_all("p")[1].find_all("strong")[1].get_text()
    points_map = {
        "FanGraphs Points": "FGP",
        "H2H FanGraphs Points": "H2H FGP",
    }
    salary_tags = [
        "All - Avg",
        "All - Med",
        f"{otto_league.scoring_system} - Avg",
        f"{otto_league.scoring_system} - Med",
        "All - Avg - L10",
        "All - Med - L10",
        f"{otto_league.scoring_system} - Avg - L10",
        f"{otto_league.scoring_system} - Med - L10",
    ]
    salary_nums = [num.get_text() for num in salary_data.find_all("span")][:-2]
    for tag, num in zip(salary_tags, salary_nums):
        player_page_dict[tag] = num

    player_stats = (
        soup.find("main").find("section", {"class": "section-container"}).find("table")
    )
    if player_dict["is_mlb"]:
        # will need to adjust for players with more than one team in year aka same as minor leaguers
        current_stats = player_stats.find_all("tr")[-1].find_all("td")
        avg_pts = current_stats[-2].get_text()
        if player_dict["is_hitter"] and not player_dict["is_pitcher"]:
            player_dict["pts_g"] = avg_pts
            player_dict["pa"] = current_stats[3].get_text()
        elif player_dict["is_pitcher"] and not player_dict["is_hitter"]:
            player_dict["pts_ip"] = avg_pts
            player_dict["ip"] = current_stats[4].get_text()
    # probably just change all references to player_page_dict to player_dict above to avoid the update
    player_dict.update(player_page_dict)
    return player_dict


def clean_name(player_name):
    name_suffixes = ("jr", "sr", "ii", "iii", "iv", "v")
    # might not want this at all for MLB names
    player_name = re.sub(r"(['])", "", player_name.lower())
    player_name = (
        player_name.rsplit(maxsplit=1)[0]
        if player_name.endswith(name_suffixes)
        else player_name
    )
    return player_name


def get_position_group(positions):
    # turn this into a dict?
    is_hitter = False
    is_pitcher = False
    if "/" in positions:
        if all(["P" in pos for pos in positions.split("/")]):
            is_pitcher = True
        elif any(["P" in pos for pos in positions.split("/")]):
            is_pitcher = True
            is_hitter = True
        else:
            is_hitter = True
    else:
        if "P" in positions:
            is_pitcher = True
        else:
            is_hitter = True
    return is_hitter, is_pitcher
