
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Diamond Edge MLB v3",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

CENTRAL = ZoneInfo("America/Chicago")
TODAY = datetime.now(CENTRAL).date()
SEASON = TODAY.year

# -------------------- Light theme --------------------
st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #f7fbff 0%, #eef5fb 100%);
    color: #132238;
}
.block-container {
    padding-top: 1rem;
    padding-bottom: 3rem;
    max-width: 1500px;
}
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #d8e4ef;
}
[data-testid="stSidebar"] * {
    color: #132238;
}
div[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #d8e4ef;
    border-radius: 16px;
    padding: 14px;
    box-shadow: 0 4px 14px rgba(29, 78, 121, 0.07);
}
.bet-card {
    background: #ffffff;
    border: 1px solid #d8e4ef;
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 14px;
    min-height: 220px;
    box-shadow: 0 5px 16px rgba(29, 78, 121, 0.08);
}
.grade-a { border-left: 6px solid #16a34a; }
.grade-b { border-left: 6px solid #65a30d; }
.grade-c { border-left: 6px solid #d97706; }
.grade-pass { border-left: 6px solid #dc2626; }
.badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 999px;
    font-size: .75rem;
    font-weight: 800;
    margin-right: 5px;
}
.green { background:#dcfce7; color:#166534; border:1px solid #86efac; }
.yellow { background:#fef3c7; color:#92400e; border:1px solid #fcd34d; }
.red { background:#fee2e2; color:#991b1b; border:1px solid #fca5a5; }
.blue { background:#dbeafe; color:#1e40af; border:1px solid #93c5fd; }
.gray { background:#f1f5f9; color:#334155; border:1px solid #cbd5e1; }
.big-pick {
    font-size: 1.16rem;
    font-weight: 850;
    margin: .55rem 0;
    color:#0f2740;
}
.muted { color:#5f7388; font-size:.88rem; }
.section-title {
    font-size:1.35rem;
    font-weight:850;
    color:#0f2740;
    margin-top:.35rem;
}
.stTabs [data-baseweb="tab-list"] { gap:8px; }
.stTabs [data-baseweb="tab"] {
    background:#ffffff;
    border:1px solid #d8e4ef;
    border-radius:10px;
    padding:8px 14px;
}
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background:#ffffff;
}
</style>
""", unsafe_allow_html=True)

# -------------------- Math helpers --------------------
def clamp(x, low, high):
    return max(low, min(high, x))

def logistic(x):
    return 1 / (1 + math.exp(-x))

def logit(p):
    p = clamp(p, 0.01, 0.99)
    return math.log(p / (1 - p))

def implied_probability(odds):
    odds = float(odds)
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def decimal_odds(odds):
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)

def expected_value_per_100(prob, odds):
    d = decimal_odds(float(odds))
    return 100 * (prob * (d - 1) - (1 - prob))

def edge_pct(prob, odds):
    return (prob - implied_probability(odds)) * 100

def grade(edge):
    if edge >= 7:
        return "A"
    if edge >= 4:
        return "B"
    if edge >= 1.5:
        return "C"
    return "PASS"

def grade_color(g):
    return "green" if g in ("A", "B") else "yellow" if g == "C" else "red"

def grade_class(g):
    return {"A":"grade-a", "B":"grade-b", "C":"grade-c"}.get(g, "grade-pass")

def american_from_probability(p):
    p = clamp(p, 0.01, 0.99)
    if p >= 0.5:
        return -round(100 * p / (1 - p))
    return round(100 * (1 - p) / p)

def fmt_time(iso):
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(CENTRAL)
        return dt.strftime("%a %b %-d • %-I:%M %p CT")
    except Exception:
        return iso

# -------------------- MLB data --------------------
@st.cache_data(ttl=300)
def fetch_schedule(date_string):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "date": date_string,
        "hydrate": "probablePitcher,team"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    rows = []
    for day in r.json().get("dates", []):
        for game in day.get("games", []):
            away = game["teams"]["away"]["team"]
            home = game["teams"]["home"]["team"]
            rows.append({
                "GamePk": game.get("gamePk"),
                "Game": f"{away['name']} @ {home['name']}",
                "AwayTeam": away["name"],
                "AwayID": away["id"],
                "HomeTeam": home["name"],
                "HomeID": home["id"],
                "Start": fmt_time(game.get("gameDate", "")),
                "Status": game.get("status", {}).get("detailedState", ""),
                "AwayPitcher": game["teams"]["away"].get("probablePitcher", {}).get("fullName", "TBD"),
                "AwayPitcherID": game["teams"]["away"].get("probablePitcher", {}).get("id"),
                "HomePitcher": game["teams"]["home"].get("probablePitcher", {}).get("fullName", "TBD"),
                "HomePitcherID": game["teams"]["home"].get("probablePitcher", {}).get("id"),
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=900)
def fetch_standings(season):
    url = "https://statsapi.mlb.com/api/v1/standings"
    params = {
        "leagueId": "103,104",
        "season": season,
        "standingsTypes": "regularSeason"
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    rows = []
    for record_group in r.json().get("records", []):
        for team_record in record_group.get("teamRecords", []):
            wins = int(team_record.get("wins", 0))
            losses = int(team_record.get("losses", 0))
            games = max(1, wins + losses)
            rows.append({
                "TeamID": team_record["team"]["id"],
                "Team": team_record["team"]["name"],
                "Wins": wins,
                "Losses": losses,
                "WinPct": wins / games,
                "RunDiff": int(team_record.get("runDifferential", 0)),
                "Games": games,
            })
    return pd.DataFrame(rows)

@st.cache_data(ttl=1800)
def fetch_pitcher_stats(person_id, season):
    if not person_id:
        return {"ERA": None, "WHIP": None, "K9": None, "IP": 0.0}
    url = f"https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
    params = {
        "stats": "season",
        "group": "pitching",
        "season": season
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        splits = r.json().get("stats", [{}])[0].get("splits", [])
        if not splits:
            return {"ERA": None, "WHIP": None, "K9": None, "IP": 0.0}
        stat = splits[0].get("stat", {})
        return {
            "ERA": float(stat["era"]) if stat.get("era") not in (None, "-.--") else None,
            "WHIP": float(stat["whip"]) if stat.get("whip") not in (None, "-.--") else None,
            "K9": float(stat["strikeoutsPer9Inn"]) if stat.get("strikeoutsPer9Inn") not in (None, "-.--") else None,
            "IP": float(stat.get("inningsPitched", 0) or 0),
        }
    except Exception:
        return {"ERA": None, "WHIP": None, "K9": None, "IP": 0.0}

@st.cache_data(ttl=180)
def fetch_odds(api_key, region="us"):
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        "apiKey": api_key,
        "regions": region,
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json(), r.headers.get("x-requests-remaining")

def flatten_odds(raw):
    rows = []
    for game in raw:
        matchup = f"{game.get('away_team')} @ {game.get('home_team')}"
        for book in game.get("bookmakers", []):
            for market in book.get("markets", []):
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "Game": matchup,
                        "Book": book.get("title", ""),
                        "Market": market.get("key", ""),
                        "Selection": outcome.get("name", ""),
                        "Line": outcome.get("point"),
                        "Odds": outcome.get("price"),
                    })
    return pd.DataFrame(rows)

def best_moneyline_prices(odds_df):
    if odds_df.empty:
        return pd.DataFrame()
    ml = odds_df[odds_df["Market"] == "h2h"].copy()
    if ml.empty:
        return ml
    idx = ml.groupby(["Game", "Selection"])["Odds"].idxmax()
    return ml.loc[idx].reset_index(drop=True)

# -------------------- Model --------------------
def team_strength(team_row):
    # Blend record and run differential per game.
    wp = float(team_row["WinPct"])
    rdpg = float(team_row["RunDiff"]) / max(1, float(team_row["Games"]))
    return logit(wp) + 0.11 * rdpg

def pitcher_adjustment(stats):
    # Positive means better than league average.
    if stats["ERA"] is None or stats["IP"] < 5:
        return 0.0
    era_component = (4.30 - stats["ERA"]) * 0.085
    whip_component = 0 if stats["WHIP"] is None else (1.30 - stats["WHIP"]) * 0.20
    k_component = 0 if stats["K9"] is None else (stats["K9"] - 8.5) * 0.018
    return clamp(era_component + whip_component + k_component, -0.45, 0.45)

def model_game(game_row, standings_df):
    away = standings_df[standings_df.TeamID == game_row.AwayID]
    home = standings_df[standings_df.TeamID == game_row.HomeID]
    if away.empty or home.empty:
        return None

    away_row = away.iloc[0]
    home_row = home.iloc[0]
    away_pitch = fetch_pitcher_stats(game_row.AwayPitcherID, SEASON)
    home_pitch = fetch_pitcher_stats(game_row.HomePitcherID, SEASON)

    away_score = team_strength(away_row) + pitcher_adjustment(away_pitch)
    home_score = team_strength(home_row) + pitcher_adjustment(home_pitch) + 0.13

    home_prob = logistic(home_score - away_score)
    away_prob = 1 - home_prob

    return {
        "Game": game_row.Game,
        "Start": game_row.Start,
        "AwayTeam": game_row.AwayTeam,
        "HomeTeam": game_row.HomeTeam,
        "AwayProb": away_prob,
        "HomeProb": home_prob,
        "AwayFair": american_from_probability(away_prob),
        "HomeFair": american_from_probability(home_prob),
        "AwayPitcher": game_row.AwayPitcher,
        "HomePitcher": game_row.HomePitcher,
        "AwayPitcherERA": away_pitch["ERA"],
        "HomePitcherERA": home_pitch["ERA"],
        "AwayWinPct": away_row.WinPct,
        "HomeWinPct": home_row.WinPct,
        "AwayRunDiff": away_row.RunDiff,
        "HomeRunDiff": home_row.RunDiff,
    }

def make_bet_board(models_df, odds_df):
    if models_df.empty or odds_df.empty:
        return pd.DataFrame()
    prices = best_moneyline_prices(odds_df)
    rows = []
    for _, game in models_df.iterrows():
        for side in ["Away", "Home"]:
            team = game[f"{side}Team"]
            prob = game[f"{side}Prob"]
            match = prices[(prices.Game == game.Game) & (prices.Selection == team)]
            if match.empty:
                continue
            best = match.iloc[0]
            edge = edge_pct(prob, best.Odds)
            ev = expected_value_per_100(prob, best.Odds)
            g = grade(edge)
            score = int(clamp(round(50 + edge * 5), 1, 99))
            rows.append({
                "Game": game.Game,
                "Start": game.Start,
                "Pick": team,
                "Odds": int(best.Odds),
                "Book": best.Book,
                "ModelProb": prob,
                "FairOdds": game[f"{side}Fair"],
                "Edge": edge,
                "EV": ev,
                "Grade": g,
                "Score": score,
                "Reason": (
                    f"{team} model probability {prob*100:.1f}% versus "
                    f"market break-even {implied_probability(best.Odds)*100:.1f}%."
                )
            })
    return pd.DataFrame(rows).sort_values(["Edge", "EV"], ascending=False)

# -------------------- Sidebar --------------------
with st.sidebar:
    st.markdown("## ⚾ Diamond Edge v3")
    st.caption("Real MLB data-driven model")
    selected_date = st.date_input("Slate date", TODAY)
    api_key = st.text_input(
        "The Odds API key",
        value=st.secrets.get("ODDS_API_KEY", os.getenv("ODDS_API_KEY", "")),
        type="password",
        help="Needed for live sportsbook prices."
    )
    region = st.selectbox("Odds region", ["us", "us2", "eu", "uk", "au"])
    min_edge = st.slider("Minimum edge", 0.0, 12.0, 1.5, 0.5)
    min_score = st.slider("Minimum score", 1, 99, 55)
    st.divider()
    bankroll = st.number_input("Bankroll", min_value=0.0, value=500.0, step=25.0)
    unit_pct = st.slider("Unit size (% bankroll)", 0.25, 5.0, 1.0, 0.25)
    st.metric("1 Unit", f"${bankroll * unit_pct / 100:,.2f}")
    st.caption("Only wager money you can afford to lose.")

# -------------------- Load data --------------------
schedule_error = standings_error = odds_error = None

try:
    schedule_df = fetch_schedule(str(selected_date))
except Exception as exc:
    schedule_df = pd.DataFrame()
    schedule_error = str(exc)

try:
    standings_df = fetch_standings(SEASON)
except Exception as exc:
    standings_df = pd.DataFrame()
    standings_error = str(exc)

models = []
if not schedule_df.empty and not standings_df.empty:
    for _, row in schedule_df.iterrows():
        result = model_game(row, standings_df)
        if result:
            models.append(result)
models_df = pd.DataFrame(models)

odds_df = pd.DataFrame()
quota_remaining = None
if api_key:
    try:
        raw_odds, quota_remaining = fetch_odds(api_key, region)
        odds_df = flatten_odds(raw_odds)
    except Exception as exc:
        odds_error = str(exc)

bet_board = make_bet_board(models_df, odds_df) if not models_df.empty and not odds_df.empty else pd.DataFrame()

# -------------------- Header --------------------
c1, c2 = st.columns([4, 1])
with c1:
    st.title("⚾ Diamond Edge MLB v3")
    st.caption("Team strength • run differential • probable pitchers • fair odds • live market value")
with c2:
    mode = "LIVE VALUE MODE" if not odds_df.empty else "MODEL ONLY"
    color = "green" if not odds_df.empty else "yellow"
    st.markdown(f'<div style="text-align:right"><span class="badge {color}">{mode}</span></div>', unsafe_allow_html=True)

tabs = st.tabs([
    "🏆 Top Bets",
    "📊 Game Predictions",
    "💵 Best Odds",
    "🎯 Player Props",
    "🧮 EV Lab",
    "ℹ️ Model Notes"
])

with tabs[0]:
    st.markdown('<div class="section-title">Top Value Plays</div>', unsafe_allow_html=True)
    if odds_error:
        st.error(f"Live odds could not load: {odds_error}")

    if bet_board.empty:
        st.info("The model is running. Add your Odds API key to turn predictions into live value bets.")
        if not models_df.empty:
            preview = models_df.copy()
            preview["Model Pick"] = preview.apply(
                lambda r: r.HomeTeam if r.HomeProb >= r.AwayProb else r.AwayTeam, axis=1
            )
            preview["Win Probability"] = preview[["AwayProb", "HomeProb"]].max(axis=1)
            preview["Win Probability"] = (preview["Win Probability"] * 100).round(1).astype(str) + "%"
            st.dataframe(
                preview[["Game", "Start", "Model Pick", "Win Probability", "AwayFair", "HomeFair"]],
                use_container_width=True,
                hide_index=True
            )
    else:
        filtered = bet_board[(bet_board.Edge >= min_edge) & (bet_board.Score >= min_score)]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Qualifying Bets", len(filtered))
        m2.metric("Best Edge", f"{filtered.Edge.max():.1f}%" if len(filtered) else "—")
        m3.metric("Best EV", f"${filtered.EV.max():.2f}" if len(filtered) else "—")
        m4.metric("A/B Grades", int(filtered.Grade.isin(["A", "B"]).sum()) if len(filtered) else 0)

        cols = st.columns(3)
        for i, (_, r) in enumerate(filtered.head(9).iterrows()):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="bet-card {grade_class(r.Grade)}">
                    <span class="badge {grade_color(r.Grade)}">GRADE {r.Grade}</span>
                    <span class="badge blue">{r.Score}/99</span>
                    <div class="muted" style="margin-top:10px">{r.Game}</div>
                    <div class="big-pick">{r.Pick} ({r.Odds:+d})</div>
                    <div><b>Best book:</b> {r.Book}</div>
                    <div style="margin-top:9px">
                        Model: <b>{r.ModelProb*100:.1f}%</b> &nbsp;
                        Fair: <b>{r.FairOdds:+d}</b>
                    </div>
                    <div>Edge: <b>{r.Edge:.1f}%</b> &nbsp; EV: <b>${r.EV:.2f}/$100</b></div>
                    <div class="muted" style="margin-top:10px">{r.Reason}</div>
                </div>
                """, unsafe_allow_html=True)

with tabs[1]:
    st.markdown('<div class="section-title">Game-by-Game Model</div>', unsafe_allow_html=True)
    if schedule_error:
        st.error(f"Schedule unavailable: {schedule_error}")
    if standings_error:
        st.error(f"Standings unavailable: {standings_error}")
    if models_df.empty:
        st.warning("No model predictions are available for this date.")
    else:
        for _, r in models_df.iterrows():
            pick = r.HomeTeam if r.HomeProb >= r.AwayProb else r.AwayTeam
            pick_prob = max(r.HomeProb, r.AwayProb)
            with st.expander(f"{r.Game} • {r.Start} • Pick: {pick} ({pick_prob*100:.1f}%)"):
                a, b = st.columns(2)
                with a:
                    st.markdown(f"### {r.AwayTeam}")
                    st.write(f"Record strength: {r.AwayWinPct*100:.1f}%")
                    st.write(f"Run differential: {int(r.AwayRunDiff):+d}")
                    st.write(f"Starter: {r.AwayPitcher}")
                    st.write(f"Starter ERA: {r.AwayPitcherERA if r.AwayPitcherERA is not None else 'N/A'}")
                    st.metric("Model win probability", f"{r.AwayProb*100:.1f}%")
                    st.metric("Model fair odds", f"{r.AwayFair:+d}")
                with b:
                    st.markdown(f"### {r.HomeTeam}")
                    st.write(f"Record strength: {r.HomeWinPct*100:.1f}%")
                    st.write(f"Run differential: {int(r.HomeRunDiff):+d}")
                    st.write(f"Starter: {r.HomePitcher}")
                    st.write(f"Starter ERA: {r.HomePitcherERA if r.HomePitcherERA is not None else 'N/A'}")
                    st.metric("Model win probability", f"{r.HomeProb*100:.1f}%")
                    st.metric("Model fair odds", f"{r.HomeFair:+d}")

with tabs[2]:
    st.markdown('<div class="section-title">Best Sportsbook Prices</div>', unsafe_allow_html=True)
    if odds_df.empty:
        st.warning("Add your Odds API key to compare live sportsbook prices.")
    else:
        market_names = {"h2h":"Moneyline", "spreads":"Run Line", "totals":"Total"}
        display = odds_df.copy()
        display["Market"] = display["Market"].map(market_names).fillna(display["Market"])
        display = display.sort_values(["Game", "Market", "Selection", "Odds"], ascending=[True, True, True, False])
        st.dataframe(display, use_container_width=True, hide_index=True)
        if quota_remaining is not None:
            st.caption(f"API requests remaining: {quota_remaining}")

with tabs[3]:
    st.markdown('<div class="section-title">Player Prop Engine</div>', unsafe_allow_html=True)
    st.info(
        "This section is prepared for strikeouts, total bases, hits, home runs, RBIs, and walks. "
        "Real player-prop prices require an API plan that includes MLB event markets."
    )
    st.dataframe(pd.DataFrame([
        ["Strikeouts", "Pitcher Over", "K rate, opponent strikeouts, pitch count"],
        ["Total Bases", "Hitter Over", "Platoon split, hard-hit rate, park factor"],
        ["Home Runs", "Hitter Yes", "Barrel rate, fly-ball rate, weather"],
        ["Hits", "Hitter Over", "Contact rate, pitch mix, lineup spot"],
    ], columns=["Market", "Target", "Planned Model Inputs"]), use_container_width=True, hide_index=True)

with tabs[4]:
    st.markdown('<div class="section-title">Expected Value Calculator</div>', unsafe_allow_html=True)
    x, y, z = st.columns(3)
    user_odds = x.number_input("American odds", value=-110, step=5)
    user_prob = y.number_input("Estimated win probability (%)", 1.0, 99.0, 55.0, 0.5)
    stake = z.number_input("Stake", 1.0, 10000.0, 100.0, 5.0)
    p = user_prob / 100
    imp = implied_probability(user_odds)
    ev100 = expected_value_per_100(p, user_odds)
    m1, m2, m3 = st.columns(3)
    m1.metric("Break-even", f"{imp*100:.1f}%")
    m2.metric("Edge", f"{(p-imp)*100:.1f}%")
    m3.metric("Expected value", f"${ev100*stake/100:.2f}")
    if ev100 > 0:
        st.success("Positive expected value based on your probability estimate.")
    else:
        st.error("Negative expected value based on your probability estimate.")

with tabs[5]:
    st.markdown('<div class="section-title">How Version 3 Works</div>', unsafe_allow_html=True)
    st.markdown("""
    Version 3 is **data-driven**, not a trained artificial-intelligence model.

    It currently uses:

    - Current MLB team win percentage
    - Run differential per game
    - Home-field advantage
    - Confirmed probable pitchers
    - Pitcher ERA, WHIP, and strikeout rate when available
    - Best available moneyline price
    - Model fair odds, edge, and expected value

    It does **not yet** include confirmed lineups, weather, injuries, umpire tendencies,
    bullpen workload, or a trained machine-learning model. Those are the next upgrades.
    """)

st.divider()
st.caption("Diamond Edge is an analysis tool, not a guarantee of profit. Always verify the current line before betting.")
