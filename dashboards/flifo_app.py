"""LAX FLIFO Flight Status Dashboard — powered by SITA Flight Status Global API."""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="LAX FLIFO Dashboard", page_icon="✈️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
[data-testid="metric-container"] {
    background:#0e1f3d; border:1px solid #1e3a5f;
    border-radius:10px; padding:16px 20px;
}
[data-testid="metric-container"] label { color:#8aaccc !important; font-size:0.78rem !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { color:#fff !important; font-size:1.9rem !important; }
[data-testid="stSidebar"] { background:#0a1628; }
[data-testid="stSidebar"] * { color:#c8ddf0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "flifo_lax.csv")
TEAL, AMBER, BLUE, RED = "#00c5b2", "#ffb800", "#2196f3", "#ff4b4b"

STATUS_COLOR = {
    "On Time":          TEAL,
    "Early":            TEAL,
    "Arrived":          "#4caf7d",
    "Landed":           "#4caf7d",
    "In Air-Recovered": "#4caf7d",
    "In Air":           BLUE,
    "Departed":         "#6a9abf",
    "Enroute":          "#6a9abf",
    "On Ground":        "#5588aa",
    "Scheduled":        "#8aaccc",
    "Delayed":          AMBER,
    "Cancelled":        RED,
    "Diverted":         "#ff8c42",
}

# Aircraft body type classification
WIDE_BODY  = {"B772","B773","B77L","B77W","B788","B789","B78X","B763","B764",
              "B744","B748","A332","A333","A338","A339","A342","A343","A344",
              "A345","A346","A350","A358","A359","A35K","A380","A388"}
REGIONAL   = {"E170","E175","E190","E195","E7W","E290","CRJ7","CRJ9","CRJX",
              "CRJ1","CRJ2","DH8D","AT72","AT73","AT75","AT76","SF34"}

def _classify_body(series):
    """Vectorised body-type classification — avoids PyArrow scalar issues."""
    codes = series.astype(str).str.upper().str.strip()
    result = pd.Series("Narrow-body", index=series.index, dtype=object)
    result[codes.isin(REGIONAL)]   = "Regional"
    result[codes.isin(WIDE_BODY)]  = "Wide-body"
    return result

def pbase(**kw):
    d = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             font_color="white", title_font_color="white",
             legend=dict(font=dict(color="white")),
             margin=dict(t=40, b=10, l=10, r=10))
    d.update(kw); return d

def cbar(fmt=None):
    cb = dict(tickfont=dict(color="white"), title=dict(font=dict(color="white")))
    if fmt: cb["tickformat"] = fmt
    return cb

def lax_hhmm(s):
    """Format UTC datetime Series as LAX local time HH:MM — pure integer math, no OS tz calls."""
    mask = s.notna()
    h = ((s.dt.hour - 7) % 24).astype(object)
    m = s.dt.minute.astype(object)
    out = pd.Series("—", index=s.index, dtype=object)
    out[mask] = (h[mask].astype(str).str.zfill(2) + ":" +
                 m[mask].astype(str).str.zfill(2))
    return out


# ── Load & Enrich ─────────────────────────────────────────────────────────────
@st.cache_data
def load():
    df = pd.read_csv(DATA_PATH)
    df = df.drop_duplicates(subset=["flightId", "flight_type"]).copy()

    for col in ["scheduledTime", "estimatedTime", "actualTime"]:
        df[col+"_dt"] = pd.to_datetime(df[col], utc=True, errors="coerce")

    df["delay_mins"] = (df["actualTime_dt"] - df["scheduledTime_dt"]).dt.total_seconds() / 60
    df["delay_mins"] = df["delay_mins"].fillna(
        (df["estimatedTime_dt"] - df["scheduledTime_dt"]).dt.total_seconds() / 60)

    on_time_statuses = {"On Time","Early","Arrived","Landed","In Air-Recovered","In Air",
                        "Departed","Enroute","On Ground"}
    df["on_time"]   = df["statusText"].isin(on_time_statuses).astype(int)
    df["delayed_f"] = (df["statusText"] == "Delayed").astype(int)
    df["sched_hour"]= (df["scheduledTime_dt"].dt.hour - 7) % 24

    df["bodyType"]  = _classify_body(df["aircraftIata"])
    df["airlineName"] = df["airlineName"].fillna(df["airlineCode"])
    df["statusText"]  = df["statusText"].fillna("Unknown")
    df["otherCity"]   = df["otherCity"].fillna(df["otherAirport"])

    # Clean terminal — vectorised, no apply() to avoid PyArrow scalar issues
    t = df["terminal"].astype(str).replace({"0": "", "nan": "", "None": ""})
    is_digit = t.str.match(r"^\d+$", na=False)
    t = t.where(~is_digit, "T" + t)
    df["terminal"] = t.replace("", "Unknown").fillna("Unknown")

    df["duration"] = pd.to_numeric(df["duration"], errors="coerce")
    return df

df_all = load()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✈️ LAX FLIFO Dashboard")
    st.markdown("**SITA Flight Status Global API**")
    st.divider()
    ty_sel  = st.multiselect("Flight type", ["departures","arrivals"],
                             default=["departures","arrivals"])
    st_opts = sorted(df_all["statusText"].unique().tolist())
    st_sel  = st.multiselect("Status", st_opts, default=st_opts)
    st.divider()
    st.caption(f"📁 {len(df_all)} flights loaded")
    if st.button("🔄 Reload", use_container_width=True):
        st.cache_data.clear(); st.rerun()

df = df_all[df_all["flight_type"].isin(ty_sel) & df_all["statusText"].isin(st_sel)].copy()
if df.empty:
    st.warning("No flights match filters."); st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total      = len(df)
on_time_n  = int(df["on_time"].sum())
delayed_n  = int(df["delayed_f"].sum())
on_time_r  = df["on_time"].mean()
avg_delay  = df.loc[df["delay_mins"] > 0, "delay_mins"].mean()
avg_delay  = round(avg_delay, 1) if pd.notna(avg_delay) else 0.0
n_aircraft = df["registration"].nunique()
n_types    = df["aircraftModel"].nunique()

# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["🖥️ Live Board","📊 Overview","✈️ Aircraft","✈️ Airline",
                "🚪 Terminal","🗺️ Routes"])


