"""LAX — Los Angeles International Airport Flight Performance Dashboard."""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="LAX Flight Performance", page_icon="✈️",
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
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "flights_latest.csv")
TEAL, AMBER, BLUE, RED = "#00c5b2", "#ffb800", "#2196f3", "#ff4b4b"
STATUS_COLOR = {
    "Scheduled": "#8aaccc", "On Time": TEAL, "Delayed": AMBER,
    "Departed": "#6a9abf", "Landed": "#6a9abf", "Arrived": "#6a9abf",
    "On Ground": "#5588aa", "Cancelled": RED, "Diverted": RED,
}

# LAX terminal assignments by operating airline IATA code (as of 2025)
LAX_TERMINAL = {
    # Terminal 1 — budget domestic
    "WN": "T1", "NK": "T1", "F9": "T1", "SY": "T1", "Y4": "T1",
    # Terminal 2/3 — Delta hub
    "DL": "T2/T3", "KE": "T2", "WS": "T2", "PD": "T2",
    # Terminal 4 — American domestic
    "AA": "T4",
    # Terminal 5/6 — Alaska hub, American intl, JetBlue
    "AS": "T5/T6", "QX": "T5", "OO": "T5", "B6": "T5",
    # Terminal 7/8 — United hub
    "UA": "T7/T8", "XE": "T7",
    # Tom Bradley International Terminal
    "AC": "TBIT", "QF": "TBIT", "BA": "TBIT", "CX": "TBIT",
    "CI": "TBIT", "MU": "TBIT", "JL": "TBIT", "SQ": "TBIT",
    "AY": "TBIT", "AF": "TBIT", "KL": "TBIT", "IB": "TBIT",
    "AZ": "TBIT", "EI": "TBIT", "AT": "TBIT", "GF": "TBIT",
    "FI": "TBIT", "LO": "TBIT", "NZ": "TBIT", "PR": "TBIT",
    "MH": "TBIT", "AM": "TBIT", "LA": "TBIT", "CM": "TBIT",
    "AV": "TBIT", "TP": "TBIT", "OS": "TBIT", "OZ": "TBIT",
    "TN": "TBIT", "VS": "TBIT", "VA": "TBIT", "AD": "TBIT",
    "KQ": "TBIT", "JU": "TBIT",
}

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


# ── Load ──────────────────────────────────────────────────────────────────────
@st.cache_data
def load():
    df = pd.read_csv(DATA_PATH)
    df["sched_dt"]   = pd.to_datetime(df["scheduledDate"]+" "+df["scheduledTime"], errors="coerce")
    df["est_dt"]     = pd.to_datetime(df["estimatedDate"]+" "+df["estimatedTime"], errors="coerce")
    df["delay_mins"] = (df["est_dt"]-df["sched_dt"]).dt.total_seconds()/60
    df["on_time"]    = (~df["delayed"].astype(str).str.lower().eq("true")).astype(int)
    df["delayed_f"]  = (df["delayed"].astype(str).str.lower().eq("true")).astype(int)
    df["sched_hour"] = df["sched_dt"].dt.hour
    df["status"]     = df["status"].fillna("Unknown")
    df["airlineName"]= df["airlineName"].fillna(df["airlineCode"])
    for col in ["destinationAirportCode","destinationAirportName",
                "destinationCountryCode","originAirportCode","weather"]:
        if col in df.columns: df[col] = df[col].fillna("Unknown")
    df["terminal"] = df["operatingAirlineCode"].map(LAX_TERMINAL).fillna("Other")
    return df

df_all = load()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✈️ LAX Flight Performance")
    st.markdown("**Los Angeles International Airport**")
    st.divider()
    ty_sel  = st.multiselect("Flight type", ["departures","arrivals"], default=["departures","arrivals"])
    st_opts = sorted(df_all["status"].unique().tolist())
    st_sel  = st.multiselect("Status", st_opts, default=st_opts)
    st.divider()
    st.caption(f"📁 {len(df_all)} flights loaded")
    if st.button("🔄 Reload", use_container_width=True):
        st.cache_data.clear(); st.rerun()

df = df_all[df_all["flight_type"].isin(ty_sel) & df_all["status"].isin(st_sel)].copy()
if df.empty:
    st.warning("No flights match filters."); st.stop()

# ── KPIs ──────────────────────────────────────────────────────────────────────
total     = len(df)
on_time_n = int(df["on_time"].sum())
delayed_n = int(df["delayed_f"].sum())
on_time_r = df["on_time"].mean()
avg_delay = df.loc[df["delay_mins"]>0,"delay_mins"].mean()
avg_delay = round(avg_delay,1) if not pd.isna(avg_delay) else 0.0
worst_al  = df[df["delayed_f"]==1]["airlineCode"].mode()
worst_al  = worst_al.iloc[0] if len(worst_al) else "—"

