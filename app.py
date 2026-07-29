# app.py
import os
import io
from datetime import datetime, timedelta
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --- 1. STREAMLIT CONFIG ---
st.set_page_config(
    page_title="Algarve Carob Market Tracker",
    layout="wide",
    page_icon="🌿",
)

# --- 2. MOBILE CSS ---
st.markdown("""
<style>
/* Prevent page horizontal scrolling/overflow */
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

/* Top Price Cards */
.price-card {
    background: #1e1e1e;
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 10px;
    border-left: 4px solid;
}
.price-card.inteira   { border-color: #D97706; }
.price-card.grainha   { border-color: #2563EB; }
.price-card.triturado { border-color: #059669; }
.card-title { font-size: 0.95rem; font-weight: 700; margin-bottom: 6px; color: #fff; }
.card-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: #ccc; padding: 2px 0; }
.card-val { font-weight: 600; color: #fff; }

/* Strict 3-Column Comparison Grid for PC & Mobile */
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

# --- 3. CONSTANTS ---
MASTER_FILE = "sima_master.csv"
GET_COTACOES_URL = "https://regsima.gpp.pt/regsima/consulta/get_cotacoes"

# --- 4. DATA FETCHING ---
def fetch_latest_sima_data(weeks_back=8):
    end = datetime.now()
    start = end - timedelta(weeks=weeks_back)
    params = {
        "setor": 23, "especie": 70, "regiao": 7, "mercado": 69,
        "tipo": 8, "export": 1,
        "ini": start.strftime("%Y-%m-%d"),
        "fim": end.strftime("%Y-%m-%d"),
    }
    try:
        res = requests.get(GET_COTACOES_URL, params=params,
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        res.raise_for_status()
        res.encoding = "windows-1252"
        return pd.read_csv(io.StringIO(res.text), sep=";")
    except Exception as e:
        st.warning(f"Could not auto-fetch SIMA data: {e}")
        return pd.DataFrame()


def sync_and_get_master_data():
    local_df = pd.DataFrame()
    if os.path.exists(MASTER_FILE):
        try:
            local_df = pd.read_csv(MASTER_FILE, sep=";", encoding="utf-8-sig")
        except Exception:
            pass

    if local_df.empty:
        for f in os.listdir("."):
            if f.endswith((".csv", ".xlsx", ".xls")) and "sima" in f.lower() and f != MASTER_FILE:
                try:
                    local_df = pd.read_csv(f, sep=";", encoding="latin1") if f.endswith(".csv") else pd.read_excel(f)
                    break
                except Exception:
                    continue

    online_df = fetch_latest_sima_data()
    if not online_df.empty:
        if not local_df.empty:
            combined = pd.concat([local_df, online_df], ignore_index=True)
            dedup_cols = [c for c in ["Produto", "Data", "Mercado"] if c in combined.columns]
            if dedup_cols:
                combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
            local_df = combined
        else:
            local_df = online_df

    if not local_df.empty:
        local_df.to_csv(MASTER_FILE, sep=";", index=False, encoding="utf-8-sig")

    return local_df


# --- 5. DATA PROCESSING ---
@st.cache_data(ttl=300)
def process_data(df_raw):
    if df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = next((c for c in df.columns if "data" in c.lower()), None)
    prod_col = next((c for c in df.columns if "prod" in c.lower()), None)
    min_col  = next((c for c in df.columns if "mín" in c.lower() or "min" in c.lower()), None)
    max_col  = next((c for c in df.columns if "máx" in c.lower() or "max" in c.lower()), None)
    freq_col = next((c for c in df.columns if "freq" in c.lower() or "mais" in c.lower()), None)

    if not all([date_col, prod_col, min_col, max_col, freq_col]):
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df[date_col], dayfirst=True, format="mixed", errors="coerce")
    df = df.dropna(subset=["date"])

    for col in [min_col, max_col, freq_col]:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace(",", ".").str.strip()
        df[col] = pd.to_numeric(df[col], errors="coerce").replace(0, pd.NA)

    def categorize(val):
        v = str(val).lower()
        if "grainha" in v or "graínha" in v or "semente" in v:
            return "grainha"
        elif "triturado" in v or "bagaço" in v:
            return "triturado"
        return "inteira"

    df["specie_key"] = df[prod_col].apply(categorize)

    grouped = df.groupby(["date", "specie_key"])[[min_col, max_col, freq_col]].mean().reset_index()
    grouped = grouped.rename(columns={min_col: "min_v", max_col: "max_v", freq_col: "freq_v"})

    pivoted = grouped.pivot(index="date", columns="specie_key", values=["min_v", "max_v", "freq_v"])
    pivoted.columns = [f"{col[1]}_{col[0].replace('_v', '')}" for col in pivoted.columns]

    for c in ["inteira_freq", "inteira_min", "inteira_max",
              "grainha_freq", "grainha_min", "grainha_max",
              "triturado_freq", "triturado_min", "triturado_max"]:
        if c not in pivoted.columns:
            pivoted[c] = pd.NA

    final = pivoted.reset_index().sort_values("date").reset_index(drop=True)
    val_cols = [c for c in final.columns if c != "date"]
    final[val_cols] = final[val_cols].ffill()
    return final


# --- 6. LOAD DATA ---
raw_sima_data = sync_and_get_master_data()
df_all = process_data(raw_sima_data)

if df_all.empty:
    st.warning("No SIMA data found. Place your SIMA export CSV in this folder and restart.")
    st.stop()

last_date = df_all["date"].max().strftime("%Y-%m-%d")

# --- 7. SIDEBAR ---
st.sidebar.header("⚙️ Filters")

if st.sidebar.button("🔄 Sync Latest SIMA Quotes"):
    st.cache_data.clear()
    raw_sima_data = sync_and_get_master_data()
    df_all = process_data(raw_sima_data)
    st.sidebar.success("Synced!")

time_range = st.sidebar.radio("Range:", ["All Time", "5 Years", "1 Year", "6 Months"], index=0)
max_date = df_all["date"].max()
if time_range == "6 Months":
    min_date = max_date - pd.DateOffset(months=6)
elif time_range == "1 Year":
    min_date = max_date - pd.DateOffset(years=1)
elif time_range == "5 Years":
    min_date = max_date - pd.DateOffset(years=5)
else:
    min_date = df_all["date"].min()

df = df_all[(df_all["date"] >= min_date) & (df_all["date"] <= max_date)].copy()

unit_mode = st.sidebar.selectbox("Unit:", ["EUR / kg", "EUR / arroba (15 kg)"])
multiplier = 15.0 if "arroba" in unit_mode else 1.0
unit_label = "€/@" if "arroba" in unit_mode else "€/kg"

selected_cats = st.sidebar.multiselect(
    "Categories:",
    ["Alfarroba Inteira", "Alfarroba Graínha", "Alfarroba Triturado Grosso"],
    default=["Alfarroba Inteira", "Alfarroba Graínha", "Alfarroba Triturado Grosso"],
)
selected_price_types = st.sidebar.multiselect(
    "Price Types:",
    ["Mais Frequente (Freq)", "Mínimo (Min)", "Máximo (Max)"],
    default=["Mais Frequente (Freq)"],
)

# --- 8. HEADER ---
st.title("🌿 Algarve Carob Market Prices")
st.caption(f"🟢 Live SIMA data | Latest entry: {last_date}")

# --- 9. METRIC CARDS ---
st.markdown("### 📍 Current Quotes")
latest = df_all.iloc[-1]

def fmt(val):
    return f"{val * multiplier:.2f} {unit_label}" if pd.notna(val) else "N/A"

def price_card(title, css_class, freq_key, min_key, max_key):
    st.markdown(f"""
    <div class="price-card {css_class}">
        <div class="card-title">{title}</div>
        <div class="card-row"><span>Freq</span><span class="card-val">{fmt(latest.get(freq_key))}</span></div>
        <div class="card-row"><span>Min</span><span class="card-val">{fmt(latest.get(min_key))}</span></div>
        <div class="card-row"><span>Max</span><span class="card-val">{fmt(latest.get(max_key))}</span></div>
    </div>
    """, unsafe_allow_html=True)

price_card("🟠 Alfarroba Inteira",          "inteira",   "inteira_freq",   "inteira_min",   "inteira_max")
price_card("🔵 Alfarroba Graínha",           "grainha",   "grainha_freq",   "grainha_min",   "grainha_max")
price_card("🟢 Alfarroba Triturado Grosso",  "triturado", "triturado_freq", "triturado_min", "triturado_max")

# --- 9.5. PRICE COMPARISON ---
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

    # Build clean HTML without line indentation (prevents Markdown code-block parsing)
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

st.divider()

# --- 10. CHART ---
line_styles = {"Mais Frequente (Freq)": "solid", "Mínimo (Min)": "dash", "Máximo (Max)": "dot"}
cat_colors  = {
    "Alfarroba Inteira": "#D97706",
    "Alfarroba Graínha": "#2563EB",
    "Alfarroba Triturado Grosso": "#059669",
}
field_map = {
    ("Alfarroba Inteira",          "Mais Frequente (Freq)"): "inteira_freq",
    ("Alfarroba Inteira",          "Mínimo (Min)"):          "inteira_min",
    ("Alfarroba Inteira",          "Máximo (Max)"):          "inteira_max",
    ("Alfarroba Graínha",          "Mais Frequente (Freq)"): "grainha_freq",
    ("Alfarroba Graínha",          "Mínimo (Min)"):          "grainha_min",
    ("Alfarroba Graínha",          "Máximo (Max)"):          "grainha_max",
    ("Alfarroba Triturado Grosso", "Mais Frequente (Freq)"): "triturado_freq",
    ("Alfarroba Triturado Grosso", "Mínimo (Min)"):          "triturado_min",
    ("Alfarroba Triturado Grosso", "Máximo (Max)"):          "triturado_max",
}

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

    # Ordering: ptype first, then cat creates 3 columns across:
    # Row 1: Inteira (Freq) | Graínha (Freq) | Triturado (Freq)
    # Row 2: Inteira (Min)  | Graínha (Min)  | Triturado (Min)
    # Row 3: Inteira (Max)  | Graínha (Max)  | Triturado Max
    for ptype in selected_price_types:
        for cat in categories_to_plot:
            col_name = field_map.get((cat, ptype))
            if col_name and col_name in df.columns:
                y_data = pd.to_numeric(df[col_name], errors="coerce") * multiplier
                
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

    xaxis_config = dict(type="date")
    
    if crop_start and crop_end:
        xaxis_config["range"] = [crop_start, crop_end]

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
        
        # STRICT 3-COLUMN LEGEND GRID (33% WIDTH PER COLUMN)
        legend=dict(
            orientation="h",
            entrywidthmode="fraction",
            entrywidth=0.33,       # Forces exactly 3 equal columns across screen
            yanchor="top",
            y=-0.22,
            xanchor="center",
            x=0.5,
            font=dict(size=9.5),   # Scaled font size so 3 items fit on mobile
        ),
        
        margin=dict(t=50, b=130, l=45, r=20), 
        
        yaxis=dict(
            type="linear",
            rangemode="tozero",
            autorange=True,
            tickformat=".2f" if multiplier == 1.0 else ".1f",
        ),
        hovermode="x unified",
        template="plotly_white",
        height=580,
    )
    return fig
    
# --- NEW UPDATED CODE ---
st.markdown("### 📈 Interactive Price Chart")

# Dedicated Chart Zoom Control Bar
chart_ctrl_1, chart_ctrl_2 = st.columns([3, 1])

with chart_ctrl_1:
    enable_custom_chart_zoom = st.checkbox("🔍 Apply custom date window to graph view only", value=False)

with chart_ctrl_2:
    reset_chart_view = st.button("🔄 Reset Zoom", use_container_width=True, help="Reset graph to default view")

# Handle Custom Chart Window vs Default Crop
if enable_custom_chart_zoom:
    cz_col1, cz_col2 = st.columns(2)
    with cz_col1:
        cz_start = st.date_input(
            "Graph Zoom Start:",
            value=(latest_date - pd.DateOffset(months=6)).date(),
            min_value=min_available_date.date(),
            max_value=latest_date.date(),
            key="cz_start_key"
        )
    with cz_col2:
        cz_end = st.date_input(
            "Graph Zoom End:",
            value=latest_date.date(),
            min_value=min_available_date.date(),
            max_value=latest_date.date(),
            key="cz_end_key"
        )
    active_crop_start = pd.Timestamp(cz_start)
    active_crop_end = pd.Timestamp(cz_end)
else:
    active_crop_start = crop_start
    active_crop_end = crop_end

# Triggering "Reset Zoom" clears the crop boundaries back to default view
if reset_chart_view:
    active_crop_start = None
    active_crop_end = None

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 All", "🟠 Inteira", "🔵 Graínha", "🟢 Triturado"]
)

chart_config = {
    "displayModeBar": "hover",
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]
}

with tab1:
    st.plotly_chart(
        build_chart(selected_cats, active_crop_start, active_crop_end, chart_h_start, chart_h_end), 
        use_container_width=True, 
        key="all", 
        config=chart_config
    )
with tab2:
    st.plotly_chart(
        build_chart(["Alfarroba Inteira"], active_crop_start, active_crop_end, chart_h_start, chart_h_end), 
        use_container_width=True, 
        key="inteira", 
        config=chart_config
    )
with tab3:
    st.plotly_chart(
        build_chart(["Alfarroba Graínha"], active_crop_start, active_crop_end, chart_h_start, chart_h_end), 
        use_container_width=True, 
        key="grainha", 
        config=chart_config
    )
with tab4:
    st.plotly_chart(
        build_chart(["Alfarroba Triturado Grosso"], active_crop_start, active_crop_end, chart_h_start, chart_h_end), 
        use_container_width=True, 
        key="triturado", 
        config=chart_config
    )
# --- 11. RAW DATA TABLE ---
with st.expander("📋 Raw Data"):
    table_df = df.copy()
    num_cols = [c for c in table_df.columns if c != "date"]
    if multiplier != 1.0:
        for col in num_cols:
            table_df[col] = table_df[col] * multiplier
    table_df["date"] = table_df["date"].dt.strftime("%d/%m/%Y")
    st.dataframe(
        table_df[["date"] + num_cols].sort_values("date", ascending=False),
        use_container_width=True,
    )

# --- 12. DATA SOURCES & LEGAL DISCLAIMERS ---
st.divider()

col_source, col_disclaimer = st.columns(2)

with col_source:
    st.markdown("""
    ### ℹ️ Data Sources & Attribution
    
    * **Primary Source:** **SIMA** (*Sistema de Informação de Mercados Agrícolas*)
    * **Publishing Entity:** **GPP** (*Gabinete de Planeamento, Políticas e Administração Geral — Ministério da Agricultura e Pescas*)
    * **Platform Notice:** This dashboard is an **independent platform** designed to visualize publicly available agricultural data. It is not officially affiliated with or endorsed by GPP or SIMA.
    """)

with col_disclaimer:
    st.markdown("""
    ### ⚠️ Legal & Trading Disclaimer
    
    * **Informational Use Only:** All prices, trends, and statistics are presented strictly for general historical reference and analytical purposes.
    * **No Financial or Commercial Advice:** Data published here does **not** constitute commercial valuation, trading advice, or binding contract price fixing.
    * **Limitation of Liability:** The project maintainers accept no responsibility for commercial transactions, harvest negotiations, or financial losses resulting from reliance on this data.
    """)

st.markdown("<br>", unsafe_allow_html=True)
st.caption(
    "🌿 **Algarve Carob Market Tracker** | Open-source platform licensed under "
    "[CC BY-NC-SA 4.0](http://creativecommons.org/licenses/by-nc-sa/4.0/)."
)