# ── TAB 0: LIVE BOARD ─────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown("### LAX Flight Status Board  —  FLIFO")
    c1, c2 = st.columns(2)
    b_type = c1.selectbox("Type",   ["departures","arrivals"])
    b_stat = c2.selectbox("Status", ["ALL"] + st_opts)

    bd = df[df["flight_type"] == b_type].copy()
    if b_stat != "ALL": bd = bd[bd["statusText"] == b_stat]
    bd = bd.sort_values("scheduledTime_dt", na_position="last")

    bd["Sched"]  = lax_hhmm(bd["scheduledTime_dt"])
    bd["Actual"] = lax_hhmm(bd["actualTime_dt"])
    bd["Delay+"] = bd["delay_mins"].apply(
        lambda x: f"+{int(x)}m" if pd.notna(x) and x > 5 else
                  (f"{int(x)}m" if pd.notna(x) and x < -2 else ""))

    endpoint_label = "To" if b_type == "departures" else "From"
    bd[endpoint_label] = bd["otherAirport"].fillna("—") + "  " + \
                         bd["otherCity"].fillna("").str[:20]
    bd["Term."] = bd["terminal"].fillna("—")
    bd["Gate"]  = bd["gate"].astype(str).replace("nan","—")
    bd["A/C"]   = bd["aircraftModel"].fillna("—").str[:22]

    cols_map = {"flight":"Flight","airlineName":"Airline",endpoint_label:endpoint_label,
                "Sched":"Sched","Actual":"Actual","Delay+":"Delay+",
                "Term.":"Term.","Gate":"Gate","A/C":"Aircraft","statusText":"Status"}

    disp = bd[[c for c in cols_map if c in bd.columns]].rename(columns=cols_map)

    def _row_color(row):
        c = STATUS_COLOR.get(row.get("Status",""), "#ffffff")
        return [f"color:{c}" if col == "Status" else "" for col in disp.columns]

    st.dataframe(disp.style.apply(_row_color, axis=1),
                 use_container_width=True, hide_index=True, height=560)
    st.caption(f"{len(bd)} flights · sorted by scheduled time · "
               f"Gate/Terminal are at LAX · Actual times from SITA FLIFO API")


