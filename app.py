"""Streamlit entry point for Plant Process Optimization Control."""

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from optimisation import (
    ACTIONS, FIRST_SCAN, LINES, Economics, Limits, baseline_for, evaluate,
    readings, scan_time,
)

st.set_page_config(page_title="Plant Process Optimization Control", page_icon="◈", layout="wide")
st.html(Path(__file__).with_name("style.css"))

st.session_state.setdefault("step", FIRST_SCAN)
st.session_state.setdefault("settings", {})
st.session_state.setdefault("decisions", {})


def money(value, signed=False):
    sign = "+" if signed and value > 0 else "−" if value < 0 else ""
    return f"{sign}RM {abs(value):,.0f}"


def advance():
    st.session_state.step += 1
    st.session_state.last_auto_scan = monotonic()


def heading(kicker, title, description, badge):
    st.html(f"""
        <div class="tower-hero">
            <div class="tower-kicker">{kicker}</div>
            <div class="tower-badge">{badge}</div>
            <h1>{title}</h1>
            <p>{description}</p>
        </div>
    """)


def trend_chart(history, metric, label, unit, colour, reference=None):
    figure = go.Figure(go.Scatter(
        x=history["Time"], y=history[metric], mode="lines",
        line=dict(color=colour, width=2.5), fill="tozeroy" if metric == "Product" else None,
        fillcolor="rgba(8,118,101,0.10)",
        hovertemplate=f"%{{x|%H:%M}}<br>%{{y:.2f}} {unit}<extra></extra>",
    ))
    if reference is not None:
        figure.add_hline(y=reference, line_dash="dot", line_color="#687c90",
                         annotation_text=f"Reference {reference:g} {unit}",
                         annotation_position="top left", annotation_font_color="#43596d")
    values = history[metric].tolist()
    if reference is not None:
        values.append(reference)
    lower, upper = min(values), max(values)
    padding = max((upper - lower) * .22, .25)
    figure.update_layout(
        height=205, margin=dict(l=8, r=12, t=16, b=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#43596d", size=11),
        showlegend=False,
    )
    figure.update_xaxes(showgrid=False, tickformat="%H:%M", nticks=5, fixedrange=True)
    figure.update_yaxes(gridcolor="#d8e3eb", title_text=unit, zeroline=False,
                        range=[lower - padding, upper + padding], fixedrange=True)
    with st.container(border=True):
        st.markdown(f"**{label}**")
        st.plotly_chart(figure, config={"displayModeBar": False}, key=f"trend-{metric}")


def monitor(line, step, limits, economics, base, ranked, live):
    heading("OPERATIONS INTELLIGENCE  /  01", "Plant Process Optimization Control",
            "Monitor the circuit, test operating changes and review the value of the next move.",
            "AUTO-SCAN ACTIVE" if live else "MONITOR PAUSED")
    left, right = st.columns([4, 1], vertical_alignment="bottom")
    left.subheader(line.name)
    left.caption(f"{line.profile} · Scan {step - FIRST_SCAN + 1:03d} · "
                 f"{scan_time(step):%d %b %Y, %H:%M} MYT · 1-hour rolling baseline")
    right.button("Advance one interval", on_click=advance, width="stretch")
    hold = next(item for item in ranked if item.action == ACTIONS[0])
    best = ranked[0]
    previous = baseline_for(line, step - 4)
    columns = st.columns(5)
    metrics = (
        ("Concentrate output", f"{base.product:.1f} t/h", f"{base.product - previous.product:+.1f} t/h", "normal"),
        ("Energy intensity", f"{base.intensity:.1f} kWh/t", f"{base.intensity - previous.intensity:+.1f} kWh/t", "inverse"),
        ("Metal recovery", f"{base.recovery:.1%}", f"{(base.recovery - previous.recovery)*100:+.2f} pp", "normal"),
        ("Concentrate grade", f"{base.grade:.1%}", f"{(base.grade - previous.grade)*100:+.2f} pp", "normal"),
        ("Stability index", f"{base.stability:.1f}/100", f"{base.stability - previous.stability:+.1f} pts", "normal"),
    )
    for column, (label, value, delta, color) in zip(columns, metrics):
        column.metric(label, value, delta, delta_color=color, border=True)
    st.caption("Metric changes compare with the previous hour. Energy intensity is per tonne of concentrate.")

    summary, evidence = st.columns([1.12, 1])
    with summary.container(border=True):
        st.markdown('<div class="tower-kicker">AGENT RECOMMENDATION</div>', unsafe_allow_html=True)
        if best.violations:
            st.subheader("Escalate operating constraints")
            st.write("All six scenarios breach at least one configured limit. Review the constraints with the operator.")
        else:
            st.subheader(best.action.name)
            st.write(best.action.instruction)
            st.markdown(f"**{money(best.impact.net, signed=True)} over {economics.hours} hours** · Estimated net impact")
        st.caption("Open Scenario Lab to compare options, adjust assumptions and record a review.")
    with evidence.container(border=True):
        st.markdown('<div class="tower-kicker">OBSERVED SIGNALS</div>', unsafe_allow_html=True)
        if hold.violations:
            st.markdown("**Baseline outside operating limits**")
            st.write(" · ".join(hold.violations))
        else:
            st.markdown("**Baseline within operating limits**")
            st.write(f"Feed {base.feed:.1f} t/h · Power {base.power:,.0f} kW")
        energy_gap = base.intensity - line.energy_target
        direction = "above" if energy_gap > 0 else "below" if energy_gap < 0 else "at"
        st.write(f"Energy intensity {direction} the line target ({line.energy_target:g} kWh/t).")

    st.subheader("Circuit trends")
    st.caption("Latest 24 synthetic readings · 15-minute intervals · MYT")
    history = []
    for period in range(step - 23, step + 1):
        point = readings(line, period)
        history.append({"Time": scan_time(period).replace(tzinfo=None),
                        "Product": point.product, "Energy": point.intensity,
                        "Recovery": point.recovery * 100, "Stability": point.stability})
    frame = pd.DataFrame(history)
    first, second = st.columns(2)
    with first:
        trend_chart(frame, "Product", "Concentrate output", "t/h", "#087665")
    with second:
        trend_chart(frame, "Energy", "Specific energy", "kWh/t", "#a5520b", line.energy_target)
    with st.expander("Recovery and stability trends"):
        first, second = st.columns(2)
        with first:
            trend_chart(frame, "Recovery", "Metal recovery", "%", "#345ca7", limits.min_recovery * 100)
        with second:
            trend_chart(frame, "Stability", "Stability index", "/100", "#7751a6", limits.min_stability)


def model_settings(line, limits, economics):
    with st.expander("Operating limits and financial assumptions"):
        with st.form(f"settings-{line.code}"):
            st.markdown("**Hard operating limits**")
            a, b, c = st.columns(3)
            feed = a.number_input("Maximum feed (t/h)", 1.0, 200.0, float(limits.feed_cap), step=1.0)
            power = b.number_input("Maximum power (kW)", 100.0, 5000.0, float(limits.power_cap), step=10.0)
            stability = c.number_input("Minimum stability (/100)", 0.0, 100.0, float(limits.min_stability), step=1.0)
            a, b = st.columns(2)
            grade = a.number_input("Minimum concentrate grade (%)", 0.0, 100.0,
                                   round(limits.min_grade * 100, 2), step=.1)
            recovery = b.number_input("Minimum metal recovery (%)", 0.0, 100.0,
                                      round(limits.min_recovery * 100, 2), step=.1)
            st.markdown("**Financial assumptions (MYR)**")
            a, b, c, d = st.columns(4)
            hours = a.number_input("Horizon (hours)", 1, 72, economics.hours)
            value = b.number_input("Product value (RM/t)", 0.0, 10000.0, float(economics.product_value), step=10.0)
            cost = c.number_input("Variable feed cost (RM/t)", 0.0, 10000.0, float(economics.feed_cost), step=5.0)
            tariff = d.number_input("Power tariff (RM/kWh)", 0.0, 10.0, economics.tariff, step=.01)
            saved = st.form_submit_button("Apply limits and assumptions")
        if saved:
            limits = Limits(feed, power, grade / 100, recovery / 100, stability)
            economics = Economics(hours, value, cost, tariff)
            st.session_state.settings[line.code] = limits, economics
            st.success("Assumptions applied to this line.")
    return limits, economics


def decision_review(line, step, limits, economics, base, best):
    st.subheader("Operator review")
    decision_id = f"{line.code}-{step:05d}"
    recorded = st.session_state.decisions.get(decision_id)
    if recorded:
        st.info(f"{recorded['Decision']} · {recorded['Scenario']} · Reference {decision_id}")
        st.caption("This scan already has a decision. Advance the monitor for a new review.")
        return
    actionable = not best.violations and best.action != ACTIONS[0]
    options = ("Approve simulated trial", "Defer") if actionable else ("Acknowledge", "Defer")
    scenario = "Escalate operating constraints" if best.violations else best.action.name
    with st.form(f"review-{decision_id}"):
        st.write(f"**{scenario}** · Reference `{decision_id}`")
        status = st.selectbox("Review outcome", options, index=None, placeholder="Select a review outcome")
        note = st.text_input("Review note", placeholder="Record why you chose this outcome", max_chars=200)
        st.caption("Approval records a simulated trial for review. Any real trial requires a separate site process.")
        submit = st.form_submit_button("Record decision", type="primary")
    if submit:
        if status is None or not note.strip():
            st.warning("Select a review outcome and enter a note.")
            return
        result = best.process if not best.violations else None
        st.session_state.decisions[decision_id] = {
            "Reference": decision_id, "Line": line.name, "Scan time (MYT)": scan_time(step).isoformat(),
            "Decision time (UTC)": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "Decision": status, "Scenario": scenario, "Note": note.strip(),
            "Estimated net (MYR)": round(best.impact.net, 2) if result else None,
            "Baseline output (t/h)": round(base.product, 3),
            "Projected output (t/h)": round(result.product, 3) if result else None,
            "Baseline power (kW)": round(base.power, 3),
            "Projected power (kW)": round(result.power, 3) if result else None,
            "Projected grade (%)": round(result.grade * 100, 3) if result else None,
            "Projected recovery (%)": round(result.recovery * 100, 3) if result else None,
            "Projected stability": round(result.stability, 3) if result else None,
            **{f"Limit {name}": value for name, value in asdict(limits).items()},
            **{f"Economics {name}": value for name, value in asdict(economics).items()},
        }
        st.rerun()


def scenario_lab(line, step, limits, economics, base):
    heading("OPERATIONS INTELLIGENCE  /  02", "Scenario Lab",
            "Compare modelled operating actions on the same baseline and review their estimated financial impact.",
            "SCAN FROZEN")
    st.subheader(line.name)
    st.caption(f"Frozen at {scan_time(step):%d %b %Y, %H:%M} MYT · "
               "The monitor pauses here so the baseline stays fixed during review.")
    limits, economics = model_settings(line, limits, economics)
    ranked = evaluate(base, limits, economics)
    best = ranked[0]
    feasible = sum(not item.violations for item in ranked)
    cards = st.columns([1.5, 1, 1])
    cards[0].metric("Recommended action",
                    "Escalate constraints" if not feasible else best.action.name, border=True)
    cards[1].metric(f"Estimated net · {economics.hours} hours",
                    money(best.impact.net, signed=True) if feasible else "Unavailable", border=True)
    cards[2].metric("Within operating limits", f"{feasible} / {len(ranked)} scenarios", border=True)
    if not feasible:
        st.warning("Every modelled option breaches at least one limit. Escalate for operator review.")
    elif best.impact.net < 0:
        st.warning("The baseline breaches a limit. The best feasible action restores compliance at an estimated cost.")
    elif best.action == ACTIONS[0]:
        st.info("The baseline passes all limits. No feasible change improves estimated net value.")
    else:
        st.write(best.action.instruction)
    st.subheader("Operating trade-offs")
    st.caption(f"Baseline · Feed {base.feed:.1f} t/h · Power {base.power:,.0f} kW · "
               f"Output {base.product:.1f} t/h · Grade {base.grade:.2%} · Recovery {base.recovery:.2%} · "
               f"Stability {base.stability:.1f}/100")
    rows = []
    for item in ranked:
        point = item.process
        rows.append({
            "Scenario": item.action.name,
            "Status": "Blocked" if item.violations else "Recommended" if item is best else "Feasible",
            "Net impact": money(item.impact.net, signed=True),
            "Output t/h": f"{point.product:.1f}",
            "Energy kWh/t": f"{point.intensity:.1f}",
            "Power kW": f"{point.power:,.0f}",
            "Feed t/h": f"{point.feed:.1f}",
            "Grade": f"{point.grade:.2%}",
            "Recovery": f"{point.recovery:.2%}",
            "Stability": f"{point.stability:.1f}",
            "Breached limits": " · ".join(item.violations) or "—",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=254,
                 column_config={"Scenario": st.column_config.TextColumn(width=195),
                                "Breached limits": st.column_config.TextColumn(width=310)})
    st.caption("Feasible options rank by net impact. Blocked options display modelled values for comparison and are ineligible for approval.")

    if feasible:
        st.subheader("Financial breakdown")
        st.caption(f"Change versus the frozen baseline over {economics.hours} hours, assuming steady rates.")
        a, b, c, d = st.columns(4)
        a.metric("Concentrate value", money(best.impact.product, signed=True), border=True)
        b.metric("Feed cost impact", money(best.impact.feed, signed=True), border=True)
        c.metric("Electricity cost impact", money(best.impact.power, signed=True), border=True)
        d.metric("Trial cost impact", money(-best.impact.action_cost, signed=True), border=True)
        low, high = best.impact.sensitivity
        energy = (best.process.power - base.power) * economics.hours
        st.caption(f"Modelled electricity change {energy:+,.0f} kWh · "
                   f"Net impact range {money(low, signed=True)} to {money(high, signed=True)} "
                   "when product value and electricity tariff each vary by ±20%.")
        with st.expander("How the estimate works"):
            st.write("Incremental concentrate × product value, less incremental ore feed × variable feed cost, "
                     "less incremental electricity × tariff, less the one-off trial cost.")
            st.write("The demo uses one product value per tonne. Contract penalties, downtime and realised savings "
                     "are outside this estimate. Process response coefficients and financial inputs are illustrative.")
    decision_review(line, step, limits, economics, base, best)


def excel_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def decision_log():
    heading("OPERATIONS INTELLIGENCE  /  03", "Decision Log",
            "Review operator outcomes and download the model assumptions behind each decision.",
            "SESSION RECORD")
    decisions = list(reversed(st.session_state.decisions.values()))
    if not decisions:
        st.info("No decisions recorded yet. Open Scenario Lab, select a review outcome and add a note.")
        return
    frame = pd.DataFrame(decisions)
    st.caption(f"{len(frame)} recorded · All lines · Export before ending the browser session.")
    st.dataframe(frame[["Reference", "Line", "Decision", "Scenario", "Estimated net (MYR)", "Note"]],
                 hide_index=True, width="stretch")
    csv = frame.map(excel_safe).to_csv(index=False).encode("utf-8-sig")
    st.download_button("Download decision log", csv, "process_optimisation_decisions.csv", "text/csv")


with st.sidebar:
    st.html("""
        <div class="tower-brand"><span>◈</span> OPS TOWER</div>
        <div class="tower-kicker sidebar-kicker">PROCESS OPTIMISATION</div>
    """)
    page = st.radio("Workspace", ["Live Monitor", "Scenario Lab", "Decision Log"])
    line_name = st.selectbox("Operating line", [item.name for item in LINES])
    line = next(item for item in LINES if item.name == line_name)
    auto = st.toggle("Auto-scan in Live Monitor", value=True)
    st.caption("Every 10 seconds advances one 15-minute sample. Scenario Lab holds the scan steady for review.")
    st.divider()
    st.markdown("**Synthetic demo**")
    st.caption("Three mineral-processing lines · Simulated data · Advisory workflow")

live = auto and page == "Live Monitor"
if page == "Decision Log":
    decision_log()
else:
    @st.fragment(run_every=10 if live else None)
    def workspace():
        # A timed fragment run advances the simulated clock. Full runs and widget
        # interactions keep the current scan unless the user explicitly advances.
        now = monotonic()
        last = st.session_state.get("last_auto_scan")
        if live and last is not None and now - last >= 9.5:
            advance()
        step = st.session_state.step
        limits, economics = st.session_state.settings.get(
            line.code, (Limits(line.feed_cap, line.power_cap), Economics())
        )
        base = baseline_for(line, step)
        if page == "Live Monitor":
            monitor(line, step, limits, economics, base, evaluate(base, limits, economics), live)
        else:
            scenario_lab(line, step, limits, economics, base)

    st.session_state.last_auto_scan = monotonic() if live else None
    workspace()
