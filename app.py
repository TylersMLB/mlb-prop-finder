
import os
import math
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="MLB Betting Dashboard",
    page_icon="⚾",
    layout="wide",
)

# -----------------------------
# Styling
# -----------------------------
st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    .metric-card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 14px;
        padding: 14px 16px;
        background: rgba(255,255,255,.03);
    }
    .small-note {font-size: .85rem; opacity: .75;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Helpers
# -----------------------------
def american_to_decimal(odds: float) -> float:
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def implied_probability(odds: float) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def expected_value_per_100(model_prob: float, odds: float) -> float:
    dec = american_to_decimal(odds)
    return 100 * ((model_prob * (dec - 1)) - (1 - model_prob))

def edge_pct(model_prob: float, odds: float) -> float:
    return (model_prob - implied_probability(odds)) * 100

def confidence_label(edge: float) -> str:
    if edge >= 8:
        return "A"
    if edge >= 5:
        return "B"
    if edge >= 2:
        return "C"
    return "Pass"

def freshness(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
        return f"{mins} min ago"
    except Exception:
        return "Unknown"

@st.cache_data(ttl=300)
def fetch_odds(api_key: str, regions: str, markets: str) -> list:
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "american",
        "dateFormat": "iso",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def parse_game_markets(raw_games: list) -> pd.DataFrame:
    rows = []
    for game in raw_games:
        away = game.get("away_team", "")
        home = game.get("home_team", "")
        start = game.get("commence_time", "")
        for book in game.get("bookmakers", []):
            book_name = book.get("title", "")
            updated = book.get("last_update", "")
            for market in book.get("markets", []):
                key = market.get("key", "")
                for outcome in market.get("outcomes", []):
                    rows.append({
                        "Game": f"{away} @ {home}",
                        "Start": start,
                        "Sportsbook": book_name,
                        "Market": key,
                        "Selection": outcome.get("name", ""),
                        "Point": outcome.get("point"),
                        "Odds": outcome.get("price"),
                        "Updated": updated,
                    })
    return pd.DataFrame(rows)

def demo_board() -> pd.DataFrame:
    return pd.DataFrame([
        ["HOU @ TEX", "Moneyline", "HOU Astros", None, -118, 0.565, "Demo Model", "Starting pitching edge"],
        ["LAD @ SF", "Run Line", "LAD Dodgers", -1.5, 124, 0.475, "Demo Model", "Bullpen + offense edge"],
        ["NYY @ BOS", "Total", "Over", 8.5, -105, 0.545, "Demo Model", "Park + contact profile"],
        ["SEA @ MIN", "Pitcher Strikeouts", "SEA Starter Over", 6.5, 110, 0.505, "Demo Model", "Opponent strikeout rate"],
        ["ATL @ MIA", "Total Bases", "ATL Hitter Over", 1.5, 135, 0.455, "Demo Model", "Platoon + hard-hit matchup"],
        ["CHC @ STL", "Home Run", "CHC Hitter", 0.5, 390, 0.235, "Demo Model", "Fly-ball + barrel matchup"],
    ], columns=[
        "Game", "Market", "Selection", "Line", "Odds", "Model Probability", "Source", "Reason"
    ])

# -----------------------------
# Header
# -----------------------------
st.title("⚾ MLB Betting Dashboard")
st.caption(
    "Moneylines, run lines, totals, player props, expected value, confidence grades, "
    "and a clean best-bets board."
)

with st.sidebar:
    st.header("Setup")
    api_key = st.text_input(
        "The Odds API key",
        value=os.getenv("ODDS_API_KEY", ""),
        type="password",
        help="Optional. Leave blank to use demo mode.",
    )
    region = st.selectbox("Sportsbook region", ["us", "us2", "eu", "uk", "au"], index=0)
    live_markets = st.multiselect(
        "Live markets",
        ["h2h", "spreads", "totals"],
        default=["h2h", "spreads", "totals"],
    )
    st.divider()
    min_edge = st.slider("Minimum edge", 0.0, 15.0, 2.0, 0.5)
    min_ev = st.slider("Minimum EV per $100", -20.0, 30.0, 0.0, 1.0)
    books = st.multiselect(
        "Sportsbooks",
        ["All"],
        default=["All"],
        disabled=True,
        help="The list becomes active after live odds load.",
    )
    st.divider()
    st.caption("This app is an analysis tool, not a guarantee of winning.")

# -----------------------------
# Data loading
# -----------------------------
live_df = pd.DataFrame()
load_error = None

if api_key and live_markets:
    try:
        raw = fetch_odds(api_key, region, ",".join(live_markets))
        live_df = parse_game_markets(raw)
    except Exception as exc:
        load_error = str(exc)

if load_error:
    st.error(f"Live odds could not load: {load_error}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Best Bets", "Live Game Lines", "Player Props", "EV Calculator", "How It Works"]
)

# -----------------------------
# Best Bets
# -----------------------------
with tab1:
    st.subheader("Best Bets Board")

    board = demo_board().copy()
    board["Implied Probability"] = board["Odds"].apply(implied_probability)
    board["Edge %"] = board.apply(
        lambda r: edge_pct(r["Model Probability"], r["Odds"]), axis=1
    )
    board["EV / $100"] = board.apply(
        lambda r: expected_value_per_100(r["Model Probability"], r["Odds"]), axis=1
    )
    board["Grade"] = board["Edge %"].apply(confidence_label)

    filtered = board[
        (board["Edge %"] >= min_edge) &
        (board["EV / $100"] >= min_ev)
    ].copy()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Qualifying Plays", len(filtered))
    c2.metric("Best Edge", f'{filtered["Edge %"].max():.1f}%' if len(filtered) else "—")
    c3.metric("Best EV", f'${filtered["EV / $100"].max():.2f}' if len(filtered) else "—")
    c4.metric("A/B Grades", int(filtered["Grade"].isin(["A", "B"]).sum()) if len(filtered) else 0)

    display = filtered.copy()
    if len(display):
        display["Model Probability"] = (display["Model Probability"] * 100).round(1).astype(str) + "%"
        display["Implied Probability"] = (display["Implied Probability"] * 100).round(1).astype(str) + "%"
        display["Edge %"] = display["Edge %"].round(1)
        display["EV / $100"] = display["EV / $100"].round(2)

    st.dataframe(
        display[
            ["Grade", "Game", "Market", "Selection", "Line", "Odds",
             "Model Probability", "Implied Probability", "Edge %", "EV / $100", "Reason"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.info(
        "The best-bets board currently uses demo model probabilities so the site works immediately. "
        "Live sportsbook lines can be enabled with an API key. A real projection model can later replace "
        "the demo probabilities."
    )

# -----------------------------
# Live lines
# -----------------------------
with tab2:
    st.subheader("Live Moneylines, Run Lines, and Totals")

    if live_df.empty:
        st.warning("Enter an Odds API key in the sidebar to load live sportsbook lines.")
        st.dataframe(
            pd.DataFrame([
                ["Example Sportsbook", "HOU @ TEX", "h2h", "Houston Astros", None, -118],
                ["Example Sportsbook", "LAD @ SF", "spreads", "Los Angeles Dodgers", -1.5, 124],
                ["Example Sportsbook", "NYY @ BOS", "totals", "Over", 8.5, -105],
            ], columns=["Sportsbook", "Game", "Market", "Selection", "Point", "Odds"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        live_df["Freshness"] = live_df["Updated"].apply(freshness)
        market_names = {
            "h2h": "Moneyline",
            "spreads": "Run Line",
            "totals": "Total",
        }
        live_df["Market"] = live_df["Market"].map(market_names).fillna(live_df["Market"])

        book_options = sorted(live_df["Sportsbook"].dropna().unique().tolist())
        selected_books = st.multiselect("Filter sportsbooks", book_options, default=book_options)
        game_options = sorted(live_df["Game"].dropna().unique().tolist())
        selected_games = st.multiselect("Filter games", game_options, default=game_options)

        view = live_df[
            live_df["Sportsbook"].isin(selected_books) &
            live_df["Game"].isin(selected_games)
        ].copy()

        st.dataframe(
            view[["Game", "Sportsbook", "Market", "Selection", "Point", "Odds", "Freshness"]],
            use_container_width=True,
            hide_index=True,
        )

# -----------------------------
# Player Props
# -----------------------------
with tab3:
    st.subheader("Player Props")
    st.write(
        "This section is ready for strikeouts, total bases, home runs, hits, RBIs, and runs."
    )

    props = pd.DataFrame([
        ["Pitcher Strikeouts", "Example Pitcher", "Over 6.5", -110, 54.0, 4.0, 3.09],
        ["Total Bases", "Example Hitter", "Over 1.5", 125, 47.0, 2.6, 5.75],
        ["Home Run", "Example Hitter", "Yes", 390, 23.5, 3.1, 15.15],
        ["Hits", "Example Hitter", "Over 0.5", -165, 65.0, 2.7, 4.24],
    ], columns=[
        "Market", "Player", "Pick", "Odds", "Model Probability %", "Edge %", "EV / $100"
    ])
    st.dataframe(props, use_container_width=True, hide_index=True)

    st.caption(
        "Many live player-prop feeds require a paid odds-data plan. The code is structured so "
        "those feeds can be added without redesigning the app."
    )

# -----------------------------
# EV Calculator
# -----------------------------
with tab4:
    st.subheader("Expected Value Calculator")
    col1, col2 = st.columns(2)
    with col1:
        calc_odds = st.number_input("American odds", value=-110, step=5)
    with col2:
        calc_prob_pct = st.number_input(
            "Your estimated win probability (%)",
            min_value=1.0,
            max_value=99.0,
            value=55.0,
            step=0.5,
        )

    calc_prob = calc_prob_pct / 100
    imp = implied_probability(calc_odds)
    ev = expected_value_per_100(calc_prob, calc_odds)
    edge = edge_pct(calc_prob, calc_odds)

    c1, c2, c3 = st.columns(3)
    c1.metric("Implied Probability", f"{imp * 100:.1f}%")
    c2.metric("Your Edge", f"{edge:.1f}%")
    c3.metric("EV per $100", f"${ev:.2f}")

    if ev > 0:
        st.success("Positive expected value based on your probability estimate.")
    else:
        st.error("Negative expected value based on your probability estimate.")

# -----------------------------
# Method
# -----------------------------
with tab5:
    st.subheader("How the Engine Works")
    st.markdown(
        """
        **1. Collect the line**  
        The app reads the sportsbook's American odds.

        **2. Convert odds to implied probability**  
        This estimates the break-even win rate before removing sportsbook hold.

        **3. Compare against a model probability**  
        The current downloadable version includes demo probabilities so the dashboard works immediately.

        **4. Calculate edge and expected value**  
        Edge is the model probability minus implied probability. EV estimates profit or loss per $100 risked over many similar bets.

        **5. Grade the play**  
        Larger edges receive higher confidence grades, but no grade guarantees a win.
        """
    )

    st.subheader("Planned Model Inputs")
    st.markdown(
        """
        - Starting pitcher skill, recent form, pitch count, handedness, and strikeout matchup
        - Bullpen quality, availability, and recent workload
        - Team hitting splits and projected batting order
        - Park factors and weather
        - Injuries and confirmed lineups
        - Sportsbook consensus, best available price, and line movement
        - Player-specific barrel rate, hard-hit rate, contact rate, and platoon splits
        """
    )

st.divider()
st.caption("Built with Streamlit • Refresh live odds from the sidebar")