# ── TAB 1: OVERVIEW ───────────────────────────────────────────────────────────
with tabs[1]:
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Total Flights",   f"{total:,}")
    c2.metric("On-Time",         f"{on_time_n:,}", delta=f"{on_time_r:.1%}")
    c3.metric("Delayed",         f"{delayed_n:,}", delta=f"-{delayed_n/total:.1%}",
              delta_color="inverse")
    c4.metric("Avg Delay (min)", f"{avg_delay:.1f}")
    c5.metric("Unique Aircraft", f"{n_aircraft:,}")
    c6.metric("Aircraft Types",  f"{n_types:,}")
    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        donut = go.Figure(go.Pie(
            labels=["On-Time","Delayed","Other"],
            values=[on_time_n, delayed_n, max(0, total - on_time_n - delayed_n)],
            hole=0.58, marker_colors=[TEAL, AMBER, "#1e3a5f"],
            textinfo="label+percent",
        ))
        donut.add_annotation(text=f"<b>{on_time_r:.0%}</b><br>on-time",
                             x=0.5, y=0.5, showarrow=False,
                             font=dict(size=17, color="white"))
        donut.update_layout(**pbase(title="On-Time Performance", height=340, showlegend=True))
        st.plotly_chart(donut, use_container_width=True)

    with col_r:
        sa = df.groupby(["flight_type","statusText"]).size().reset_index(name="count")
        fig = px.bar(sa, x="flight_type", y="count", color="statusText",
                     color_discrete_map=STATUS_COLOR, barmode="stack",
                     labels={"count":"Flights","flight_type":"Type","statusText":"Status"},
                     title="Status by Flight Type")
        fig.update_layout(**pbase(height=340))
        st.plotly_chart(fig, use_container_width=True)

    col_l2, col_r2 = st.columns(2)
    with col_l2:
        hr = df.groupby("sched_hour").agg(
            avg_delay=("delay_mins", lambda x: x[x>0].mean()),
            flights=("flight","count")
        ).reset_index().fillna(0)
        fh = go.Figure()
        fh.add_bar(x=hr["sched_hour"], y=hr["flights"],
                   name="Flights", marker_color=TEAL, opacity=0.45, yaxis="y2")
        fh.add_scatter(x=hr["sched_hour"], y=hr["avg_delay"],
                       name="Avg Delay", line=dict(color=AMBER, width=2.5),
                       mode="lines+markers")
        fh.update_layout(**pbase(
            title="Delay by Hour of Day (LAX time (PDT, UTC-7))", height=300,
            yaxis=dict(title="Avg Delay (min)", color=AMBER),
            yaxis2=dict(title="Flights", overlaying="y", side="right", color=TEAL),
            xaxis=dict(title="Hour", dtick=2),
        ))
        st.plotly_chart(fh, use_container_width=True)

    with col_r2:
        dl = df[df["delay_mins"].between(-60, 180)]
        fh2 = px.histogram(dl, x="delay_mins", nbins=40,
                           color="flight_type",
                           color_discrete_map={"departures": TEAL, "arrivals": AMBER},
                           barmode="overlay", opacity=0.75,
                           labels={"delay_mins":"Delay (min)","flight_type":"Type"},
                           title="Delay Distribution")
        fh2.add_vline(x=0,  line_dash="dash", line_color="white", opacity=0.5,
                      annotation_text="On-time", annotation_font_color="white")
        fh2.add_vline(x=15, line_dash="dot",  line_color=AMBER,  opacity=0.7,
                      annotation_text="+15 min", annotation_font_color=AMBER)
        fh2.update_layout(**pbase(height=300))
        st.plotly_chart(fh2, use_container_width=True)


