import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Carob Price Tracker",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. GLOBAL CSS STYLING ---
st.markdown("""
<style>
/* Prevent horizontal page scrolling and overflow */
html, body, [data-testid="stAppViewContainer"], .main {
    overflow-x: hidden !important;
    max-width: 100vw !important;
}

@media (max-width: 768px) {
    .block-container { padding: 1rem 0.5rem !important; }
    [data-testid="stTabs"] > div:first-child {
        overflow-x: auto !important;
        white-space: nowrap !important;
    }
    h1 { font-size: 1.3rem !important; }
    h3 { font-size: 1.05rem !important; }
}

/* Overview Summary Cards */
.price-card {
    background: #18181b;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 10px;
    border-left: 4px solid;
    border-top: 1px solid #27272a;
    border-right: 1px solid #27272a;
    border-bottom: 1px solid #27272a;
}
.price-card.inteira   { border-left-color: #D97706; }
.price-card.grainha   { border-left-color: #2563EB; }
.price-card.triturado { border-left-color: #059669; }
.card-title { font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; color: #fff; }
.card-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: #a1a1aa; padding: 2px 0; }
.card-val { font-weight: 600; color: #fff; }

/* Responsive 3-Column Comparison Grid (Strict Side-by-Side on PC & Mobile) */
.comp-container {
    display: flex !important;
    flex-direction: row !important;
    justify-content: space-between !important;
    gap: 6px !important;
    width: 100% !important;
    box-sizing: border-box !important;
    margin-top: 10px !important;
}
.comp-col {
    flex: 1 1 33.33% !important;
    min-width: 0 !important;
    background: #18181b !important;
    border-radius: 8px !important;
    padding: 8px 6px !important;
    border: 1px solid #27272a !important;
    box-sizing: border-box !important;
}
.comp-header {
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    margin-bottom: 8px !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    color: #f4f4f5 !important;
}
.comp-metric-item {
    margin-bottom: 6px !important;
    padding-bottom: 4px !important;
    border-bottom: 1px solid #27272a !important;
}
.comp-metric-item:last-child {
    border-bottom: none !important;
    margin-bottom: 0 !important;
}
.comp-label {
    font-size: 0.65rem !important;
    color: #a1a1aa !important;
    display: block !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
.comp-val {
    font-size: 0.80rem !important;
    font-weight: 600 !important;
    color: #ffffff !important;
    display: block !important;
    line-height: 1.2 !important;
}
.comp-delta {
    font-size: 0.65rem !important;
    font-weight: 600 !important;
    display: inline-block !important;
    padding: 1px 4px !important;
    border-radius: 4px !important;
    margin-top: 2px !important;
}
.comp-delta.pos { background: rgba(34, 197, 94, 0.15) !important; color: #4ade80 !important; }
.comp-delta.neg { background: rgba(239, 68, 68, 0.15) !important; color: #f87171 !important; }
.comp-delta.neutral { background: rgba(161, 161, 170, 0.15) !important; color: #a1a1aa !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING & CACHING ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("carob_prices.csv")
    except Exception:
        # Fallback generator if carob_prices.csv is not present locally
        dates = pd.date_range(start="2012-01-01", end="2026-07-20", freq="W")
        df = pd.DataFrame({"date": dates})
        df["inteira_freq"] = 0.30 + (df.index * 0.003)
        df["inteira_min"] = df["inteira_freq"] * 0.95
        df["inteira_max"] = df["inteira_freq"] * 1.05
        df["grainha_freq"] = df["inteira_freq"] * 5.0
        df["grainha_min"] = df["grainha_freq"] * 0.96
        df["grainha_max"] = df["grainha_freq"] * 1.04
        df["triturado_freq"] = df["inteira_freq"] * 1.2
        df["triturado_min"] = df["triturado_freq"] * 0.94
        df["triturado_max"] = df["triturado_freq"] * 1.06
    
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

df_all = load_data()
df = df_all.copy()

# --- 4. CONFIGURATION MAPPINGS ---
field_map = {
    ("Alfarroba Inteira", "Mais Frequente (Freq)"): "inteira_freq",
    ("Alfarroba Inteira", "Mínimo (Min)"): "inteira_min",
    ("Alfarroba Inteira", "Máximo (Max)"): "inteira_max",
    ("Alfarroba Graínha", "Mais Frequente (Freq)"): "grainha_freq",
    ("Alfarroba Graínha", "Mínimo (Min)"): "grainha_min",
    ("Alfarroba Graínha", "Máximo (Max)"): "grainha_max",
    ("Alfarroba Triturado Grosso", "Mais Frequente (Freq)"): "triturado_freq",
    ("Alfarroba Triturado Grosso", "Mínimo (Min)"): "triturado_min",
    ("Alfarroba Triturado Grosso", "Máximo (Max)"): "triturado_max",
}

cat_colors = {
    "Alfarroba Inteira": "#D97706",
    "Alfarroba Graínha": "#2563EB",
    "Alfarroba Triturado Grosso": "#059669",
}

line_styles = {
    "Mais Frequente (Freq)": "solid",
    "Mínimo (Min)": "dash",
    "Máximo (Max)": "dot",
}

# --- 5. SIDEBAR CONTROLS ---
st.sidebar.title("🌾 Carob Tracker")
st.sidebar.markdown("---")

unit_choice = st.sidebar.radio("Display Unit", ["€/kg", "€/arroba (15 kg)"], index=0)
multiplier = 15.0 if "arroba" in unit_choice else 1.0
unit_label = "€/arroba" if multiplier == 15.0 else "€/kg"

st.sidebar.markdown("---")
st.sidebar.subheader("Chart Filter Options")

categories_to_plot = st.sidebar.multiselect(
    "Products to Display:",
    ["Alfarroba Inteira", "Alfarroba Graínha", "Alfarroba Triturado Grosso"],
    default=["Alfarroba Inteira", "Alfarroba Graínha", "Alfarroba Triturado Grosso"]
)

selected_price_types = st.sidebar.multiselect(
    "Price Metrics:",
    ["Mais Frequente (Freq)", "Mínimo (Min)", "Máximo (Max)"],
    default=["Mais Frequente (Freq)", "Mínimo (Min)", "Máximo (Max)"]
)

min_date = df_all["date"].min()
max_date = df_all["date"].max()

# --- 6. HEADER & LATEST PRICE OVERVIEW CARDS ---
st.title("🌾 Carob Price Tracker")
st.caption(f"Historical trends & market analysis ({min_date.strftime('%Y')} - {max_date.strftime('%Y')})")

latest_row = df_all.iloc[-1]
card_cols = st.columns(3)

card_data = [
    ("Alfarroba Inteira", "inteira", "inteira"),
    ("Alfarroba Graínha", "grainha", "grainha"),
    ("Alfarroba Triturado Grosso", "triturado", "triturado"),
]

for col, (title, key, css_class) in zip(card_cols, card_data):
    with col:
        freq_v = latest_row.get(f"{key}_freq") * multiplier if pd.notna(latest_row.get(f"{key}_freq")) else None
        min_v = latest_row.get(f"{key}_min") * multiplier if pd.notna(latest_row.get(f"{key}_min")) else None
        max_v = latest_row.get(f"{key}_max") * multiplier if pd.notna(latest_row.get(f"{key}_max")) else None
        
        freq_str = f"{freq_v:.2f} {unit_label}" if freq_v else "N/A"
        min_str = f"{min_v:.2f} {unit_label}" if min_v else "N/A"
        max_str = f"{max_v:.2f} {unit_label}" if max_v else "N/A"

        st.markdown(
            f'<div class="price-card {css_class}">'
            f'<div class="card-title">{title}</div>'
            f'<div class="card-row"><span>Freq:</span><span class="card-val">{freq_str}</span></div>'
            f'<div class="card-row"><span>Min:</span><span class="card-val">{min_str}</span></div>'
            f'<div class="card-row"><span>Max:</span><span class="card-val">{max_str}</span></div>'
            f'</div>',
            unsafe_allow_html=True
        )

# --- 7. PRICE CHANGE COMPARISON SECTION ---
st.markdown("### 📊 Price Change Comparison")

comp_col_select, comp_col_toggle = st.columns([3, 2])

with comp_col_select:
    comp_period = st.selectbox(
        "Compare price changes across period:",
        [
            "None (Off)",
            "1 Week", 
            "1 Month", 
            "3 Months", 
            "6 Months", 
            "Year-to-Date (YTD)", 
            "1 Year", 
            "5 Years", 
            "Max (All Time)",
            "📅 Custom Date Range"
        ],
        index=0
    )

with comp_col_toggle:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    show_highlight = st.checkbox(
        "Highlight period on chart", 
        value=False, 
        disabled=(comp_period == "None (Off)")
    )

latest_date = df_all["date"].max()
min_available_date = df_all["date"].min()

if comp_period == "None (Off)":
    start_date = None
    end_date = None
    crop_start = None
    crop_end = None
    chart_h_start = None
    chart_h_end = None
    st.info("💡 Select a time period or custom range above to compare price changes.")

else:
    if comp_period == "📅 Custom Date Range":
        col_start, col_end = st.columns(2)
        with col_start:
            picked_start = st.date_input(
                "Start Date:",
                value=(latest_date - pd.DateOffset(months=1)).date(),
                min_value=min_available_date.date(),
                max_value=latest_date.date(),
                key="comp_start_date"
            )
        with col_end:
            picked_end = st.date_input(
                "End Date:",
                value=latest_date.date(),
                min_value=min_available_date.date(),
                max_value=latest_date.date(),
                key="comp_end_date"
            )
        
        if picked_start > picked_end:
            st.error("⚠️ Start date cannot be later than End date.")
            start_date = pd.Timestamp(picked_start)
            end_date = pd.Timestamp(picked_start)
        else:
            start_date = pd.Timestamp(picked_start)
            end_date = pd.Timestamp(picked_end)
    else:
        end_date = latest_date
        if comp_period == "1 Week":
            start_date = latest_date - pd.DateOffset(weeks=1)
        elif comp_period == "1 Month":
            start_date = latest_date - pd.DateOffset(months=1)
        elif comp_period == "3 Months":
            start_date = latest_date - pd.DateOffset(months=3)
        elif comp_period == "6 Months":
            start_date = latest_date - pd.DateOffset(months=6)
        elif comp_period == "Year-to-Date (YTD)":
            start_date = pd.Timestamp(year=latest_date.year, month=1, day=1)
        elif comp_period == "1 Year":
            start_date = latest_date - pd.DateOffset(years=1)
        elif comp_period == "5 Years":
            start_date = latest_date - pd.DateOffset(years=5)
        else:
            start_date = min_available_date

    crop_start = start_date
    crop_end = end_date
    chart_h_start = start_date if show_highlight else None
    chart_h_end = end_date if show_highlight else None

    start_df = df_all[df_all["date"] <= start_date]
    start_row = start_df.iloc[-1] if not start_df.empty else df_all.iloc[0]
    actual_start_date_str = start_row["date"].strftime("%d/%m/%Y")

    end_df = df_all[df_all["date"] <= end_date]
    end_row = end_df.iloc[-1] if not end_df.empty else df_all.iloc[-1]
    actual_end_date_str = end_row["date"].strftime("%d/%m/%Y")

    st.caption(f"Comparing baseline prices from **{actual_start_date_str}** to **{actual_end_date_str}**")

    categories_info = [
        ("🟠 Inteira",   "inteira"),
        ("🔵 Graínha",   "grainha"),
        ("🟢 Triturado", "triturado"),
    ]

    grid_parts = ['<div class="comp-container">']
    for title, key in categories_info:
        grid_parts.append(f'<div class="comp-col"><div class="comp-header">{title}</div>')
        for ptype, pkey in [("Freq", f"{key}_freq"), ("Min", f"{key}_min"), ("Max", f"{key}_max")]:
            end_v = end_row.get(pkey)
            start_v = start_row.get(pkey)
            
            if pd.notna(end_v) and pd.notna(start_v) and start_v > 0:
                end_val = end_v * multiplier
                start_val = start_v * multiplier
                diff = end_val - start_val
                pct = (diff / start_val) * 100
                
                val_str = f"{end_val:.2f} {unit_label}"
                cls = "pos" if diff > 0 else ("neg" if diff < 0 else "neutral")
                delta_str = f"{diff:+.2f} ({pct:+.1f}%)"
                
                grid_parts.append(
                    f'<div class="comp-metric-item">'
                    f'<span class="comp-label">{ptype}</span>'
                    f'<span class="comp-val">{val_str}</span>'
                    f'<span class="comp-delta {cls}">{delta_str}</span>'
                    f'</div>'
                )
            else:
                grid_parts.append(
                    f'<div class="comp-metric-item">'
                    f'<span class="comp-label">{ptype}</span>'
                    f'<span class="comp-val">N/A</span>'
                    f'</div>'
                )
        grid_parts.append('</div>')
    grid_parts.append('</div>')

    st.markdown("".join(grid_parts), unsafe_allow_html=True)

# --- 8. PLOTLY CHART BUILDER FUNCTION ---
def build_chart(categories_to_plot, crop_start=None, crop_end=None, highlight_start=None, highlight_end=None):
    fig = go.Figure()

    clean_cat_names = {
        "Alfarroba Inteira": "Inteira",
        "Alfarroba Graínha": "Graínha",
        "Alfarroba Triturado Grosso": "Triturado"
    }

    clean_ptypes = {
        "Mais Frequente (Freq)": "Freq",
        "Mínimo (Min)": "Min",
        "Máximo (Max)": "Max"
    }

    all_visible_y_values = []

    # Slice dataset for calculating vertical Y-axis dynamic zoom bounds
    if crop_start and crop_end:
        mask = (df["date"] >= pd.Timestamp(crop_start)) & (df["date"] <= pd.Timestamp(crop_end))
        df_slice = df[mask]
    else:
        df_slice = df

    # Order loop: ptype first, then cat -> 3 horizontal columns in plot legend
    for ptype in selected_price_types:
        for cat in categories_to_plot:
            col_name = field_map.get((cat, ptype))
            if col_name and col_name in df.columns:
                y_data = pd.to_numeric(df[col_name], errors="coerce") * multiplier
                
                # Visible subset for Y-range dynamic bounds
                y_slice = pd.to_numeric(df_slice[col_name], errors="coerce").dropna() * multiplier
                if not y_slice.empty:
                    all_visible_y_values.extend(y_slice.tolist())

                short_cat = clean_cat_names.get(cat, cat)
                short_ptype = clean_ptypes.get(ptype, ptype)
                trace_label = f"{short_cat} ({short_ptype})"

                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=y_data,
                        name=trace_label,
                        line=dict(color=cat_colors[cat], dash=line_styles[ptype], width=2),
                        connectgaps=True,
                    )
                )

    xaxis_config = dict(
        type="date",
        gridcolor="rgba(255, 255, 255, 0.08)",
        zerolinecolor="rgba(255, 255, 255, 0.15)",
    )
    
    yaxis_config = dict(
        type="linear",
        tickformat=".2f" if multiplier == 1.0 else ".1f",
        gridcolor="rgba(255, 255, 255, 0.08)",
        zerolinecolor="rgba(255, 255, 255, 0.15)",
    )

    if crop_start and crop_end:
        xaxis_config["range"] = [crop_start, crop_end]

    # Calculate dynamic Y-axis scale based strictly on visible window data
    if all_visible_y_values:
        y_min = min(all_visible_y_values)
        y_max = max(all_visible_y_values)
        y_span = y_max - y_min
        
        # 8% top and bottom padding
        padding = y_span * 0.08 if y_span > 0 else (y_max * 0.05 if y_max > 0 else 0.5)
        
        calculated_min = max(0, y_min - padding)
        calculated_max = y_max + padding
        
        yaxis_config["range"] = [calculated_min, calculated_max]
        yaxis_config["autorange"] = False
    else:
        yaxis_config["autorange"] = True

    if highlight_start and highlight_end:
        fig.add_vrect(
            x0=highlight_start,
            x1=highlight_end,
            fillcolor="rgba(37, 99, 235, 0.12)",
            layer="below",
            line_width=1.5,
            line_dash="dash",
            line_color="rgba(37, 99, 235, 0.4)",
            annotation_text="Comparison Period",
            annotation_position="top left",
            annotation_font=dict(size=10, color="#888")
        )

    fig.update_layout(
        title=dict(
            text=f"Price History ({min_date.strftime('%Y')} - {max_date.strftime('%Y')})",
            x=0.01,
            y=0.98,
            xanchor="left",
            yanchor="top",
            font=dict(size=16)
        ),
        xaxis_title="Date",
        yaxis_title=f"Price ({unit_label})",
        xaxis=xaxis_config,
        yaxis=yaxis_config,
        
        # 3-COLUMN FRACTION LEGEND GRID
        legend=dict(
            orientation="h",
            entrywidthmode="fraction",
            entrywidth=0.33,
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            font=dict(size=9.5),
        ),
        
        margin=dict(t=50, b=130, l=45, r=20), 
        hovermode="x unified",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=580,
    )
    return fig

# --- 9. RENDER CHART ---
st.markdown("### 📈 Interactive Price History")
fig = build_chart(categories_to_plot, crop_start, crop_end, chart_h_start, chart_h_end)
st.plotly_chart(fig, use_container_width=True)

# --- 10. RAW DATA & DISCLAIMER ---
with st.expander("📋 View Raw Dataset"):
    st.dataframe(df_all, use_container_width=True)

st.markdown("---")
st.caption("⚠️ **Disclaimer:** For informational purposes only. Data provided as-is without guarantee of real-time accuracy.")
