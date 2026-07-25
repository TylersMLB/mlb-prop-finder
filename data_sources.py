
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st
from constants import STADIUMS

CENTRAL = ZoneInfo("America/Chicago")

def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

@st.cache_data(ttl=300)
def mlb_schedule(date_string):
    response = requests.get(
        "https://statsapi.mlb.com/api/v1/schedule",
        params={
            "sportId": 1,
            "date": date_string,
            "hydrate": "probablePitcher,team,venue",
        },
        timeout=20,
    )
    response.raise_for_status()
    rows = []
    for day in response.json().get("dates", []):
        for game in day.get("games", []):
            away = game["teams"]["away"]["team"]
            home = game["teams"]["home"]["team"]
            start_iso = game.get("gameDate", "")
            try:
                start_ct = datetime.fromisoformat(start_iso.replace("Z", "+00:00")).astimezone(CENTRAL)
                start_label = start_ct.strftime("%-I:%M %p CT")
            except Exception:
                start_ct = None
                start_label = start_iso
            rows.append({
                "GamePk": game.get("gamePk"),
                "Game": f"{away['name']} @ {home['name']}",
                "AwayTeam": away["name"], "AwayID": away["id"],
                "HomeTeam": home["name"], "HomeID": home["id"],
                "StartISO": start_iso, "StartCT": start_ct, "Start": start_label,
                "Status": game.get("status", {}).get("detailedState", ""),
                "Venue": game.get("venue", {}).get("name", STADIUMS.get(home["name"], (0,0,"Unknown"))[2]),
                "AwayPitcher": game["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD"),
                "AwayPitcherID": game["teams"]["away"].get("probablePitcher", {}).get("id"),
                "HomePitcher": game["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD"),
                "HomePitcherID": game["teams"]["home"].get("probablePitcher", {}).get("id"),
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=900)
def standings(season):
    response = requests.get(
        "https://statsapi.mlb.com/api/v1/standings",
        params={"leagueId": "103,104", "season": season, "standingsTypes": "regularSeason"},
        timeout=20,
    )
    response.raise_for_status()
    rows = []
    for group in response.json().get("records", []):
        for team in group.get("teamRecords", []):
            wins = int(team.get("wins", 0))
            losses = int(team.get("losses", 0))
            games = max(1, wins + losses)
            rows.append({
                "TeamID": team["team"]["id"], "Team": team["team"]["name"],
                "Wins": wins, "Losses": losses, "Games": games,
                "WinPct": wins / games, "RunDiff": int(team.get("runDifferential", 0)),
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=1800)
def pitcher_stats(person_id, season):
    blank = {"ERA": None, "WHIP": None, "K9": None, "BB9": None, "IP": 0.0}
    if not person_id:
        return blank
    try:
        response = requests.get(
            f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats",
            params={"stats": "season", "group": "pitching", "season": season},
            timeout=15,
        )
        response.raise_for_status()
        splits = response.json().get("stats", [{}])[0].get("splits", [])
        if not splits:
            return blank
        stat = splits[0].get("stat", {})
        return {
            "ERA": _num(stat.get("era")), "WHIP": _num(stat.get("whip")),
            "K9": _num(stat.get("strikeoutsPer9Inn")),
            "BB9": _num(stat.get("walksPer9Inn")),
            "IP": _num(stat.get("inningsPitched")) or 0.0,
        }
    except Exception:
        return blank

@st.cache_data(ttl=180)
def sportsbook_odds(api_key, region):
    response = requests.get(
        "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/",
        params={
            "apiKey": api_key, "regions": region,
            "markets": "h2h,spreads,totals", "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json(), response.headers.get("x-requests-remaining")

def flatten_odds(raw):
    rows = []
    for event in raw:
        game = f"{event.get('away_team')} @ {event.get('home_team')}"
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "Game": game, "Book": book.get("title", ""),
                        "Market": market.get("key", ""), "Selection": outcome.get("name", ""),
                        "Line": outcome.get("point"), "Odds": outcome.get("price"),
                    })
    return pd.DataFrame(rows)

@st.cache_data(ttl=900)
def weather_forecast(home_team, game_start_iso):
    stadium = STADIUMS.get(home_team)
    if not stadium or not game_start_iso:
        return None
    lat, lon, venue = stadium
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,wind_speed_10m,wind_direction_10m",
        "temperature_unit": "fahrenheit", "wind_speed_unit": "mph",
        "timezone": "America/Chicago", "forecast_days": 16,
    }
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get("hourly", {})
        target = datetime.fromisoformat(game_start_iso.replace("Z", "+00:00")).astimezone(CENTRAL)
        times = [datetime.fromisoformat(t).replace(tzinfo=CENTRAL) for t in data.get("time", [])]
        if not times:
            return None
        idx = min(range(len(times)), key=lambda i: abs((times[i] - target).total_seconds()))
        return {
            "Venue": venue,
            "Temperature": data["temperature_2m"][idx],
            "Humidity": data["relative_humidity_2m"][idx],
            "RainChance": data["precipitation_probability"][idx],
            "WindSpeed": data["wind_speed_10m"][idx],
            "WindDirection": data["wind_direction_10m"][idx],
        }
    except Exception:
        return None