# ── TAB 2: AIRCRAFT ───────────────────────────────────────────────────────────
with tabs[2]:
    st.markdown("### Fleet Analysis — unique to SITA FLIFO (real aircraft data, not scheduled)")

    col_l, col_r = st.columns(2)
    with col_l:
        # Body type donut
        bt = df.groupby("bodyType").size().reset_index(name="count")
        bt_colors = {"Wide-body": TEAL, "Narrow-body": BLUE, "Regional": AMBER}
        fig_bt = go.Figure(go.Pie(
            labels=bt["bodyType"], values=bt["count"],
            hole=0.5,
            marker_colors=[bt_colors.get(b, "#8aaccc") for b in bt["bodyType"]],
            textinfo="label+percent",
        ))
        fig_bt.update_layout(**pbase(title="Fleet Mix by Body Type", height=320, showlegend=True))
        st.plotly_chart(fig_bt, use_container_width=True)

    with col_r:
        # Top aircraft models by flight count
        top_ac = df.groupby("aircraftModel").agg(
            flights=("flight","count"),
            airlines=("airlineCode","nunique"),
            avg_delay=("delay_mins", lambda x: x[x>0].mean()),
        ).reset_index().sort_values("flights", ascending=False).head(15).fillna(0)
        top_ac["avg_delay"] = top_ac["avg_delay"].round(1)
        fig_ac = px.bar(top_ac.sort_values("flights"),
                        x="flights", y="aircraftModel", orientation="h",
                        color="avg_delay",
                        color_continuous_scale=[[0,TEAL],[0.5,AMBER],[1,RED]],
                        text="flights",
                        labels={"flights":"Flights","aircraftModel":"Aircraft Model",
                                "avg_delay":"Avg Delay (min)"},
                        title="Top 15 Aircraft Models (colour = avg delay)")
        fig_ac.update_traces(textposition="outside")
        fig_ac.update_layout(**pbase(height=420, coloraxis_showscale=False))
        st.plotly_chart(fig_ac, use_container_width=True)

    # Aircraft type per airline heatmap
    ac_al = df.groupby(["airlineCode","aircraftModel"]).size().reset_index(name="flights")
    top_al = ac_al.groupby("airlineCode")["flights"].sum().nlargest(14).index
    top_ac_types = ac_al.groupby("aircraftModel")["flights"].sum().nlargest(14).index
    ac_al2 = ac_al[ac_al["airlineCode"].isin(top_al) & ac_al["aircraftModel"].isin(top_ac_types)]
    if not ac_al2.empty:
        pv_ac = ac_al2.pivot(index="airlineCode", columns="aircraftModel", values="flights").fillna(0)
        fig_hm = px.imshow(pv_ac, color_continuous_scale=[[0,"#0a1628"],[1,TEAL]],
                           aspect="auto",
                           labels={"x":"Aircraft Model","y":"Airline","color":"Flights"},
                           title="Airline × Aircraft Type (top 14 × 14)")
        fig_hm.update_layout(**pbase(height=400))
        fig_hm.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig_hm, use_container_width=True)

    # Registration counts — unique tail numbers by airline
    reg = df[df["registration"].notna() & (df["registration"]!="")].groupby("airlineCode").agg(
        tail_numbers=("registration","nunique"),
        flights=("flight","count"),
    ).reset_index().sort_values("tail_numbers", ascending=False).head(15)
    fig_reg = px.bar(reg.sort_values("tail_numbers"),
                     x="tail_numbers", y="airlineCode", orientation="h",
                     color="tail_numbers",
                     color_continuous_scale=[[0,BLUE],[1,TEAL]],
                     text="tail_numbers",
                     labels={"tail_numbers":"Unique Tail Numbers","airlineCode":"Airline"},
                     title="Unique Aircraft (Tail Numbers) per Airline at LAX")
    fig_reg.update_traces(textposition="outside")
    fig_reg.update_layout(**pbase(height=380, coloraxis_showscale=False))
    st.plotly_chart(fig_reg, use_container_width=True)

    # Duration distribution
    dur = df[df["duration"].between(30, 900)]
    fig_dur = px.histogram(dur, x="duration", nbins=50, color="bodyType",
                           color_discrete_map={"Wide-body":TEAL,"Narrow-body":BLUE,"Regional":AMBER},
                           barmode="overlay", opacity=0.75,
                           labels={"duration":"Flight Duration (min)","bodyType":"Type"},
                           title="Flight Duration Distribution by Body Type")
    fig_dur.update_layout(**pbase(height=280))
    st.plotly_chart(fig_dur, use_container_width=True)

    # Codeshare table
    st.markdown("#### Codeshare Density")
    cs_grp = df.groupby("airlineCode").agg(
        flights=("flight","count"),
        avg_codeshares=("numCodeshares","mean"),
        max_codeshares=("numCodeshares","max"),
        pct_with_cs=("numCodeshares", lambda x: (x>0).mean()),
    ).reset_index().sort_values("avg_codeshares", ascending=False).head(15)
    cs_grp["avg_codeshares"] = cs_grp["avg_codeshares"].round(2)
    cs_grp["pct_with_cs"]    = cs_grp["pct_with_cs"].apply(lambda x: f"{x:.0%}")
    st.dataframe(cs_grp.rename(columns={
        "airlineCode":"Airline","flights":"Flights",
        "avg_codeshares":"Avg Codeshares","max_codeshares":"Max Codeshares",
        "pct_with_cs":"% Flights with Codeshares"}),
        use_container_width=True, hide_index=True)


