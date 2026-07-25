# Diamond Edge Pro V8.3 — single-file deployment
# All project logic is intentionally kept in this file to avoid module import errors.

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import math
import pandas as pd
import requests
import streamlit as st



# ---------------- Constants ----------------

STADIUMS = {
    "Arizona Diamondbacks": (33.4455, -112.0667, "Chase Field"),
    "Atlanta Braves": (33.8908, -84.4677, "Truist Park"),
    "Baltimore Orioles": (39.2838, -76.6217, "Oriole Park"),
    "Boston Red Sox": (42.3467, -71.0972, "Fenway Park"),
    "Chicago Cubs": (41.9484, -87.6553, "Wrigley Field"),
    "Chicago White Sox": (41.8300, -87.6338, "Rate Field"),
    "Cincinnati Reds": (39.0979, -84.5082, "Great American Ball Park"),
    "Cleveland Guardians": (41.4962, -81.6852, "Progressive Field"),
    "Colorado Rockies": (39.7559, -104.9942, "Coors Field"),
    "Detroit Tigers": (42.3390, -83.0485, "Comerica Park"),
    "Houston Astros": (29.7573, -95.3555, "Daikin Park"),
    "Kansas City Royals": (39.0517, -94.4803, "Kauffman Stadium"),
    "Los Angeles Angels": (33.8003, -117.8827, "Angel Stadium"),
    "Los Angeles Dodgers": (34.0739, -118.2400, "Dodger Stadium"),
    "Miami Marlins": (25.7781, -80.2197, "loanDepot park"),
    "Milwaukee Brewers": (43.0280, -87.9712, "American Family Field"),
    "Minnesota Twins": (44.9817, -93.2776, "Target Field"),
    "New York Mets": (40.7571, -73.8458, "Citi Field"),
    "New York Yankees": (40.8296, -73.9262, "Yankee Stadium"),
    "Athletics": (38.5802, -121.4997, "Sutter Health Park"),
    "Philadelphia Phillies": (39.9061, -75.1665, "Citizens Bank Park"),
    "Pittsburgh Pirates": (40.4469, -80.0057, "PNC Park"),
    "San Diego Padres": (32.7076, -117.1570, "Petco Park"),
    "San Francisco Giants": (37.7786, -122.3893, "Oracle Park"),
    "Seattle Mariners": (47.5914, -122.3325, "T-Mobile Park"),
    "St. Louis Cardinals": (38.6226, -90.1928, "Busch Stadium"),
    "Tampa Bay Rays": (27.7682, -82.6534, "George M. Steinbrenner Field"),
    "Texas Rangers": (32.7473, -97.0847, "Globe Life Field"),
    "Toronto Blue Jays": (43.6414, -79.3894, "Rogers Centre"),
    "Washington Nationals": (38.8730, -77.0074, "Nationals Park"),
}

PARK_RUN_FACTOR = {
    "Colorado Rockies": 1.12, "Boston Red Sox": 1.06, "Cincinnati Reds": 1.05,
    "Philadelphia Phillies": 1.04, "Chicago Cubs": 1.03, "Texas Rangers": 1.02,
    "New York Yankees": 1.02, "Arizona Diamondbacks": 1.01, "Houston Astros": 1.01,
    "Atlanta Braves": 1.01, "Kansas City Royals": 1.00, "Minnesota Twins": 1.00,
    "Milwaukee Brewers": 1.00, "Los Angeles Angels": 1.00, "Baltimore Orioles": 1.00,
    "Chicago White Sox": .99, "Cleveland Guardians": .99, "Detroit Tigers": .99,
    "Los Angeles Dodgers": .99, "St. Louis Cardinals": .99, "Washington Nationals": .99,
    "Toronto Blue Jays": .99, "Pittsburgh Pirates": .98, "Miami Marlins": .98,
    "New York Mets": .98, "Seattle Mariners": .97, "San Francisco Giants": .96,
    "San Diego Padres": .96, "Tampa Bay Rays": .98, "Athletics": 1.01,
}

# ---------------- Data sources ----------------






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
        timeout=25,
    )
    response.raise_for_status()
    return response.json(), {
        "remaining": response.headers.get("x-requests-remaining"),
        "used": response.headers.get("x-requests-used"),
        "last": response.headers.get("x-requests-last"),
    }

def flatten_odds(raw):
    rows = []
    for event in raw:
        game = f"{event.get('away_team')} @ {event.get('home_team')}"
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "EventID": event.get("id"), "Game": game,
                        "CommenceTime": event.get("commence_time"),
                        "BookKey": book.get("key", ""), "Book": book.get("title", ""),
                        "BookLink": book.get("link", ""),
                        "Market": market.get("key", ""), "Selection": outcome.get("name", ""),
                        "Description": outcome.get("description", ""),
                        "Line": outcome.get("point"), "Odds": outcome.get("price"),
                        "LastUpdate": market.get("last_update", book.get("last_update", "")),
                    })
    return pd.DataFrame(rows)

