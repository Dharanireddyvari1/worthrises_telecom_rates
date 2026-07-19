"""Interactive Streamlit dashboard for exploring matched telecom rate data.

Run:
    cd src && streamlit run dashboard.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


DATA_PATH = Path(__file__).resolve().parent.parent / "outputs" / "matched_telecom_rates.csv"


st.set_page_config(page_title="Telecom Rate Explorer", page_icon="📞", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_PATH)
    df["in_state_rate"] = pd.to_numeric(df["in_state_rate"], errors="coerce")
    df["out_of_state_rate"] = pd.to_numeric(df["out_of_state_rate"], errors="coerce")
    df["county"] = df["county"].fillna("")
    df["matched_facilities"] = df["matched_facilities"].fillna("")
    df["match_reason"] = df["match_reason"].fillna("")
    return df


data = load_data()

# ── Sidebar filters ──────────────────────────────────────────────────────────

st.sidebar.header("Filters")

states = ["All"] + sorted(data["state"].unique())
selected_state = st.sidebar.selectbox("State", states)

types = ["All"] + sorted(data["type"].unique())
selected_type = st.sidebar.selectbox("Jurisdiction type", types)

statuses = ["All"] + sorted(data["match_status"].unique())
selected_status = st.sidebar.selectbox("Match status", statuses)

filtered = data.copy()
if selected_state != "All":
    filtered = filtered[filtered["state"] == selected_state]
if selected_type != "All":
    filtered = filtered[filtered["type"] == selected_type]
if selected_status != "All":
    filtered = filtered[filtered["match_status"] == selected_status]

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Telecom Rate Explorer")
st.markdown("Jurisdiction-level phone rates matched from provider facility data.")

# ── KPI metrics ───────────────────────────────────────────────────────────────

col1, col2, col3, col4, col5, col6 = st.columns(6)
matched_df = filtered[filtered["match_status"] == "matched"]
avg_in = matched_df["in_state_rate"].mean()
avg_out = matched_df["out_of_state_rate"].mean()

col1.metric("Total jurisdictions", len(filtered))
col2.metric("Matched", len(matched_df))
col3.metric("Review", len(filtered[filtered["match_status"] == "review"]))
col4.metric("No match", len(filtered[filtered["match_status"] == "no_match"]))
col5.metric("Avg in-state rate", f"${avg_in:.3f}" if pd.notna(avg_in) else "—")
col6.metric("Avg out-of-state rate", f"${avg_out:.3f}" if pd.notna(avg_out) else "—")

st.divider()

# ── Tab layout ────────────────────────────────────────────────────────────────

tab_overview, tab_rates, tab_compare, tab_lookup, tab_data = st.tabs(
    ["Overview", "Rate Analysis", "State Comparison", "Facility Lookup", "Full Dataset"]
)

# ── Tab 1: Overview ───────────────────────────────────────────────────────────

with tab_overview:
    left, right = st.columns(2)

    with left:
        st.subheader("Match quality")
        status_counts = filtered["match_status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        colors = {"matched": "#2f6f73", "review": "#e6a817", "no_match": "#c0392b"}
        fig_pie = px.pie(
            status_counts,
            values="count",
            names="status",
            color="status",
            color_discrete_map=colors,
            hole=0.45,
        )
        fig_pie.update_traces(textinfo="value+percent")
        fig_pie.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

    with right:
        st.subheader("County vs state: median rate")
        type_rates = (
            matched_df.groupby("type")["in_state_rate"]
            .median()
            .reset_index()
        )
        type_rates.columns = ["Jurisdiction type", "Median rate ($/min)"]
        fig_type = px.bar(
            type_rates,
            x="Jurisdiction type",
            y="Median rate ($/min)",
            color="Jurisdiction type",
            color_discrete_map={"state": "#2f6f73", "county": "#e6a817"},
            text_auto=".3f",
        )
        fig_type.update_layout(
            margin=dict(t=20, b=20),
            height=350,
            showlegend=False,
        )
        st.plotly_chart(fig_type, use_container_width=True)

    # Jurisdictions needing review
    needs_attention = filtered[filtered["match_status"] != "matched"]
    if not needs_attention.empty:
        st.subheader("Jurisdictions needing review")
        st.dataframe(
            needs_attention[["type", "state", "county", "match_status", "match_reason"]],
            use_container_width=True,
            hide_index=True,
        )

# ── Tab 2: Rate Analysis ─────────────────────────────────────────────────────

with tab_rates:

    # Top 15 most expensive
    left, right = st.columns(2)
    with left:
        st.subheader("15 most expensive jurisdictions")
        top15 = matched_df.nlargest(15, "in_state_rate").copy()
        top15["label"] = top15.apply(
            lambda r: f"{r['state']} – {r['county']}" if r["county"] else f"{r['state']} (state)",
            axis=1,
        )
        fig_top = px.bar(
            top15.sort_values("in_state_rate"),
            x="in_state_rate",
            y="label",
            orientation="h",
            color_discrete_sequence=["#c0392b"],
            labels={"in_state_rate": "Rate ($/min)", "label": ""},
            text_auto=".3f",
        )
        fig_top.update_layout(margin=dict(t=20, b=20, l=10), height=450)
        st.plotly_chart(fig_top, use_container_width=True)

    with right:
        st.subheader("15 least expensive jurisdictions")
        bottom15 = matched_df.nsmallest(15, "in_state_rate").copy()
        bottom15["label"] = bottom15.apply(
            lambda r: f"{r['state']} – {r['county']}" if r["county"] else f"{r['state']} (state)",
            axis=1,
        )
        fig_bot = px.bar(
            bottom15.sort_values("in_state_rate", ascending=False),
            x="in_state_rate",
            y="label",
            orientation="h",
            color_discrete_sequence=["#2f6f73"],
            labels={"in_state_rate": "Rate ($/min)", "label": ""},
            text_auto=".3f",
        )
        fig_bot.update_layout(margin=dict(t=20, b=20, l=10), height=450)
        st.plotly_chart(fig_bot, use_container_width=True)

    # In-state vs out-of-state differences
    diff_df = matched_df[
        (matched_df["in_state_rate"].notna())
        & (matched_df["out_of_state_rate"].notna())
    ].copy()
    diff_df["rate_difference"] = diff_df["out_of_state_rate"] - diff_df["in_state_rate"]
    has_diff = diff_df[diff_df["rate_difference"].abs() > 0.001]

    st.subheader("In-state vs out-of-state rate gap")
    if has_diff.empty:
        st.info("All matched jurisdictions have identical in-state and out-of-state rates.")
    else:
        has_diff = has_diff.copy()
        has_diff["label"] = has_diff.apply(
            lambda r: f"{r['state']} – {r['county']}" if r["county"] else f"{r['state']} (state)",
            axis=1,
        )
        fig_diff = px.bar(
            has_diff.sort_values("rate_difference"),
            x="rate_difference",
            y="label",
            orientation="h",
            color="rate_difference",
            color_continuous_scale=["#2f6f73", "#e6a817", "#c0392b"],
            labels={"rate_difference": "Out-of-state minus in-state ($/min)", "label": ""},
        )
        fig_diff.update_layout(
            margin=dict(t=20, b=20, l=10),
            height=max(250, len(has_diff) * 30),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_diff, use_container_width=True)
        st.caption(
            f"**{len(has_diff)}** of {len(diff_df)} jurisdictions have different "
            f"in-state and out-of-state rates. The rest charge the same for both."
        )

# ── Tab 3: State Comparison ──────────────────────────────────────────────────

with tab_compare:

    # Median in-state rate by state
    st.subheader("Median in-state rate by state")
    state_data = matched_df[matched_df["in_state_rate"].notna()].copy()
    state_medians_in = (
        state_data.groupby("state")["in_state_rate"]
        .median()
        .sort_values(ascending=False)
        .reset_index()
    )
    state_medians_in.columns = ["State", "Median rate ($/min)"]
    fig_in = px.bar(
        state_medians_in,
        x="State",
        y="Median rate ($/min)",
        color="Median rate ($/min)",
        color_continuous_scale=["#2f6f73", "#e6a817", "#c0392b"],
        text_auto=".3f",
    )
    fig_in.update_layout(
        margin=dict(t=20, b=20),
        height=420,
        xaxis_tickangle=-45,
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_in, use_container_width=True)

    # Rate spread per state — box plot
    st.subheader("Rate spread by state")
    state_order = (
        state_data.groupby("state")["in_state_rate"]
        .median()
        .sort_values(ascending=False)
        .index.tolist()
    )
    fig_box = px.box(
        state_data,
        x="state",
        y="in_state_rate",
        color_discrete_sequence=["#2f6f73"],
        category_orders={"state": state_order},
        labels={"state": "State", "in_state_rate": "In-state rate ($/min)"},
        hover_data=["type", "county"],
    )
    fig_box.update_traces(line=dict(color="#2f6f73"), marker=dict(color="#2f6f73", outliercolor="#2f6f73"))
    for trace in fig_box.data:
        trace.update(line_color="#2f6f73", fillcolor="rgba(47,111,115,0.3)")
    # Add median markers as a separate scatter trace
    median_vals = state_data.groupby("state")["in_state_rate"].median().reset_index()
    median_vals.columns = ["state", "median"]
    fig_box.add_trace(go.Scatter(
        x=median_vals["state"],
        y=median_vals["median"],
        mode="markers",
        marker=dict(color="#c0392b", size=10, symbol="diamond"),
        name="Median",
        hovertemplate="State: %{x}<br>Median: $%{y:.3f}<extra></extra>",
    ))
    fig_box.update_layout(
        margin=dict(t=20, b=20),
        height=420,
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig_box, use_container_width=True)
    st.caption(
        "Each box shows the rate spread across jurisdictions in that state. "
        "The line inside marks the median. States with one jurisdiction show as a single point."
    )

# ── Tab 4: Facility Lookup ────────────────────────────────────────────────────

with tab_lookup:
    st.subheader("Facility lookup")
    st.markdown("Select a jurisdiction to see all matched facilities and their rates.")

    lookup_col1, lookup_col2, lookup_col3 = st.columns(3)
    with lookup_col1:
        lookup_type = st.selectbox("Type", ["county", "state"], key="lookup_type")
    with lookup_col2:
        lookup_states = sorted(data[data["type"] == lookup_type]["state"].unique())
        lookup_state = st.selectbox("State", lookup_states, key="lookup_state")
    with lookup_col3:
        if lookup_type == "county":
            lookup_counties = sorted(
                data[(data["type"] == "county") & (data["state"] == lookup_state)]["county"].unique()
            )
            lookup_county = st.selectbox("County", lookup_counties, key="lookup_county")
        else:
            lookup_county = ""
            st.selectbox("County", ["(all state facilities)"], disabled=True, key="lookup_county_disabled")

    # Find the jurisdiction row
    if lookup_type == "county":
        jurisdiction = data[
            (data["type"] == "county")
            & (data["state"] == lookup_state)
            & (data["county"] == lookup_county)
        ]
    else:
        jurisdiction = data[
            (data["type"] == "state") & (data["state"] == lookup_state)
        ]

    if not jurisdiction.empty:
        row = jurisdiction.iloc[0]
        st.divider()

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Match status", row["match_status"])
        m2.metric("In-state rate", f"${row['in_state_rate']:.3f}" if pd.notna(row["in_state_rate"]) else "—")
        m3.metric("Out-of-state rate", f"${row['out_of_state_rate']:.3f}" if pd.notna(row["out_of_state_rate"]) else "—")
        m4.metric("Facilities matched", int(row["matched_facility_count"]))

        st.markdown(f"**Match reason:** {row['match_reason']}")

        # Facility list
        facilities = str(row["matched_facilities"])
        if facilities:
            st.subheader("Matched facilities")
            facility_list = [f.strip() for f in facilities.split(";") if f.strip()]
            for i, name in enumerate(facility_list, 1):
                st.markdown(f"{i}. {name}")
        else:
            st.info("No facilities matched for this jurisdiction.")

# ── Tab 5: Full Dataset ──────────────────────────────────────────────────────

with tab_data:
    st.subheader("Matched telecom rates")
    st.markdown(f"Showing **{len(filtered)}** of {len(data)} jurisdictions.")

    display_cols = [
        "type", "state", "county", "match_status",
        "in_state_rate", "out_of_state_rate",
        "matched_facility_count", "matched_facilities", "match_reason",
    ]
    st.dataframe(
        filtered[display_cols],
        use_container_width=True,
        hide_index=True,
        height=600,
    )

    csv = filtered[display_cols].to_csv(index=False)
    st.download_button(
        label="Download filtered data as CSV",
        data=csv,
        file_name="filtered_telecom_rates.csv",
        mime="text/csv",
    )