# ── TAB 3: AIRLINE ────────────────────────────────────────────────────────────
with tabs[3]:
    al = df.groupby(["airlineCode","airlineName"]).agg(
        flights=("flight","count"),
        on_time_rate=("on_time","mean"),
        delayed_n=("delayed_f","sum"),
        avg_delay=("delay_mins", lambda x: x[x>0].mean()),
        aircraft_types=("aircraftModel","nunique"),
    ).reset_index().sort_values("flights", ascending=False).fillna(0)
    al["avg_delay"] = al["avg_delay"].round(1)

    top_n  = st.slider("Top N airlines", 5, min(40, len(al)), min(20, len(al)))
    al_top = al.head(top_n)

    col_l, col_r = st.columns(2)
    with col_l:
        al_s = al_top.sort_values("on_time_rate")
        fig = px.bar(al_s, x="on_time_rate", y="airlineCode", orientation="h",
                     color="on_time_rate",
                     color_continuous_scale=[[0,AMBER],[0.6,TEAL],[1,TEAL]],
                     text=al_s["on_time_rate"].apply(lambda x: f"{x:.0%}"),
                     labels={"on_time_rate":"On-Time Rate","airlineCode":"Airline"},
                     title="On-Time Rate by Airline")
        fig.update_traces(textposition="outside")
        fig.update_xaxes(tickformat=".0%", range=[0, 1.25])
        fig.update_layout(**pbase(height=max(320, top_n*24), coloraxis_showscale=False))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        fig2 = px.scatter(al_top, x="flights", y="on_time_rate",
                          size="delayed_n", color="aircraft_types",
                          text="airlineCode", size_max=45,
                          color_continuous_scale=[[0,BLUE],[1,TEAL]],
                          labels={"flights":"Total Flights","on_time_rate":"On-Time Rate",
                                  "aircraft_types":"# A/C Types"},
                          title="Volume vs Performance (size=delays  colour=fleet variety)")
        fig2.update_traces(textposition="top center")
        fig2.update_yaxes(tickformat=".0%")
        fig2.update_layout(**pbase(height=max(320, top_n*24), showlegend=False))
        fig2.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig2, use_container_width=True)

    al_d = al_top.copy()
    al_d["on_time_rate"] = al_d["on_time_rate"].apply(lambda x: f"{x:.1%}")
    al_d["avg_delay"]    = al_d["avg_delay"].apply(lambda x: f"{x:.1f} min")
    st.dataframe(al_d.rename(columns={
        "airlineCode":"Code","airlineName":"Airline","flights":"Flights",
        "on_time_rate":"On-Time Rate","delayed_n":"Delayed",
        "avg_delay":"Avg Delay","aircraft_types":"A/C Types"}),
        use_container_width=True, hide_index=True)