# ══════════════════════════════════════════════════════════════════════════════
tabs = st.tabs(["🖥️ Live Board","📊 Overview","✈️ Airline","🚪 Terminal","🗺️ Routes"])


# ── TAB 0: BOARD ──────────────────────────────────────────────────────────────
with tabs[0]:
    st.markdown("### LAX Flight Information Display")
    c1, c2 = st.columns(2)
    b_type = c1.selectbox("Type",   ["departures","arrivals"])
    b_stat = c2.selectbox("Status", ["ALL"]+st_opts)

    bd = df[df["flight_type"]==b_type].copy()
    if b_stat != "ALL": bd = bd[bd["status"]==b_stat]
    bd = bd.sort_values("sched_dt", na_position="last")

    bd["Sched"] = bd["sched_dt"].dt.strftime("%H:%M").fillna("—")
    bd["Est."]  = bd["est_dt"].dt.strftime("%H:%M").fillna("—")
    bd["Delay+"]= bd["delay_mins"].apply(lambda x: f"+{int(x)}m" if pd.notna(x) and x>0 else "")

    if b_type == "departures":
        bd["To"] = bd["destinationAirportCode"].fillna("—") + "  " + \
                   bd["destinationAirportName"].fillna("").str[:24]
        cols_map = {"flight":"Flight","airlineName":"Airline","To":"To",
                    "Sched":"Sched","Est.":"Est.","Delay+":"Delay+","status":"Status"}
    else:
        bd["From"] = bd["originAirportCode"].fillna("—") + "  " + \
                     bd["originAirportName"].fillna("").str[:24]
        cols_map = {"flight":"Flight","airlineName":"Airline","From":"From",
                    "Sched":"Sched","Est.":"Est.","Delay+":"Delay+","status":"Status"}

    disp = bd[[c for c in cols_map if c in bd.columns]].rename(columns=cols_map)

    def _row_color(row):
        c = STATUS_COLOR.get(row.get("Status",""), "#ffffff")
        return [f"color:{c}" if col=="Status" else "" for col in disp.columns]

    st.dataframe(disp.style.apply(_row_color, axis=1),
                 use_container_width=True, hide_index=True, height=540)
    st.caption(f"{len(bd)} flights · sorted by scheduled time")


# ── TAB 1: OVERVIEW ───────────────────────────────────────────────────────────
with tabs[1]:
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Flights",   f"{total:,}")
    c2.metric("On-Time",         f"{on_time_n:,}", delta=f"{on_time_r:.1%}")
    c3.metric("Delayed",         f"{delayed_n:,}", delta=f"-{delayed_n/total:.1%}",
              delta_color="inverse")
    c4.metric("Avg Delay (min)", f"{avg_delay:.1f}")
    c5.metric("Most Delayed",    worst_al)
    st.divider()

    col_l, col_r = st.columns(2)
    with col_l:
        donut = go.Figure(go.Pie(
            labels=["On-Time","Delayed","Other"],
            values=[on_time_n, delayed_n, max(0,total-on_time_n-delayed_n)],
            hole=0.58, marker_colors=[TEAL, AMBER, "#1e3a5f"],
            textinfo="label+percent",
        ))
        donut.add_annotation(text=f"<b>{on_time_r:.0%}</b><br>on-time",
                             x=0.5, y=0.5, showarrow=False,
                             font=dict(size=17, color="white"))
        donut.update_layout(**pbase(title="On-Time Performance", height=340, showlegend=True))
        st.plotly_chart(donut, use_container_width=True)

    with col_r:
        sa = df.groupby(["flight_type","status"]).size().reset_index(name="count")
        fig = px.bar(sa, x="flight_type", y="count", color="status",
                     color_discrete_map=STATUS_COLOR, barmode="stack",
                     labels={"count":"Flights","flight_type":"Type","status":"Status"},
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
                   name="Flights", marker_color=TEAL, opacity=0.5, yaxis="y2")
        fh.add_scatter(x=hr["sched_hour"], y=hr["avg_delay"],
                       name="Avg Delay", line=dict(color=AMBER, width=2.5),
                       mode="lines+markers")
        fh.update_layout(**pbase(
            title="Delay by Hour of Day", height=300,
            yaxis=dict(title="Avg Delay (min)", color=AMBER),
            yaxis2=dict(title="Flights", overlaying="y", side="right", color=TEAL),
            xaxis=dict(title="Hour", dtick=2),
        ))
        st.plotly_chart(fh, use_container_width=True)

    with col_r2:
        if "weather" in df.columns:
            wx = df.groupby("weather").size().reset_index(name="count").sort_values("count",ascending=False)
            fw = px.bar(wx, x="weather", y="count", color_discrete_sequence=[TEAL],
                        labels={"count":"Flights","weather":"Condition"},
                        title="Weather Conditions at LAX")
            fw.update_layout(**pbase(height=300, showlegend=False))
            st.plotly_chart(fw, use_container_width=True)

    dl = df[df["delay_mins"].between(-90,240)]
    fh2 = px.histogram(dl, x="delay_mins", nbins=40,
                       color="flight_type",
                       color_discrete_map={"departures":TEAL,"arrivals":AMBER},
                       barmode="overlay", opacity=0.75,
                       labels={"delay_mins":"Delay (min)","flight_type":"Type"},
                       title="Delay Distribution — Departures vs Arrivals")
    fh2.add_vline(x=0,  line_dash="dash", line_color="white", opacity=0.5,
                  annotation_text="On-time", annotation_font_color="white")
    fh2.add_vline(x=15, line_dash="dot",  line_color=AMBER,  opacity=0.7,
                  annotation_text="+15 min", annotation_font_color=AMBER)
    fh2.update_layout(**pbase(height=280))
    st.plotly_chart(fh2, use_container_width=True)


