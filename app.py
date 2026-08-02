import os
import io
import requests
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ==========================================
# 1. PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Algarve Carob Market Prices",
    layout="wide",
    page_icon="🌾",
)

# ==========================================
# 2. DESIGN SYSTEM & CUSTOM CSS
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg: #16130F;
    --surface: #241E17;
    --surface-2: #2C251C;
    --text: #E8DFC8;
    --text-dim: #A69D8A;
    --pulp: #B5652D;
    --seed: #8B7355;
    --kibble: #5B6B4F;
    --accent: #3D5A5B;
    --delta-up: #7A9B76;
    --delta-down: #B25C4F;
}

html, body, [class*="css"] { 
    font-family: 'Inter', sans-serif; 
}

.eyebrow {
    font-size: 0.72rem; 
    letter-spacing: 0.12em; 
    text-transform: uppercase;
    color: var(--text-dim); 
    margin-bottom: 0.15rem;
}

.display-title {
    font-family: 'Fraunces', serif; 
    font-weight: 600; 
    font-size: 2.1rem;
    color: var(--text); 
    margin: 0 0 0.3rem 0; 
    line-height: 1.15;
}

.chart-heading {
    font-family: 'Fraunces', serif; 
    font-weight: 600; 
    font-size: 1.3rem;
    color: var(--text); 
    margin: 0 0 0.5rem 0;
}

.card {
    background: var(--surface); 
    border-radius: 10px; 
    padding: 16px 18px;
    margin-bottom: 12px; 
    border-left: 4px solid;
    border-top: 1px solid var(--surface-2);
    border-right: 1px solid var(--surface-2);
    border-bottom: 1px solid var(--surface-2);
    height: 100%;
}

.card.pulp { border-left-color: var(--pulp); }
.card.seed { border-left-color: var(--seed); }
.card.kibble { border-left-color: var(--kibble); }

.card-label {
    font-size: 0.7rem; 
    letter-spacing: 0.08em; 
    text-transform: uppercase;
    color: var(--text-dim); 
    margin-bottom: 4px;
}

.card-title {
    font-family: 'Fraunces', serif; 
    font-size: 1.1rem; 
    font-weight: 600;
    color: var(--text); 
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.card-main-val {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text);
    font-variant-numeric: tabular-nums;
    margin-top: 4px;
}

.delta-badge {
    font-size: 0.75rem; 
    font-weight: 600; 
    padding: 2px 8px; 
    border-radius: 12px;
    font-variant-numeric: tabular-nums;
    display: inline-block;
}

.delta-up { background: rgba(122,155,118,0.18); color: var(--delta-up); border: 1px solid rgba(122,155,118,0.3); }
.delta-down { background: rgba(178,92,79,0.18); color: var(--delta-down); border: 1px solid rgba(178,92,79,0.3); }
.delta-flat { background: rgba(166,157,138,0.15); color: var(--text-dim); }

.section-divider { 
    border: none; 
    border-top: 1px solid var(--surface-2); 
    margin: 1.6rem 0 1.2rem 0; 
}

@media (max-width: 768px) {
    .block-container { padding: 1rem 0.75rem !important; }
    [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }
    .display-title { font-size: 1.5rem; }
    [data-testid="stTabs"] > div:first-child { overflow-x: auto !important; white-space: nowrap !important; }
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. CONSTANTS & HELPERS
# ==========================================
MASTER_FILE = "sima_master.csv"
GET_COTACOES_URL = "https://regsima.gpp.pt/regsima/consulta/get_cotacoes"

CATEGORY_META = {
    "Alfarroba Inteira": {"key": "inteira", "css": "pulp", "color": "#B5652D", "short": "Inteira"},
    "Alfarroba Grainha": {"key": "grainha", "css": "seed", "color": "#8B7355", "short": "Graínha"},
    "Alfarroba Triturado Grosso": {"key": "triturado", "css": "kibble", "color": "#5B6B4F", "short": "Triturado"},
}

def hex_to_rgba(hex_str, opacity=0.15):
    hex_str = hex_str.lstrip('#')
    r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {opacity})"