# ── TAB 4: TERMINAL ───────────────────────────────────────────────────────────
with tabs[4]:
    st.caption("Terminal data is real — sourced directly from SITA FLIFO API. "
               "TBIT = Tom Bradley International Terminal.")
    st.divider()

    term_order = ["T1","T2","T3","T4","T5","T6","T7","T8","TBIT","B","Unknown"]
    df_t = df[df["terminal"] != "Unknown"]

    tm = df_t.groupby("terminal").agg(
        flights=("flight","count"),
        on_time_rate=("on_time","mean"),
        delayed_n=("delayed_f","sum"),
        avg_delay=("delay_mins", lambda x: x[x>0].mean()),
        airlines=("airlineCode","nunique"),
    ).reset_index().fillna(0)
    tm["avg_delay"] = tm["avg_delay"].round(1)
    tm["terminal"]  = pd.Categorical(tm["terminal"], categories=term_order, ordered=True)
    tm = tm.sort_values("terminal")

    col_l, col_r = st.columns(2)
    with col_l:
        fig_t = px.bar(tm, x="terminal", y="on_time_rate",
                       color="on_time_rate",
                       color_continuous_scale=[[0,AMBER],[0.6,TEAL],[1,TEAL]],
                       text=tm["on_time_rate"].apply(lambda x: f"{x:.0%}"),
                       labels={"on_time_rate":"On-Time Rate","terminal":"Terminal"},
                       title="On-Time Rate by Terminal")
        fig_t.update_traces(textposition="outside")
        fig_t.update_yaxes(tickformat=".0%", range=[0, 1.25])
        fig_t.update_layout(**pbase(height=360, coloraxis_showscale=False))
        st.plotly_chart(fig_t, use_container_width=True)

    with col_r:
        fig_tv = px.bar(tm, x="terminal", y="flights",
                        color="avg_delay",
                        color_continuous_scale=[[0,TEAL],[0.5,AMBER],[1,RED]],
                        text="flights",
                        labels={"flights":"Flights","terminal":"Terminal",
                                "avg_delay":"Avg Delay (min)"},
                        title="Flight Volume by Terminal (colour = avg delay)")
        fig_tv.update_traces(textposition="outside")
        fig_tv.update_layout(**pbase(height=360))
        fig_tv.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig_tv, use_container_width=True)

    # Terminal × Hour heatmap
    th = df_t.groupby(["terminal","sched_hour"]).size().reset_index(name="flights")
    if not th.empty:
        pv_th = th.pivot(index="terminal", columns="sched_hour",
                         values="flights").fillna(0)
        pv_th.index = pd.CategoricalIndex(pv_th.index,
                          categories=[t for t in term_order if t in pv_th.index],
                          ordered=True)
        pv_th = pv_th.sort_index()
        fig_hm = px.imshow(pv_th,
                           color_continuous_scale=[[0,"#0a1628"],[1,TEAL]],
                           aspect="auto",
                           labels={"x":"Hour of Day","y":"Terminal","color":"Flights"},
                           title="Terminal × Hour — Flight Volume Heatmap (LAX time (PDT, UTC-7))")
        fig_hm.update_layout(**pbase(height=340))
        fig_hm.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig_hm, use_container_width=True)

    # Airlines per terminal
    al_t = df_t.groupby(["terminal","airlineCode"]).size().reset_index(name="flights")
    top_terms = al_t.groupby("terminal")["flights"].sum().nlargest(8).index
    al_t2 = al_t[al_t["terminal"].isin(top_terms)]
    if not al_t2.empty:
        fig_at = px.bar(al_t2, x="terminal", y="flights", color="airlineCode",
                        barmode="stack",
                        labels={"flights":"Flights","terminal":"Terminal","airlineCode":"Airline"},
                        title="Airlines per Terminal")
        fig_at.update_layout(**pbase(height=340))
        st.plotly_chart(fig_at, use_container_width=True)

    tm_d = tm.copy()
    tm_d["on_time_rate"] = tm_d["on_time_rate"].apply(lambda x: f"{x:.1%}")
    tm_d["avg_delay"]    = tm_d["avg_delay"].apply(lambda x: f"{x:.1f} min")
    st.dataframe(tm_d.rename(columns={
        "terminal":"Terminal","flights":"Flights","on_time_rate":"On-Time Rate",
        "delayed_n":"Delayed","avg_delay":"Avg Delay","airlines":"Airlines"}),
        use_container_width=True, hide_index=True)