# ── TAB 2: AIRLINE ────────────────────────────────────────────────────────────
with tabs[2]:
    al = df.groupby(["airlineCode","airlineName"]).agg(
        flights=("flight","count"),
        on_time_rate=("on_time","mean"),
        delayed_n=("delayed_f","sum"),
        avg_delay=("delay_mins", lambda x: x[x>0].mean()),
    ).reset_index().sort_values("flights",ascending=False).fillna(0)
    al["avg_delay"] = al["avg_delay"].round(1)

    top_n  = st.slider("Top N airlines", 5, min(40,len(al)), min(20,len(al)))
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
        fig.update_xaxes(tickformat=".0%", range=[0,1.2])
        fig.update_layout(**pbase(height=max(320,top_n*24), coloraxis_showscale=False))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        fig2 = px.scatter(al_top, x="flights", y="on_time_rate",
                          size="delayed_n", color="airlineCode",
                          text="airlineCode", size_max=45,
                          labels={"flights":"Total Flights","on_time_rate":"On-Time Rate"},
                          title="Volume vs Performance (bubble = delays)")
        fig2.update_traces(textposition="top center")
        fig2.update_yaxes(tickformat=".0%")
        fig2.update_layout(**pbase(height=max(320,top_n*24), showlegend=False))
        st.plotly_chart(fig2, use_container_width=True)

    al_d = al_top.copy()
    al_d["on_time_rate"] = al_d["on_time_rate"].apply(lambda x: f"{x:.1%}")
    al_d["avg_delay"]    = al_d["avg_delay"].apply(lambda x: f"{x:.1f} min")
    st.dataframe(al_d.rename(columns={"airlineCode":"Code","airlineName":"Airline",
                                       "flights":"Flights","on_time_rate":"On-Time Rate",
                                       "delayed_n":"Delayed","avg_delay":"Avg Delay"}),
                 use_container_width=True, hide_index=True)


# ── TAB 3: TERMINAL ───────────────────────────────────────────────────────────
with tabs[3]:
    st.caption("Terminal assignments derived from LAX airline-to-terminal map (2025). "
               "TBIT = Tom Bradley International Terminal.")
    st.divider()

    term_order = ["T1","T2/T3","T4","T5/T6","T7/T8","TBIT","Other"]

    tm = df.groupby("terminal").agg(
        flights=("flight","count"),
        on_time_rate=("on_time","mean"),
        delayed_n=("delayed_f","sum"),
        avg_delay=("delay_mins", lambda x: x[x>0].mean()),
    ).reset_index().fillna(0)
    tm["avg_delay"] = tm["avg_delay"].round(1)
    tm["terminal"] = pd.Categorical(tm["terminal"], categories=term_order, ordered=True)
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
        fig_t.update_yaxes(tickformat=".0%", range=[0,1.25])
        fig_t.update_layout(**pbase(height=360, coloraxis_showscale=False))
        st.plotly_chart(fig_t, use_container_width=True)

    with col_r:
        fig_tv = px.bar(tm, x="terminal", y="flights",
                        color="avg_delay",
                        color_continuous_scale=[[0,TEAL],[0.5,AMBER],[1,RED]],
                        text="flights",
                        labels={"flights":"Flights","terminal":"Terminal","avg_delay":"Avg Delay (min)"},
                        title="Flight Volume by Terminal (colour = avg delay)")
        fig_tv.update_traces(textposition="outside")
        fig_tv.update_layout(**pbase(height=360))
        fig_tv.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig_tv, use_container_width=True)

    # Terminal × Hour heatmap
    th = df.groupby(["terminal","sched_hour"]).size().reset_index(name="flights")
    if not th.empty:
        pv_th = th.pivot(index="terminal", columns="sched_hour", values="flights").fillna(0)
        pv_th = pv_th.reindex([t for t in term_order if t in pv_th.index])
        fig_hm = px.imshow(pv_th,
                           color_continuous_scale=[[0,"#0a1628"],[1,TEAL]],
                           aspect="auto",
                           labels={"x":"Hour of Day","y":"Terminal","color":"Flights"},
                           title="Terminal × Hour — Flight Volume Heatmap")
        fig_hm.update_layout(**pbase(height=320))
        fig_hm.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig_hm, use_container_width=True)

    # Summary table
    tm_d = tm.copy()
    tm_d["on_time_rate"] = tm_d["on_time_rate"].apply(lambda x: f"{x:.1%}")
    tm_d["avg_delay"]    = tm_d["avg_delay"].apply(lambda x: f"{x:.1f} min")
    st.dataframe(tm_d.rename(columns={
        "terminal":"Terminal","flights":"Flights",
        "on_time_rate":"On-Time Rate","delayed_n":"Delayed","avg_delay":"Avg Delay"
    }), use_container_width=True, hide_index=True)


