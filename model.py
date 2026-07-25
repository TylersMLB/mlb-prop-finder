
import math
import pandas as pd
from constants import PARK_RUN_FACTOR
from data_sources import pitcher_stats, weather_forecast

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