MLB_PROP_MARKETS = {
    "Pitcher Strikeouts": "pitcher_strikeouts",
    "Pitcher Outs": "pitcher_outs",
    "Pitcher Hits Allowed": "pitcher_hits_allowed",
    "Pitcher Walks": "pitcher_walks",
    "Pitcher Earned Runs": "pitcher_earned_runs",
    "Pitcher Win": "pitcher_record_a_win",
    "Batter Total Bases": "batter_total_bases",
    "Batter Hits": "batter_hits",
    "Batter Home Runs": "batter_home_runs",
    "Batter RBIs": "batter_rbis",
    "Batter Runs": "batter_runs_scored",
    "Hits + Runs + RBIs": "batter_hits_runs_rbis",
    "Batter Walks": "batter_walks",
    "Batter Strikeouts": "batter_strikeouts",
    "Batter Singles": "batter_singles",
    "Batter Doubles": "batter_doubles",
    "Batter Triples": "batter_triples",
    "Stolen Bases": "batter_stolen_bases",
}

@st.cache_data(ttl=180, show_spinner=False)
def event_prop_odds(api_key, event_id, region, market_keys):
    if not event_id or not market_keys:
        return {}, {}
    response = requests.get(
        f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds",
        params={
            "apiKey": api_key,
            "regions": region,
            "markets": ",".join(market_keys),
            "oddsFormat": "american",
            "dateFormat": "iso",
        },
        timeout=35,
    )
    response.raise_for_status()
    return response.json(), {
        "remaining": response.headers.get("x-requests-remaining"),
        "used": response.headers.get("x-requests-used"),
        "last": response.headers.get("x-requests-last"),
    }

def flatten_props(events):
    rows = []
    for event in events:
        if not event:
            continue
        game = f"{event.get('away_team')} @ {event.get('home_team')}"
        for book in event.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "EventID": event.get("id"), "Game": game,
                        "CommenceTime": event.get("commence_time"),
                        "BookKey": book.get("key", ""), "Book": book.get("title", ""),
                        "BookLink": book.get("link", ""),
                        "Market": market.get("key", ""),
                        "Player": outcome.get("description", ""),
                        "Side": outcome.get("name", ""),
                        "Line": outcome.get("point"),
                        "Odds": outcome.get("price"),
                        "LastUpdate": market.get("last_update", book.get("last_update", "")),
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

# ---------------- Models ----------------



def clamp(x, low, high):
    return max(low, min(high, x))

def logistic(x):
    return 1 / (1 + math.exp(-x))

def logit(p):
    p = clamp(float(p), .01, .99)
    return math.log(p / (1-p))

def implied_probability(odds):
    odds = float(odds)
    return 100/(odds+100) if odds > 0 else abs(odds)/(abs(odds)+100)

def decimal_odds(odds):
    return 1 + odds/100 if odds > 0 else 1 + 100/abs(odds)

def expected_value(prob, odds, stake=100):
    d = decimal_odds(float(odds))
    return stake * (prob*(d-1) - (1-prob))

def fair_odds(prob):
    prob = clamp(prob, .01, .99)
    return -round(100*prob/(1-prob)) if prob >= .5 else round(100*(1-prob)/prob)

def team_strength(row):
    rd_per_game = float(row.RunDiff) / max(1, float(row.Games))
    return logit(row.WinPct) + .11 * rd_per_game

def pitcher_adjustment(stats):
    if stats["ERA"] is None or stats["IP"] < 5:
        return 0.0
    era = (4.30 - stats["ERA"]) * .085
    whip = 0 if stats["WHIP"] is None else (1.30 - stats["WHIP"]) * .20
    strikeouts = 0 if stats["K9"] is None else (stats["K9"] - 8.5) * .018
    walks = 0 if stats["BB9"] is None else (3.2 - stats["BB9"]) * .015
    return clamp(era + whip + strikeouts + walks, -.50, .50)

def weather_run_adjustment(weather):
    if not weather:
        return 0.0
    adjustment = 0.0
    temp = weather["Temperature"]
    wind = weather["WindSpeed"]
    if temp >= 85: adjustment += .10
    elif temp <= 50: adjustment -= .10
    if wind >= 15: adjustment += .05
    return adjustment

