import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from data_sources import (
    MLB_PROP_MARKETS,
    event_prop_odds,
    flatten_odds,
    flatten_props,
    mlb_schedule,
    sportsbook_odds,
    standings,
)
from model import (
    build_game_models,
    decimal_odds,
    prop_best_prices,
    prop_value_board,
    value_board,
)

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


def render_cards(frame, limit=12, prop=False):
    if frame.empty:
        st.info("No bets match the current filters.")
        return
    cols = st.columns(3)
    for i, (_, row) in enumerate(frame.head(limit).iterrows()):
        with cols[i % 3]:
            if prop:
                title = f"{row.Player} {row.Side} {row.Line:g}"
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
<b>{row.Book} ({row.Odds:+d})</b><br>
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
            prop_board = prop_value_board(props)
            min_prop_edge = st.slider("Minimum consensus edge", -3.0, 10.0, 0.0, .5)
            render_cards(prop_board[prop_board.Edge >= min_prop_edge], 24, prop=True)
            st.caption("Prop rankings compare the best available price with a no-vig sportsbook consensus. They are not yet trained player-performance projections.")

elif page == "🎯 Player Props":
    page_header("Player Props", "Load available markets, compare every sportsbook, and isolate the best price.")
    game_options = sorted(odds.Game.dropna().unique().tolist()) if not odds.empty else []
    selected_games = st.multiselect("Games", game_options, default=game_options[: min(4, len(game_options))])
    market_names = list(MLB_PROP_MARKETS.keys())
    defaults = ["Pitcher Strikeouts", "Batter Total Bases", "Batter Hits", "Batter Home Runs", "Batter RBIs"]
    selected_markets = st.multiselect("Markets", market_names, default=defaults)
    estimated_calls = len(selected_games or game_options)
    st.caption(f"Estimated request load: {estimated_calls} game requests across {len(selected_markets)} selected markets.")
    if st.button("Load selected player props", type="primary", use_container_width=True):
        load_props(selected_games, selected_markets)
    if st.session_state.prop_status:
        st.info(st.session_state.prop_status)

    props = st.session_state.props
    if not props.empty:
        a, b, c, d = st.columns(4)
        a.metric("Prices", len(props)); b.metric("Players", props.Player.nunique()); c.metric("Books", props.Book.nunique()); d.metric("Markets", props.Market.nunique())
        f1, f2, f3 = st.columns([2, 2, 1])
        market_choice = f1.selectbox("Market filter", ["All"] + sorted(props.Market.map(lambda x: MARKET_LABELS.get(x, x)).unique().tolist()))
        player_search = f2.text_input("Search player")
        best_only = f3.checkbox("Best prices only", value=True)
        display = props.copy()
        display["Market Name"] = display.Market.map(lambda x: MARKET_LABELS.get(x, x))
        if market_choice != "All": display = display[display["Market Name"] == market_choice]
        if player_search: display = display[display.Player.str.contains(player_search, case=False, na=False)]
        if best_only:
            display = prop_best_prices(display)
            display["Market Name"] = display.Market.map(lambda x: MARKET_LABELS.get(x, x))
        st.dataframe(display[["Game", "Market Name", "Player", "Side", "Line", "Odds", "Book", "LastUpdate"]], use_container_width=True, hide_index=True)
        st.download_button("Download prop prices", display.to_csv(index=False), "diamond_edge_props.csv", "text/csv")

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
