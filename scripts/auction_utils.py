import datetime
import re
from time import sleep
import pandas as pd
import requests
from bs4 import BeautifulSoup
import json


def get_league_scoring(league_id):
    scoring_map = {
        "FanGraphs Points": "FGP",
        "H2H FanGraphs Points": "H2H FGP",
    }
    url = f"https://ottoneu.fangraphs.com/{league_id}/settings"
    r = requests.get(url)
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


def safe_int(data):
    try:
        data = int(data)
    except ValueError:
        pass
    return data


def dict_to_html(records):
    df = pd.DataFrame.from_records(records)
    return df.to_html().replace("\n", "")


def format_html(hitters, pitchers, league_id):
    hitters_html = dict_to_html(hitters)
    pitchers_html = dict_to_html(pitchers)
    html = f"""
    <!doctype html>
    <html>
    <body>
    <h1>Ottoneu Auctions - <a href="https://ottoneu.fangraphs.com/{league_id}/home">League {league_id}</a></h1>
    <h2> Hitters </h2>
    {hitters_html}
    <h2> Pitchers </h2>
    {pitchers_html}
    <footer><a href="https://wfordh.github.io/ottoneu_auctions">Home</a></footer>
    </body>
    </html>
    """
    return html


def get_ottoneu_player_page(player_id, lg_id, lg_scoring):
    sleep(1.1)
    player_page_dict = dict()
    today = datetime.date.today()
    if today.month < 4:
        current_year = today.year - 1
    else:
        current_year = today.year
    url = f"https://ottoneu.fangraphs.com/{lg_id}/playercard"
    r = requests.get(url, params={"id": player_id})
    soup = BeautifulSoup(r.content, "html.parser")
    header_data = soup.find("main").find("header", {"class": "page-header"})
    level_data = (
        header_data.find("div", {"class": "page-header__section--split"})
        .find("span", {"class": "strong tinytext"})
        .get_text()
    )
    if "(" in level_data or len(level_data.split()) == 2:
        player_page_dict["is_mlb"] = False
    else:
        latest_year = int(
            soup.find("main")
            .find("section", {"class": "section-container"})
            .find("table")
            .find_all("tr")[-1]
            .find("td")
            .get_text()
        )
        player_page_dict["is_mlb"] = True if latest_year == current_year else False
    # player_page_dict["is_mlb"] = False if "(" in level_data else True
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
        f"{lg_scoring} - Avg",
        f"{lg_scoring} - Med",
        "All - Avg - L10",
        "All - Med - L10",
        f"{lg_scoring} - Avg - L10",
        f"{lg_scoring} - Med - L10",
    ]
    salary_nums = [num.get_text() for num in salary_data.find_all("span")][:-2]
    for tag, num in zip(salary_tags, salary_nums):
        player_page_dict[tag] = num

    player_stats = soup.find("main").find("section", {"class":"section-container"}).find("table")
    if player_page_dict["is_mlb"]:
        player_page_dict["avg_pts"] = player_stats.find_all("tr")[-1].find_all("td")[-2].get_text()
    return player_page_dict


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