def build_game_models(schedule, standings, season):
    rows = []
    for _, game in schedule.iterrows():
        away_row = standings[standings.TeamID == game.AwayID]
        home_row = standings[standings.TeamID == game.HomeID]
        if away_row.empty or home_row.empty:
            continue
        away = away_row.iloc[0]
        home = home_row.iloc[0]
        away_pitch = pitcher_stats(game.AwayPitcherID, season)
        home_pitch = pitcher_stats(game.HomePitcherID, season)
        weather = weather_forecast(game.HomeTeam, game.StartISO)

        away_power = team_strength(away) + pitcher_adjustment(away_pitch)
        home_power = team_strength(home) + pitcher_adjustment(home_pitch) + .13
        home_prob = logistic(home_power - away_power)
        away_prob = 1 - home_prob

        park = PARK_RUN_FACTOR.get(game.HomeTeam, 1.0)
        projected_total = 8.6 * park + weather_run_adjustment(weather)
        projected_total += clamp((4.30-(away_pitch["ERA"] or 4.30)) * -.18, -.45, .45)
        projected_total += clamp((4.30-(home_pitch["ERA"] or 4.30)) * -.18, -.45, .45)

        rows.append({
            **game.to_dict(),
            "AwayProb": away_prob, "HomeProb": home_prob,
            "AwayFair": fair_odds(away_prob), "HomeFair": fair_odds(home_prob),
            "AwayERA": away_pitch["ERA"], "HomeERA": home_pitch["ERA"],
            "AwayK9": away_pitch["K9"], "HomeK9": home_pitch["K9"],
            "AwayWinPct": away.WinPct, "HomeWinPct": home.WinPct,
            "AwayRunDiff": away.RunDiff, "HomeRunDiff": home.RunDiff,
            "ProjectedTotal": round(projected_total, 1),
            "ParkFactor": park, "Weather": weather,
        })
    return pd.DataFrame(rows)

def grade(edge):
    if edge >= 7: return "A"
    if edge >= 4: return "B"
    if edge >= 1.5: return "C"
    return "PASS"

def best_price_rows(odds, market):
    frame = odds[odds.Market == market].copy()
    if frame.empty:
        return frame
    keys = ["Game", "Selection"]
    if market in ("spreads", "totals"):
        keys.append("Line")
    idx = frame.groupby(keys, dropna=False)["Odds"].idxmax()
    return frame.loc[idx].reset_index(drop=True)

def value_board(models, odds):
    if models.empty or odds.empty:
        return pd.DataFrame()
    prices = best_price_rows(odds, "h2h")
    rows = []
    for _, game in models.iterrows():
        for side in ("Away", "Home"):
            team = game[f"{side}Team"]
            prob = game[f"{side}Prob"]
            match = prices[(prices.Game == game.Game) & (prices.Selection == team)]
            if match.empty:
                continue
            best = match.iloc[0]
            edge = (prob - implied_probability(best.Odds)) * 100
            rows.append({
                "Game": game.Game, "Start": game.Start, "Pick": team,
                "Odds": int(best.Odds), "Book": best.Book,
                "ModelProb": prob, "FairOdds": game[f"{side}Fair"],
                "Edge": edge, "EV": expected_value(prob, best.Odds),
                "Grade": grade(edge), "Score": int(clamp(round(50 + edge*5), 1, 99)),
                "Reason": f"Model {prob*100:.1f}% vs market break-even {implied_probability(best.Odds)*100:.1f}%.",
            })
    return pd.DataFrame(rows).sort_values(["Edge", "EV"], ascending=False)


def no_vig_probability(over_odds, under_odds, side):
    over_raw = implied_probability(over_odds)
    under_raw = implied_probability(under_odds)
    total = over_raw + under_raw
    if total <= 0:
        return None
    return over_raw / total if side == "Over" else under_raw / total

def prop_best_prices(props):
    """Best sportsbook price for each exact player/market/side/line."""
    if props.empty:
        return props
    clean = props.dropna(subset=["Player", "Side", "Odds"]).copy()
    idx = clean.groupby(["Game","Market","Player","Side","Line"], dropna=False)["Odds"].idxmax()
    return clean.loc[idx].reset_index(drop=True)