# ── TAB 4: ROUTES ─────────────────────────────────────────────────────────────
with tabs[4]:
    c_rt, _ = st.columns([1,3])
    route_type = c_rt.radio("View", ["Departures","Arrivals"], horizontal=True)

    if route_type == "Departures":
        rt = df[df["flight_type"]=="departures"].groupby(
            ["destinationAirportCode","destinationAirportName","destinationCountryCode"]
        ).agg(flights=("flight","count"), on_time=("on_time","mean")).reset_index()
        rt.columns = ["iata","name","country","flights","on_time"]
    else:
        rt = df[df["flight_type"]=="arrivals"].groupby(
            ["originAirportCode","originAirportName"]
        ).agg(flights=("flight","count"), on_time=("on_time","mean")).reset_index()
        rt.columns = ["iata","name","flights","on_time"]
        rt["country"] = ""

    rt = rt.sort_values("flights", ascending=False).head(30)

    col_l, col_r = st.columns(2)
    with col_l:
        fig_rt = px.bar(rt.head(20).sort_values("flights"),
                        x="flights", y="iata", orientation="h",
                        color="on_time",
                        color_continuous_scale=[[0,AMBER],[0.6,TEAL],[1,TEAL]],
                        text="flights",
                        labels={"flights":"Flights","iata":"Airport","on_time":"On-Time"},
                        title="Top 20 Routes by Volume")
        fig_rt.update_traces(textposition="outside")
        fig_rt.update_layout(**pbase(height=500, coloraxis_showscale=False))
        st.plotly_chart(fig_rt, use_container_width=True)

    with col_r:
        tree_path = ["country","iata"] if rt.get("country","").any() else ["iata"]
        fig_tree = px.treemap(rt, path=tree_path, values="flights",
                              color="on_time",
                              color_continuous_scale=[[0,AMBER],[0.6,TEAL],[1,TEAL]],
                              title="Treemap: size=volume  colour=on-time rate")
        fig_tree.update_layout(**pbase(height=500))
        fig_tree.update_coloraxes(colorbar=cbar(".0%"))
        st.plotly_chart(fig_tree, use_container_width=True)

    # Airline × destination heatmap
    pv_data = df[df["flight_type"]=="departures"].groupby(
        ["airlineCode","destinationAirportCode"]
    ).size().reset_index(name="flights")
    top_al  = pv_data.groupby("airlineCode")["flights"].sum().nlargest(12).index
    top_dst = pv_data.groupby("destinationAirportCode")["flights"].sum().nlargest(15).index
    pv_data = pv_data[pv_data["airlineCode"].isin(top_al) & pv_data["destinationAirportCode"].isin(top_dst)]
    if not pv_data.empty:
        pv = pv_data.pivot(index="airlineCode", columns="destinationAirportCode",
                           values="flights").fillna(0)
        fig_hm = px.imshow(pv, color_continuous_scale=[[0,"#0a1628"],[1,TEAL]],
                           aspect="auto",
                           labels={"x":"Destination","y":"Airline","color":"Flights"},
                           title="Airline × Destination Concentration")
        fig_hm.update_layout(**pbase(height=380))
        fig_hm.update_coloraxes(colorbar=cbar())
        st.plotly_chart(fig_hm, use_container_width=True)