# ==========================================
# 4. DATA FETCHING (Cached)
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_latest_sima_data(weeks_back=8):
    end = datetime.now()
    start = end - timedelta(weeks=weeks_back)
    params = {
        "setor": 23, "especie": 70, "regiao": 7, "mercado": 69,
        "tipo": 8, "export": 1,
        "ini": start.strftime("%Y-%m-%d"), "fim": end.strftime("%Y-%m-%d"),
    }
    try:
        res = requests.get(GET_COTACOES_URL, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        res.raise_for_status()
        res.encoding = "windows-1252"
        return pd.read_csv(io.StringIO(res.text), sep=";")
    except Exception as e:
        st.warning(f"Could not reach SIMA online: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
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

# ==========================================
# 5. DATA PROCESSING
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def process_data(df_raw):
    if df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = next((c for c in df.columns if "data" in c.lower()), None)
    prod_col = next((c for c in df.columns if "prod" in c.lower()), None)
    min_col = next((c for c in df.columns if "min" in c.lower() or "mín" in c.lower()), None)
    max_col = next((c for c in df.columns if "máx" in c.lower() or "max" in c.lower()), None)
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

    for c in [
        "inteira_freq", "inteira_min", "inteira_max",
        "grainha_freq", "grainha_min", "grainha_max",
        "triturado_freq", "triturado_min", "triturado_max"
    ]:
        if c not in pivoted.columns:
            pivoted[c] = pd.NA

    final = pivoted.reset_index().sort_values("date").reset_index(drop=True)
    val_cols = [c for c in final.columns if c != "date"]
    final[val_cols] = final[val_cols].ffill()

    return final

# ==========================================
# 6. SHARED HELPERS
# ==========================================
def resolve_period_start(period_label, latest_date, earliest_date):
    if period_label in ("All Time", "Max (All Time)", "MAX"):
        return earliest_date
    if period_label == "Year-to-Date (YTD)":
        return pd.Timestamp(year=latest_date.year, month=1, day=1)
    
    offsets = {
        "1 Week": {"weeks": 1},
        "1 Month": {"months": 1},
        "1M": {"months": 1},
        "3 Months": {"months": 3},
        "3M": {"months": 3},
        "6 Months": {"months": 6},
        "6M": {"months": 6},
        "1 Year": {"years": 1},
        "1Y": {"years": 1},
        "5 Years": {"years": 5},
        "5Y": {"years": 5},
    }
    kwargs = offsets.get(period_label)
    return latest_date - pd.DateOffset(**kwargs) if kwargs else earliest_date

def fmt_price(val, multiplier, unit_label):
    return f"{val * multiplier:.2f} {unit_label}" if pd.notna(val) else "N/A"

def render_card(category_label, freq, multiplier, unit_label, delta_pct=None):
    meta = CATEGORY_META[category_label]
    delta_html = ""
    if delta_pct is not None:
        cls = "delta-up" if delta_pct > 0.05 else ("delta-down" if delta_pct < -0.05 else "delta-flat")
        arrow = "▲" if delta_pct > 0.05 else ("▼" if delta_pct < -0.05 else "•")
        delta_html = f'<span class="delta-badge {cls}">{arrow} {abs(delta_pct):.1f}%</span>'

    st.markdown(f"""
    <div class="card {meta['css']}">
        <div class="card-label">{meta['short']}</div>
        <div class="card-title">
            <span>{category_label}</span>
            {delta_html}
        </div>
        <div class="card-main-val">{fmt_price(freq, multiplier, unit_label)}</div>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 7. LOAD DATA
# ==========================================
raw_sima_data = sync_and_get_master_data()
df_all = process_data(raw_sima_data)

if df_all.empty:
    st.warning("No SIMA data found. Place a SIMA export CSV in this folder and restart.")
    st.stop()

last_date = df_all["date"].max().strftime("%Y-%m-%d")
earliest_date = df_all["date"].min()
latest_date = df_all["date"].max()

# ==========================================
# 8. SIDEBAR CONTROLS
# ==========================================
st.sidebar.header("Global Settings")

if st.sidebar.button("Refresh SIMA Data"):
    st.cache_data.clear()
    st.rerun()

unit_mode = st.sidebar.selectbox("Display Unit", ["EUR/kg", "EUR / arroba (15 kg)"])
multiplier = 15.0 if "arroba" in unit_mode else 1.0
unit_label = "€/@" if "arroba" in unit_mode else "€/kg"

st.sidebar.markdown("---")
st.sidebar.subheader("📈 Technical Overlays")

enable_hlc_range = st.sidebar.checkbox("Overlay High-Low (Min-Max) Band", value=True)
enable_sma = st.sidebar.checkbox("Overlay SMA (Moving Avg)", value=False)
sma_window = st.sidebar.number_input("SMA Window (weeks)", min_value=2, max_value=52, value=4) if enable_sma else 4

enable_bb = st.sidebar.checkbox("Overlay Bollinger Bands", value=False)
enable_rsi = st.sidebar.checkbox("Show RSI Subplot (14-period)", value=False)

scale_type = st.sidebar.radio("Y-Axis Scale Mode", ["Linear", "Logarithmic"], index=0)
is_log_scale = scale_type == "Logarithmic"

show_rangeslider = st.sidebar.checkbox("Show Range Slider", value=False)

# ==========================================
# 9. HEADER
# ==========================================
st.markdown('<div class="eyebrow">Algarve SIMA Market Data</div>', unsafe_allow_html=True)
st.markdown('<div class="display-title">Carob Market Prices</div>', unsafe_allow_html=True)
st.caption(f"Latest entry: **{last_date}** farm-gate quotes (Inteira / Graínha / Triturado Grosso)")

# ==========================================
# 10. CURRENT SNAPSHOT
# ==========================================
st.markdown("### Current Quotes")
latest = df_all.iloc[-1]
cols = st.columns(3, gap="medium")

for col, cat_label in zip(cols, CATEGORY_META.keys()):
    key = CATEGORY_META[cat_label]["key"]
    with col:
        render_card(
            cat_label,
            latest.get(f"{key}_freq"),
            multiplier,
            unit_label
        )

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ==========================================
# 11. PRICE CHANGE COMPARISON
# ==========================================
st.markdown("### Price Change Comparison")
st.caption("Compares current market quotes against a chosen baseline point in history.")

comp_col1, comp_col2 = st.columns([3, 2])

with comp_col1:
    comp_period = st.selectbox(
        "Compare latest quote to:",
        ["1 Week", "1 Month", "3 Months", "6 Months", "Year-to-Date (YTD)", "1 Year", "5 Years", "Max (All Time)", "Custom range"],
        index=1
    )

with comp_col2:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    show_highlight = st.checkbox("Highlight comparison window on chart", value=False, disabled=(comp_period == "Max (All Time)"))

if comp_period == "Custom range":
    c1, c2 = st.columns(2)
    picked_start = c1.date_input("From", value=(latest_date - pd.DateOffset(months=1)).date(), min_value=earliest_date.date(), max_value=latest_date.date())
    picked_end = c2.date_input("To (baseline)", value=latest_date.date(), min_value=earliest_date.date(), max_value=latest_date.date())
    if picked_start > picked_end:
        picked_start, picked_end = picked_end, picked_start
        st.info("Start and end were swapped to keep a valid range.")
    baseline_date = pd.Timestamp(picked_start)
    chart_crop_end = pd.Timestamp(picked_end)
else:
    baseline_date = resolve_period_start(comp_period, latest_date, earliest_date)
    chart_crop_end = latest_date

baseline_row = df_all[df_all["date"] <= baseline_date]
baseline_row = baseline_row.iloc[-1] if not baseline_row.empty else df_all.iloc[0]

actual_base_date_str = baseline_row["date"].strftime("%d/%m/%Y")
st.caption(f"Baseline comparison point: **{actual_base_date_str}**")

comp_cols = st.columns(3, gap="medium")
for col, cat_label in zip(comp_cols, CATEGORY_META.keys()):
    key = CATEGORY_META[cat_label]["key"]
    latest_freq = latest.get(f"{key}_freq")
    delta_pct = None
    if baseline_row is not None:
        base_freq = baseline_row.get(f"{key}_freq")
        if pd.notna(base_freq) and base_freq != 0 and pd.notna(latest_freq):
            delta_pct = ((latest_freq - base_freq) / base_freq) * 100

    with col:
        render_card(
            cat_label,
            latest_freq,
            multiplier,
            unit_label,
            delta_pct=delta_pct
        )

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ==========================================
# 12. TRADINGVIEW-STYLE CHART ENGINE
# ==========================================
selected_cats_for_chart = list(CATEGORY_META.keys())

st.markdown('<div class="chart-heading">Price History & Analytics</div>', unsafe_allow_html=True)

# --- UNIFIED INLINE TIME RANGE BAR ---
t_col1, t_col2, t_col3 = st.columns([3.2, 1, 1], vertical_alignment="bottom")

with t_col1:
    selected_range_preset = st.radio(
        "Chart Horizon",
        ["1M", "3M", "6M", "YTD", "1Y", "5Y", "MAX", "Custom"],
        index=6,
        horizontal=True,
        label_visibility="collapsed"
    )

if selected_range_preset == "Custom":
    with t_col2:
        custom_from = pd.Timestamp(st.date_input("From", value=(latest_date - pd.DateOffset(months=6)).date(), min_value=earliest_date.date(), max_value=latest_date.date()))
    with t_col3:
        custom_to = pd.Timestamp(st.date_input("To", value=latest_date.date(), min_value=earliest_date.date(), max_value=latest_date.date()))
    
    if custom_from > custom_to:
        custom_from, custom_to = custom_to, custom_from
    
    range_start_date, range_end_date = custom_from, custom_to
else:
    range_end_date = latest_date
    range_start_date = resolve_period_start(selected_range_preset, latest_date, earliest_date)

def build_chart(categories_to_plot):
    # Slice dataframe dynamically so plot scale adjusts automatically
    df_slice = df_all[(df_all["date"] >= range_start_date) & (df_all["date"] <= range_end_date)].copy()

    if enable_rsi:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.75, 0.25],
            subplot_titles=("Price History & Overlays", "RSI (14)")
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    for cat in categories_to_plot:
        meta = CATEGORY_META[cat]
        key = meta["key"]

        # 1. High-Low (Min-Max) Band
        if enable_hlc_range:
            col_min = f"{key}_min"
            col_max = f"{key}_max"
            if col_min in df_slice.columns and col_max in df_slice.columns:
                y_min = df_slice[col_min] * multiplier
                y_max = df_slice[col_max] * multiplier

                fig.add_trace(
                    go.Scatter(
                        x=df_slice["date"], y=y_max,
                        name=f"{meta['short']} Max Range",
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo="skip"
                    ),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_slice["date"], y=y_min,
                        name=f"{meta['short']} Min-Max Band",
                        line=dict(width=0),
                        fill="tonexty",
                        fillcolor=hex_to_rgba(meta["color"], opacity=0.12),
                        showlegend=False,
                        hoverinfo="skip"
                    ),
                    row=1, col=1
                )

        # 2. Main Price Line (Mais Frequente)
        col_freq = f"{key}_freq"
        if col_freq in df_slice.columns:
            y_full = df_slice[col_freq] * multiplier

            fig.add_trace(
                go.Scatter(
                    x=df_slice["date"],
                    y=y_full,
                    name=meta['short'],
                    line=dict(color=meta["color"], width=2.2),
                    connectgaps=True,
                ),
                row=1, col=1
            )

            # Moving Average Overlay
            if enable_sma:
                sma_series = y_full.rolling(window=sma_window).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df_slice["date"],
                        y=sma_series,
                        name=f"{meta['short']} SMA ({sma_window}w)",
                        line=dict(color=meta["color"], width=1.2, dash="dashdot"),
                        opacity=0.75
                    ),
                    row=1, col=1
                )

            # Bollinger Bands Overlay
            if enable_bb:
                bb_mid = y_full.rolling(20).mean()
                bb_std = y_full.rolling(20).std()
                bb_upper = bb_mid + (bb_std * 2)
                bb_lower = bb_mid - (bb_std * 2)

                fig.add_trace(
                    go.Scatter(
                        x=df_slice["date"], y=bb_upper,
                        name=f"{meta['short']} Upper BB",
                        line=dict(color=meta["color"], width=0.8, dash="dot"),
                        showlegend=False
                    ),
                    row=1, col=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_slice["date"], y=bb_lower,
                        name=f"{meta['short']} Lower BB",
                        line=dict(color=meta["color"], width=0.8, dash="dot"),
                        fill="tonexty",
                        fillcolor="rgba(255,255,255,0.03)",
                        showlegend=False
                    ),
                    row=1, col=1
                )

            # RSI Subplot
            if enable_rsi:
                delta = y_full.diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))

                fig.add_trace(
                    go.Scatter(
                        x=df_slice["date"], y=rsi,
                        name=f"{meta['short']} RSI",
                        line=dict(color=meta["color"], width=1.5)
                    ),
                    row=2, col=1
                )

    if enable_rsi:
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(239, 68, 68, 0.5)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(34, 197, 94, 0.5)", row=2, col=1)
        fig.update_yaxes(range=[0, 100], row=2, col=1, title="RSI", gridcolor="#2C251C")

    xaxis_config = dict(
        type="date",
        gridcolor="#2C251C",
        linecolor="#2C251C",
        rangeslider=dict(visible=show_rangeslider, bgcolor="#241E17"),
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikedash="dot", spikecolor="#A69D8A"
    )

    # Autorange automatically fits vertical scale to sliced visible range
    yaxis_config = dict(
        type="log" if is_log_scale else "linear",
        autorange=True,
        title=f"Price ({unit_label})",
        gridcolor="#2C251C",
        linecolor="#2C251C",
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikedash="dot", spikecolor="#A69D8A"
    )

    if show_highlight and comp_period != "Max (All Time)":
        fig.add_vrect(
            x0=baseline_date,
            x1=chart_crop_end,
            fillcolor="rgba(61, 90, 91, 0.18)",
            layer="below", line_width=1.5, line_dash="dash",
            line_color="rgba(61, 90, 91, 0.5)",
            annotation_text="Comparison Period",
            annotation_position="top left",
            annotation_font=dict(size=10, color="#A69D8A")
        )

    fig.update_layout(
        paper_bgcolor="#16130F",
        plot_bgcolor="#1D1811",
        font=dict(color="#E8DFC8", family="Inter, sans-serif"),
        showlegend=False,
        xaxis=xaxis_config,
        yaxis=yaxis_config,
        hovermode="x unified",
        height=620 if enable_rsi else 500,
        margin=dict(t=20, b=50 if not show_rangeslider else 90, l=50, r=10),
    )

    return fig

tab1, tab2, tab3, tab4 = st.tabs(["All Products", "Inteira", "Graínha", "Triturado"])

with tab1:
    st.plotly_chart(build_chart(selected_cats_for_chart), use_container_width=True, key="chart_all")
with tab2:
    st.plotly_chart(build_chart(["Alfarroba Inteira"]), use_container_width=True, key="chart_inteira")
with tab3:
    st.plotly_chart(build_chart(["Alfarroba Grainha"]), use_container_width=True, key="chart_grainha")
with tab4:
    st.plotly_chart(build_chart(["Alfarroba Triturado Grosso"]), use_container_width=True, key="chart_triturado")

# ==========================================
# 13. RAW DATA VIEW
# ==========================================
with st.expander("📋 View Raw SIMA Dataset"):
    table_df = df_all.copy()
    num_cols = [c for c in table_df.columns if c != "date"]
    
    if multiplier != 1.0:
        for col in num_cols:
            table_df[col] = table_df[col] * multiplier

    table_df["date"] = table_df["date"].dt.strftime("%d/%m/%Y")
    st.dataframe(
        table_df[["date"] + num_cols].sort_values("date", ascending=False),
        use_container_width=True
    )

# ==========================================
# 14. FOOTER
# ==========================================
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("""
<div style="font-size: 0.8rem; color: var(--text-dim); line-height: 1.6;">
    <strong>Data source:</strong> GPP / SIMA (regsima.gpp.pt), Portugal's public agricultural market information system. Independently collected and processed; not affiliated with or endorsed by GPP or IPMA.<br>
    <strong>Code license:</strong> PolyForm Noncommercial 1.0.0 - free for personal, research, and noncommercial use. Commercial use requires permission.<br>
    <strong>Disclaimer:</strong> Figures shown are informational and may not reflect the exact price achievable in any individual transaction. Verify independently before relying on them.
</div>
""", unsafe_allow_html=True)