def prop_value_board(props):
    """
    Market-consensus ranking, not a proprietary performance projection.
    Compares each best price to a no-vig consensus derived from paired Over/Under prices.
    """
    if props.empty:
        return pd.DataFrame()
    best = prop_best_prices(props)
    rows = []
    group_cols = ["Game","Market","Player","Line"]
    for keys, group in props.groupby(group_cols, dropna=False):
        over = group[group.Side=="Over"]
        under = group[group.Side=="Under"]
        if over.empty or under.empty:
            continue
        over_consensus = over.Odds.apply(implied_probability).median()
        under_consensus = under.Odds.apply(implied_probability).median()
        total = over_consensus + under_consensus
        if total <= 0:
            continue
        consensus = {"Over": over_consensus/total, "Under": under_consensus/total}
        for side in ("Over","Under"):
            choice = best[
                (best.Game==keys[0]) & (best.Market==keys[1]) &
                (best.Player==keys[2]) & (best.Line==keys[3]) &
                (best.Side==side)
            ]
            if choice.empty:
                continue
            row = choice.iloc[0]
            probability = consensus[side]
            edge = (probability - implied_probability(row.Odds))*100
            ev = expected_value(probability, row.Odds)
            rows.append({
                "Game": keys[0], "Market": keys[1], "Player": keys[2],
                "Side": side, "Line": keys[3], "Odds": int(row.Odds),
                "Book": row.Book, "BookLink": row.get("BookLink",""),
                "ConsensusProb": probability, "Edge": edge, "EV": ev,
                "Grade": grade(edge), "Score": int(clamp(round(50+edge*6),1,99)),
                "LastUpdate": row.LastUpdate,
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["Edge","EV"], ascending=False)



def best_prop_shortlist(props, minimum_books=2, minimum_edge=0.5, one_per_player=True, limit=15):
    """Return a concise list of the strongest line-shopping prop opportunities."""
    board = prop_value_board(props)
    if board.empty:
        return board

    coverage = (
        props.groupby(["Game", "Market", "Player", "Line"], dropna=False)["Book"]
        .nunique()
        .rename("BookCount")
        .reset_index()
    )
    board = board.merge(coverage, on=["Game", "Market", "Player", "Line"], how="left")
    board["BookCount"] = board["BookCount"].fillna(0).astype(int)
    board = board[(board.BookCount >= minimum_books) & (board.Edge >= minimum_edge)].copy()
    if board.empty:
        return board

    board["RankScore"] = (
        board.Edge * 7.0
        + board.EV.clip(lower=-10, upper=25) * 0.8
        + board.BookCount.clip(upper=8) * 1.5
        + board.ConsensusProb * 10
    )
    board = board.sort_values(["RankScore", "Edge", "EV"], ascending=False)
    if one_per_player:
        board = board.drop_duplicates(subset=["Player"], keep="first")
    board["Reason"] = board.apply(
        lambda r: (
            f"Best price {int(r.Odds):+d} at {r.Book}; "
            f"{r.Edge:.1f}% above break-even with prices from {int(r.BookCount)} books."
        ), axis=1
    )
    return board.head(limit).reset_index(drop=True)

# ---------------- Streamlit application ----------------
st.set_page_config(page_title="Diamond Edge Pro", page_icon="⚾", layout="wide")
TODAY = datetime.now(ZoneInfo("America/Chicago")).date()
SEASON = TODAY.year

st.markdown(
    """
<style>
.stApp{background:linear-gradient(180deg,#f8fbff 0%,#edf4fa 100%);color:#12263a}
.block-container{max-width:1600px;padding-top:1rem;padding-bottom:3rem}
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #d7e3ee}
[data-testid="stMetric"],.panel,.bet-card{background:#fff;border:1px solid #d7e3ee;border-radius:18px;padding:16px;box-shadow:0 6px 18px rgba(35,72,105,.08)}
.bet-card{margin-bottom:14px;min-height:215px}.edge-a{border-left:6px solid #16a34a}.edge-b{border-left:6px solid #2563eb}.edge-c{border-left:6px solid #d97706}.edge-pass{border-left:6px solid #94a3b8}
.badge{display:inline-block;padding:4px 9px;border-radius:999px;font-size:.72rem;font-weight:800;margin-right:5px}.green{background:#dcfce7;color:#166534}.blue{background:#dbeafe;color:#1e40af}.yellow{background:#fef3c7;color:#92400e}.gray{background:#eef2f7;color:#334155}.red{background:#fee2e2;color:#991b1b}
.muted{color:#62768a;font-size:.87rem}.pick{font-size:1.12rem;font-weight:850;margin:.55rem 0}.hero{font-size:2.4rem;font-weight:900;line-height:1.05;margin-bottom:.25rem}.small{font-size:.8rem}
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## ⚾ Diamond Edge Pro")
    page = st.radio(
        "Navigation",
        [
            "🏠 Command Center",
            "🔥 Best Bets",
            "🎯 Player Props",
            "⚾ Matchups",
            "📊 Team Research",
            "🌦️ Weather",
            "📈 Sportsbook Market",
            "💼 Bet Tracker",
            "⚙️ Data Status",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    slate_date = st.date_input("Slate date", TODAY)
    api_key = st.text_input(
        "The Odds API key",
        value=st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", "")),
        type="password",
    )
    region = st.selectbox("Odds region", ["us", "us2", "eu", "uk", "au"])
    st.divider()
    bankroll = st.number_input("Bankroll", min_value=0.0, value=500.0, step=25.0)
    unit_pct = st.slider("Unit size (%)", .25, 5.0, 1.0, .25)
    unit_value = bankroll * unit_pct / 100
    st.metric("1 unit", f"${unit_value:,.2f}")


def safe_load():
    try:
        schedule = mlb_schedule(str(slate_date))
    except Exception:
        schedule = pd.DataFrame()
    try:
        table = standings(SEASON)
    except Exception:
        table = pd.DataFrame()
    models = build_game_models(schedule, table, SEASON) if not schedule.empty and not table.empty else pd.DataFrame()
    odds = pd.DataFrame()
    quota = {}
    error = None
    if api_key:
        try:
            raw, quota = sportsbook_odds(api_key, region)
            odds = flatten_odds(raw)
        except Exception as exc:
            error = str(exc)
    return schedule, table, models, odds, quota, error


schedule, table, models, odds, quota, odds_error = safe_load()
board = value_board(models, odds)

if "props" not in st.session_state:
    st.session_state.props = pd.DataFrame()
if "prop_status" not in st.session_state:
    st.session_state.prop_status = ""
if "prop_quota" not in st.session_state:
    st.session_state.prop_quota = {}
if "bets" not in st.session_state:
    st.session_state.bets = pd.DataFrame(columns=["Date", "Bet", "Market", "Odds", "Stake", "Result", "Profit", "Notes"])

MARKET_LABELS = {v: k for k, v in MLB_PROP_MARKETS.items()}


def page_header(title, subtitle):
    left, right = st.columns([5, 1])
    with left:
        st.markdown(f'<div class="hero">{title}</div>', unsafe_allow_html=True)
        st.caption(subtitle)
    with right:
        if not odds.empty:
            st.markdown('<div style="text-align:right"><span class="badge green">LIVE ODDS</span></div>', unsafe_allow_html=True)
        elif api_key:
            st.markdown('<div style="text-align:right"><span class="badge red">ODDS ERROR</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="text-align:right"><span class="badge yellow">MODEL ONLY</span></div>', unsafe_allow_html=True)


def grade_class(grade):
    return {"A": "edge-a", "B": "edge-b", "C": "edge-c"}.get(grade, "edge-pass")


def grade_badge(grade):
    return {"A": "green", "B": "blue", "C": "yellow"}.get(grade, "gray")




def format_line(value):
    try:
        if pd.isna(value):
            return ""
        number = float(value)
        return f"{number:g}"
    except Exception:
        return str(value or "")


def format_american(value):
    try:
        return f"{int(float(value)):+d}"
    except Exception:
        return str(value)


def render_cards(frame, limit=12, prop=False):
    if frame.empty:
        st.info("No bets match the current filters.")
        return
    cols = st.columns(3)
    for i, (_, row) in enumerate(frame.head(limit).iterrows()):
        with cols[i % 3]:
            if prop:
                line_text = format_line(row.Line)
                title = f"{row.Player} {row.Side} {line_text}".strip()
                detail = f"{MARKET_LABELS.get(row.Market, row.Market)} • {row.Game}"
                prob_label = "No-vig consensus"
                prob = row.ConsensusProb
                fair_text = "Best available price"
            else:
                title = f"{row.Pick} ({row.Odds:+d})"
                detail = f"{row.Game} • {row.Start}"
                prob_label = "Model probability"
                prob = row.ModelProb
                fair_text = f"Fair odds {row.FairOdds:+d}"
            st.markdown(
                f"""
<div class="bet-card {grade_class(row.Grade)}">
<span class="badge {grade_badge(row.Grade)}">GRADE {row.Grade}</span>
<span class="badge blue">{row.Score}/99</span>
<div class="muted" style="margin-top:8px">{detail}</div>
<div class="pick">{title}</div>
<b>{row.Book} ({format_american(row.Odds)})</b><br>
{prob_label}: <b>{prob*100:.1f}%</b><br>
Edge: <b>{row.Edge:.1f}%</b> • EV: <b>${row.EV:.2f}/$100</b><br>
<span class="muted">{fair_text}</span>
</div>
""",
                unsafe_allow_html=True,
            )


def load_props(selected_games, selected_market_names):
    if not api_key:
        st.session_state.prop_status = "Add your Odds API key first."
        return
    if odds.empty:
        st.session_state.prop_status = "Featured odds must load before event-level props can be requested."
        return
    market_keys = [MLB_PROP_MARKETS[name] for name in selected_market_names]
    games = selected_games or sorted(odds.Game.dropna().unique().tolist())
    events, errors, latest_quota = [], [], {}
    progress = st.progress(0, text="Loading player props...")
    for i, game in enumerate(games):
        match = odds[odds.Game == game]
        if match.empty:
            continue
        try:
            event, q = event_prop_odds(api_key, match.EventID.iloc[0], region, market_keys)
            events.append(event)
            latest_quota = q
        except Exception as exc:
            errors.append(f"{game}: {exc}")
        progress.progress((i + 1) / max(1, len(games)), text=f"Loading {game}")
    progress.empty()
    st.session_state.props = flatten_props(events)
    st.session_state.prop_quota = latest_quota
    if st.session_state.props.empty:
        st.session_state.prop_status = "No prop prices were returned. Books may not have posted them yet, or the API plan/credits may not cover them."
        if errors:
            st.session_state.prop_status += f" First error: {errors[0]}"
    else:
        st.session_state.prop_status = f"Loaded {len(st.session_state.props):,} player-prop prices from {st.session_state.props.Book.nunique()} sportsbooks."


if page == "🏠 Command Center":
    page_header("Command Center", "Today’s slate, model edges, prop prices, and bankroll snapshot.")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Games", len(schedule))
    k2.metric("Sportsbooks", odds.Book.nunique() if not odds.empty else 0)
    k3.metric("Live prices", len(odds))
    k4.metric("Loaded props", len(st.session_state.props))
    k5.metric("1 unit", f"${unit_value:,.2f}")

    if odds_error:
        st.error(f"Odds connection error: {odds_error}")
    elif not api_key:
        st.warning("Your model is available, but live bets require the Odds API key saved in Streamlit Secrets.")

    st.subheader("Top model value")
    top = board[board.Edge >= 1.5] if not board.empty else pd.DataFrame()
    render_cards(top, 9)

    st.subheader("Slate overview")
    if models.empty:
        st.info("No MLB matchup data is available for this date.")
    else:
        overview = models.copy()
        overview["Model Pick"] = overview.apply(lambda r: r.HomeTeam if r.HomeProb >= r.AwayProb else r.AwayTeam, axis=1)
        overview["Pick Probability"] = (overview[["AwayProb", "HomeProb"]].max(axis=1) * 100).round(1)
        st.dataframe(
            overview[["Game", "Start", "AwayPitcher", "HomePitcher", "Model Pick", "Pick Probability", "ProjectedTotal"]],
            use_container_width=True,
            hide_index=True,
        )

elif page == "🔥 Best Bets":
    page_header("Best Bets", "Separate true model edges from simple sportsbook line shopping.")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Model Value", "Moneylines", "Run Lines", "Totals", "Props"])
    with tab1:
        c1, c2 = st.columns(2)
        min_edge = c1.slider("Minimum edge", 0.0, 12.0, 1.5, .5)
        min_score = c2.slider("Minimum score", 1, 99, 55)
        frame = board[(board.Edge >= min_edge) & (board.Score >= min_score)] if not board.empty else pd.DataFrame()
        render_cards(frame, 18)
    for tab, key, title in [(tab2, "h2h", "Moneyline"), (tab3, "spreads", "Run Line"), (tab4, "totals", "Total")]:
        with tab:
            frame = odds[odds.Market == key].copy() if not odds.empty else pd.DataFrame()
            if frame.empty:
                st.info(f"No {title.lower()} prices are currently available.")
            else:
                groups = ["Game", "Selection"] + (["Line"] if key in ("spreads", "totals") else [])
                best = frame.loc[frame.groupby(groups, dropna=False).Odds.idxmax()].sort_values(["Game", "Selection"])
                st.dataframe(best[["Game", "Selection", "Line", "Odds", "Book", "LastUpdate"]], use_container_width=True, hide_index=True)
    with tab5:
        props = st.session_state.props
        if props.empty:
            st.info("Load player props from the Player Props page first.")
        else:
            shortlist = best_prop_shortlist(props, minimum_books=2, minimum_edge=0.5, one_per_player=True, limit=15)
            st.subheader("Best player props")
            render_cards(shortlist, 15, prop=True)
            st.caption("Only the strongest available price for each player is shown. Rankings use no-vig sportsbook consensus and line shopping, not a guaranteed performance projection.")

elif page == "🎯 Player Props":
    page_header("Best Player Props", "A short ranked list of the strongest available props—not a wall of sportsbook prices.")
    game_options = sorted(odds.Game.dropna().unique().tolist()) if not odds.empty else []
    selected_games = st.multiselect("Games", game_options, default=game_options[: min(4, len(game_options))])
    market_names = list(MLB_PROP_MARKETS.keys())
    defaults = ["Pitcher Strikeouts", "Batter Total Bases", "Batter Hits", "Batter Home Runs", "Batter RBIs"]
    selected_markets = st.multiselect("Markets", market_names, default=defaults)
    estimated_calls = len(selected_games or game_options)
    st.caption(f"Estimated request load: {estimated_calls} game requests across {len(selected_markets)} selected markets.")
    if st.button("Find today's best player props", type="primary", use_container_width=True):
        load_props(selected_games, selected_markets)
    if st.session_state.prop_status:
        st.info(st.session_state.prop_status)

    props = st.session_state.props
    if not props.empty:
        c1, c2, c3 = st.columns(3)
        minimum_edge = c1.slider("Minimum edge", 0.0, 8.0, 0.5, 0.5)
        minimum_books = c2.slider("Minimum sportsbooks", 1, 6, 2)
        top_n = c3.slider("Number of picks", 3, 20, 10)

        try:
            shortlist = best_prop_shortlist(
                props,
                minimum_books=minimum_books,
                minimum_edge=minimum_edge,
                one_per_player=True,
                limit=top_n,
            )
        except Exception as exc:
            st.error(f"Could not rank the loaded props: {exc}")
            shortlist = pd.DataFrame()

        a, b, c, d = st.columns(4)
        a.metric("Best props", len(shortlist))
        b.metric("Players checked", props.Player.nunique())
        c.metric("Sportsbooks", props.Book.nunique())
        d.metric("Markets checked", props.Market.nunique())

        if shortlist.empty:
            st.warning("No props meet those quality filters. Lower Minimum edge or Minimum sportsbooks, or load more games and markets.")
        else:
            st.subheader("Today's strongest props")
            render_cards(shortlist, top_n, prop=True)
            table = shortlist.copy()
            table["Prop"] = table.apply(lambda r: f"{r.Player} {r.Side} {format_line(r.Line)}".strip(), axis=1)
            table["Market Name"] = table.Market.map(lambda x: MARKET_LABELS.get(x, x))
            table["Consensus %"] = (table.ConsensusProb * 100).round(1)
            table["Edge %"] = table.Edge.round(1)
            st.dataframe(
                table[["Prop", "Market Name", "Game", "Odds", "Book", "Consensus %", "Edge %", "BookCount"]],
                use_container_width=True,
                hide_index=True,
            )
            st.download_button("Download best props", table.to_csv(index=False), "diamond_edge_best_props.csv", "text/csv")

        with st.expander("See all sportsbook prop prices"):
            display = props.copy()
            display["Market Name"] = display.Market.map(lambda x: MARKET_LABELS.get(x, x))
            st.dataframe(
                display[["Game", "Market Name", "Player", "Side", "Line", "Odds", "Book", "LastUpdate"]],
                use_container_width=True,
                hide_index=True,
            )

        st.caption("These are the best line-shopping opportunities found from the connected books. A future trained player model would add independent statistical projections.")

elif page == "⚾ Matchups":
    page_header("Matchups", "Starting pitchers, fair odds, projected total, park factor, weather, and live prices.")
    if models.empty:
        st.info("No matchup data is available for the selected date.")
    for _, row in models.iterrows():
        favorite = row.HomeTeam if row.HomeProb >= row.AwayProb else row.AwayTeam
        with st.expander(f"{row.Game} • {row.Start} • Model lean: {favorite}"):
            a, b, c = st.columns(3)
            with a:
                st.subheader(row.AwayTeam)
                st.write(f"Starter: **{row.AwayPitcher}**")
                st.write(f"ERA: {row.AwayERA or 'N/A'} • K/9: {row.AwayK9 or 'N/A'}")
                st.metric("Win probability", f"{row.AwayProb*100:.1f}%")
                st.metric("Fair odds", f"{row.AwayFair:+d}")
            with b:
                st.subheader(row.HomeTeam)
                st.write(f"Starter: **{row.HomePitcher}**")
                st.write(f"ERA: {row.HomeERA or 'N/A'} • K/9: {row.HomeK9 or 'N/A'}")
                st.metric("Win probability", f"{row.HomeProb*100:.1f}%")
                st.metric("Fair odds", f"{row.HomeFair:+d}")
            with c:
                st.subheader("Environment")
                st.metric("Projected total", row.ProjectedTotal)
                st.write(f"Park factor: **{row.ParkFactor:.2f}**")
                if row.Weather:
                    st.write(f"{row.Weather['Temperature']}°F • Wind {row.Weather['WindSpeed']} mph")
                    st.write(f"Rain chance: {row.Weather['RainChance']}%")
            game_odds = odds[odds.Game == row.Game] if not odds.empty else pd.DataFrame()
            if not game_odds.empty:
                st.dataframe(game_odds[["Market", "Selection", "Line", "Odds", "Book", "LastUpdate"]].sort_values("Odds", ascending=False), use_container_width=True, hide_index=True)

elif page == "📊 Team Research":
    page_header("Team Research", "Sortable standings, run differential, and basic strength indicators.")
    if table.empty:
        st.info("Team standings are unavailable.")
    else:
        research = table.copy()
        research["RunDiff/Game"] = (research.RunDiff / research.Games).round(2)
        research["Win %"] = (research.WinPct * 100).round(1)
        research["Strength Score"] = (research.WinPct * 70 + research["RunDiff/Game"].clip(-2, 2) * 7.5 + 15).round(1)
        research = research.sort_values("Strength Score", ascending=False)
        st.dataframe(research[["Team", "Wins", "Losses", "Win %", "RunDiff", "RunDiff/Game", "Strength Score"]], use_container_width=True, hide_index=True)
        team = st.selectbox("Team detail", research.Team.tolist())
        row = research[research.Team == team].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Record", f"{int(row.Wins)}-{int(row.Losses)}")
        c2.metric("Win %", f"{row['Win %']:.1f}%")
        c3.metric("Run differential", f"{int(row.RunDiff):+d}")
        c4.metric("Strength score", f"{row['Strength Score']:.1f}")

elif page == "🌦️ Weather":
    page_header("Weather Center", "Game-time temperature, wind, humidity, precipitation risk, and projected total.")
    rows = []
    for _, row in models.iterrows():
        w = row.Weather
        rows.append({"Game": row.Game, "Start": row.Start, "Venue": row.Venue, "Temperature": None if not w else w["Temperature"], "Wind mph": None if not w else w["WindSpeed"], "Wind direction": None if not w else w["WindDirection"], "Humidity %": None if not w else w["Humidity"], "Rain chance %": None if not w else w["RainChance"], "Projected total": row.ProjectedTotal})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page == "📈 Sportsbook Market":
    page_header("Sportsbook Market", "All connected moneyline, run-line, total, and loaded prop prices.")
    game_tab, prop_tab = st.tabs(["Game Markets", "Player Props"])
    with game_tab:
        if odds.empty:
            st.info("No live game-market prices are loaded.")
        else:
            display = odds.copy()
            display["Market"] = display.Market.map({"h2h": "Moneyline", "spreads": "Run Line", "totals": "Total"})
            st.dataframe(display[["Game", "Market", "Selection", "Line", "Odds", "Book", "LastUpdate"]], use_container_width=True, hide_index=True)
    with prop_tab:
        if st.session_state.props.empty:
            st.info("Load player props first.")
        else:
            p = st.session_state.props.copy(); p["Market Name"] = p.Market.map(lambda x: MARKET_LABELS.get(x, x))
            st.dataframe(p[["Game", "Market Name", "Player", "Side", "Line", "Odds", "Book", "LastUpdate"]], use_container_width=True, hide_index=True)

elif page == "💼 Bet Tracker":
    page_header("Bet Tracker", "Track outcomes, ROI, win rate, market performance, and export your records.")
    uploaded = st.file_uploader("Import existing tracker CSV", type=["csv"])
    if uploaded is not None:
        try:
            imported = pd.read_csv(uploaded)
            required = ["Date", "Bet", "Market", "Odds", "Stake", "Result", "Profit"]
            if all(col in imported.columns for col in required):
                if "Notes" not in imported.columns: imported["Notes"] = ""
                st.session_state.bets = imported[st.session_state.bets.columns]
                st.success("Tracker imported.")
            else:
                st.error("The CSV is missing required tracker columns.")
        except Exception as exc:
            st.error(f"Could not import CSV: {exc}")
    with st.form("add_bet", clear_on_submit=True):
        a, b, c = st.columns(3)
        bet = a.text_input("Bet")
        market = b.selectbox("Market", ["Moneyline", "Run Line", "Total", "Player Prop"])
        price = c.number_input("Odds", value=-110, step=5)
        d, e, f = st.columns(3)
        stake = d.number_input("Stake", min_value=1.0, value=max(1.0, round(unit_value, 2)))
        result = e.selectbox("Result", ["Pending", "Win", "Loss", "Push"])
        notes = f.text_input("Notes")
        submitted = st.form_submit_button("Add bet")
    if submitted and bet:
        profit = stake * (decimal_odds(price) - 1) if result == "Win" else -stake if result == "Loss" else 0
        new = pd.DataFrame([[str(slate_date), bet, market, price, stake, result, round(profit, 2), notes]], columns=st.session_state.bets.columns)
        st.session_state.bets = pd.concat([st.session_state.bets, new], ignore_index=True)
    bets = st.session_state.bets
    if not bets.empty:
        settled = bets[bets.Result.isin(["Win", "Loss", "Push"])].copy()
        risk = settled.Stake.sum(); profit = settled.Profit.sum(); roi = profit / risk * 100 if risk else 0
        decisions = settled[settled.Result.isin(["Win", "Loss"])]
        win_rate = (decisions.Result == "Win").mean() * 100 if not decisions.empty else 0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Profit", f"${profit:,.2f}")
        c2.metric("ROI", f"{roi:.1f}%")
        c3.metric("Win rate", f"{win_rate:.1f}%")
        c4.metric("Total bets", len(bets))
        st.dataframe(bets, use_container_width=True, hide_index=True)
        if not settled.empty:
            market_summary = settled.groupby("Market", as_index=False).agg(Bets=("Bet", "count"), Risked=("Stake", "sum"), Profit=("Profit", "sum"))
            market_summary["ROI %"] = (market_summary.Profit / market_summary.Risked * 100).round(1)
            st.subheader("Performance by market")
            st.dataframe(market_summary, use_container_width=True, hide_index=True)
        st.download_button("Download tracker CSV", bets.to_csv(index=False), "diamond_edge_tracker.csv", "text/csv")
        if st.button("Clear tracker"):
            st.session_state.bets = st.session_state.bets.iloc[0:0]
            st.rerun()

elif page == "⚙️ Data Status":
    page_header("Data Status", "See what is connected, what is free, and what still needs premium data.")
    statuses = [
        ["MLB schedule and standings", "Connected" if not schedule.empty else "Unavailable", "Free"],
        ["Probable pitchers and season stats", "Connected" if not models.empty else "Unavailable", "Free"],
        ["Weather", "Connected" if not models.empty else "Unavailable", "Free"],
        ["Moneylines, run lines, totals", "Connected" if not odds.empty else "Needs API/key", "Free tier available"],
        ["Player prop prices", "Loaded" if not st.session_state.props.empty else "Load on Player Props page", "Depends on free credits"],
        ["Confirmed lineups/injuries", "Not connected", "Usually paid or separate source"],
        ["Historical odds/backtesting", "Not connected", "Usually paid"],
        ["Trained player prop projection model", "Not built yet", "Can be built later with historical data"],
    ]
    st.dataframe(pd.DataFrame(statuses, columns=["Feature", "Status", "Cost/Limit"]), use_container_width=True, hide_index=True)
    if quota:
        st.write(f"Odds API requests remaining: **{quota.get('remaining', 'Unknown')}**")
    if odds_error:
        st.error(odds_error)
    st.markdown("""### Permanent Streamlit secret
```toml
ODDS_API_KEY = "your_actual_key"
```
""")

st.divider()
st.caption("Research tool only. Predictions and consensus estimates are not guarantees. Verify lineups and prices before placing any wager.")