# ── TAB 5: ROUTES ─────────────────────────────────────────────────────────────
with tabs[5]:
    c_rt, _ = st.columns([1,3])
    route_type = c_rt.radio("View", ["Departures","Arrivals"], horizontal=True)

    ft = "departures" if route_type == "Departures" else "arrivals"
    rt = df[df["flight_type"] == ft].groupby(["otherAirport","otherCity"]).agg(
        flights=("flight","count"),
        on_time=("on_time","mean"),
        avg_delay=("delay_mins", lambda x: x[x>0].mean()),
    ).reset_index().sort_values("flights", ascending=False).fillna(0)
    rt["avg_delay"] = rt["avg_delay"].round(1)
    rt30 = rt.head(30)

    col_l, col_r = st.columns(2)
    with col_l:
        fig_rt = px.bar(rt30.head(20).sort_values("flights"),
                        x="flights", y="otherAirport", orientation="h",
                        color="on_time",
                        color_continuous_scale=[[0,AMBER],[0.6,TEAL],[1,TEAL]],
                        text="flights",
                        hover_data=["otherCity","avg_delay"],
                        labels={"flights":"Flights","otherAirport":"Airport",
                                "on_time":"On-Time","otherCity":"City"},
                        title="Top 20 Routes by Volume")
        fig_rt.update_traces(textposition="outside")
        fig_rt.update_layout(**pbase(height=520, coloraxis_showscale=False))
        st.plotly_chart(fig_rt, use_container_width=True)

    with col_r:
        fig_tree = px.treemap(rt30, path=["otherCity"], values="flights",
                              color="on_time",
                              color_continuous_scale=[[0,AMBER],[0.6,TEAL],[1,TEAL]],
                              title="Treemap: size=volume  colour=on-time rate",
                              hover_data=["avg_delay"])
        fig_tree.update_layout(**pbase(height=520))
        fig_tree.update_coloraxes(colorbar=cbar(".0%"))
        st.plotly_chart(fig_tree, use_container_width=True)

    # Aircraft × Route scatter
    ac_rt = df[df["flight_type"] == ft].groupby(
        ["otherAirport","aircraftModel","bodyType"]
    ).agg(flights=("flight","count")).reset_index()
    top_routes = ac_rt.groupby("otherAirport")["flights"].sum().nlargest(20).index
    ac_rt2 = ac_rt[ac_rt["otherAirport"].isin(top_routes)]
    if not ac_rt2.empty:
        bt_colors = {"Wide-body": TEAL, "Narrow-body": BLUE, "Regional": AMBER}
        fig_sc = px.scatter(ac_rt2, x="otherAirport", y="aircraftModel",
                            size="flights", color="bodyType",
                            color_discrete_map=bt_colors,
                            size_max=30,
                            labels={"otherAirport":"Route","aircraftModel":"Aircraft",
                                    "bodyType":"Body Type","flights":"Flights"},
                            title="Aircraft Type × Route (top 20 routes)")
        fig_sc.update_layout(**pbase(height=480))
        st.plotly_chart(fig_sc, use_container_width=True)

    st.dataframe(rt.head(30).rename(columns={
        "otherAirport":"Airport","otherCity":"City","flights":"Flights",
        "on_time":"On-Time","avg_delay":"Avg Delay (min)"}),
        use_container_width=True, hide_index=True)
