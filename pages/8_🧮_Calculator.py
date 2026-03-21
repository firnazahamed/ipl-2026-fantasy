import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(layout="wide")
st.title("Points Calculator")

# ── Inputs ────────────────────────────────────────────────────────────────────
col_bat, col_bowl, col_extra = st.columns(3, gap="large")

with col_bat:
    st.subheader("🏏 Batting")
    batted = st.checkbox("Did bat", value=True)
    runs   = st.number_input("Runs",  min_value=0, value=0, step=1, disabled=not batted)
    balls  = st.number_input("Balls", min_value=0, value=0, step=1, disabled=not batted)
    fours  = st.number_input("4s",    min_value=0, value=0, step=1, disabled=not batted)
    sixes  = st.number_input("6s",    min_value=0, value=0, step=1, disabled=not batted)

with col_bowl:
    st.subheader("🎳 Bowling")
    bowled    = st.checkbox("Did bowl", value=True)
    overs_str = st.text_input("Overs", value="0.0", help="e.g. 4.2 = 4 overs 2 balls", disabled=not bowled)
    runs_c    = st.number_input("Runs conceded", min_value=0, value=0, step=1, disabled=not bowled)
    wickets   = st.number_input("Wickets",   min_value=0, max_value=10, value=0, step=1, disabled=not bowled)
    dots      = st.number_input("Dot balls", min_value=0, value=0, step=1, disabled=not bowled)
    maidens   = st.number_input("Maidens",   min_value=0, value=0, step=1, disabled=not bowled)

with col_extra:
    st.subheader("🧤 Fielding & Bonus")
    catches  = st.number_input("Catches",   min_value=0, value=0, step=1)
    runouts  = st.number_input("Run-outs",  min_value=0, value=0, step=1)
    mom      = st.checkbox("Man of the Match (+25)")
    win_team = st.checkbox("Winning team (+5)")

st.divider()

# ── Calculations ──────────────────────────────────────────────────────────────

# Batting
if batted:
    bat_base      = int(runs)
    bat_pace      = int(runs - balls)
    bat_milestone = {0: 0, 1: 10, 2: 20, 3: 30}.get(min(int(np.floor(runs / 25)), 3), 50)
    duck          = batted and runs == 0 and balls > 0
    bat_impact    = int(fours + 2 * sixes + (-5 if duck else 0))
    bat_total     = bat_base + bat_pace + bat_milestone + bat_impact
else:
    bat_base = bat_pace = bat_milestone = bat_impact = bat_total = 0

# Bowling
if bowled:
    try:
        parts   = str(overs_str).split(".")
        balls_b = int(parts[0]) * 6 + (int(parts[1]) if len(parts) > 1 and parts[1] else 0)
    except Exception:
        balls_b = 0

    econ = (runs_c * 6 / balls_b) if balls_b > 0 else 0.0

    bowl_base = int(25 * wickets)

    if balls_b == 0:
        bowl_pace  = 0
        econ_label = "—"
        econ_tier  = "No balls bowled"
    elif econ < 9:
        bowl_pace  = int(np.round(3 * (balls_b * 1.5 - runs_c)))
        econ_label = f"{econ:.2f}"
        econ_tier  = "Econ < 9 → 3×(balls×1.5 − runs)"
    elif econ <= 12:
        bowl_pace  = 0
        econ_label = f"{econ:.2f}"
        econ_tier  = "Econ 9–12 → 0 pts"
    else:
        bowl_pace  = int(np.round(balls_b * 2 - runs_c))
        econ_label = f"{econ:.2f}"
        econ_tier  = "Econ > 12 → balls×2 − runs"

    bowl_milestone = {0: 0, 1: 0, 2: 10, 3: 20, 4: 30}.get(int(wickets), 50)
    bowl_impact    = int(np.round(1.5 * dots + maidens * 30))
    bowl_total     = bowl_base + bowl_pace + bowl_milestone + bowl_impact
else:
    bowl_base = bowl_pace = bowl_milestone = bowl_impact = bowl_total = 0
    econ_label = "—"
    econ_tier  = "—"

# Fielding & Bonus
field_total = int((catches + runouts) * 10)
bonus_total = int(mom * 25 + win_team * 5)
grand_total = bat_total + bowl_total + field_total + bonus_total

# ── Results ───────────────────────────────────────────────────────────────────
st.subheader("Results")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Batting",  bat_total)
m2.metric("Bowling",  bowl_total)
m3.metric("Fielding", field_total)
m4.metric("Bonus",    bonus_total)
m5.metric("Total Points", grand_total, delta=None)

st.divider()

res1, res2, res3 = st.columns(3, gap="large")

with res1:
    st.markdown("**Batting Breakdown**")
    bat_df = pd.DataFrame({
        "Component": ["Base (runs)", "Pace (SR)", "Milestone", "Impact"],
        "Formula": [
            f"{runs} runs",
            f"{runs} − {balls}",
            f"≥{min(int(np.floor(runs/25)),3)*25 if batted else 0} runs",
            f"{fours}×1 + {sixes}×2{' − 5 (duck)' if duck else ''}" ,
        ],
        "Points": [bat_base, bat_pace, bat_milestone, bat_impact],
    }) if batted else pd.DataFrame({"Component": ["—"], "Formula": ["Did not bat"], "Points": [0]})
    st.dataframe(bat_df, hide_index=True, use_container_width=True)

with res2:
    st.markdown("**Bowling Breakdown**")
    bowl_df = pd.DataFrame({
        "Component": ["Base (wickets)", "Economy", "Milestone", "Impact"],
        "Formula": [
            f"{wickets} wkts × 25",
            econ_tier,
            f"{wickets} wkts",
            f"{dots}×1.5 + {maidens}×30",
        ],
        "Points": [bowl_base, bowl_pace, bowl_milestone, bowl_impact],
    }) if bowled else pd.DataFrame({"Component": ["—"], "Formula": ["Did not bowl"], "Points": [0]})
    st.dataframe(bowl_df, hide_index=True, use_container_width=True)

with res3:
    st.markdown("**Fielding & Bonus Breakdown**")
    extra_df = pd.DataFrame({
        "Component": ["Catches", "Run-outs", "MOM", "Winning team"],
        "Formula": [f"{catches}×10", f"{runouts}×10", "+25" if mom else "—", "+5" if win_team else "—"],
        "Points": [catches * 10, runouts * 10, 25 if mom else 0, 5 if win_team else 0],
    })
    st.dataframe(extra_df, hide_index=True, use_container_width=True)
