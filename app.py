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

# --- 2. MOBILE CSS (unchanged) ---
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
.comp-delta.pos     { background: rgba(34, 197, 94, 0.15) !important;  color: #4ade80 !important; }
.comp-delta.neg     { background: rgba(239, 68, 68, 0.15) !important;  color: #f87171 !important; }
.comp-delta.neutral { background: rgba(161, 161, 170, 0.15) !important; color: #a1a1aa !important; }
</style>
""", unsafe_allow_html=True)

# --- 3. CONSTANTS ---
MASTER_FILE = "sima_master.csv"
GET_COTACOES_URL = "https://regsima.gpp.pt/regsima/consulta/get_cotacoes"

VALUE_COLS = [
    "inteira_freq", "inteira_min", "inteira_max",
    "grainha_freq", "grainha_min", "grainha_max",
    "triturado_freq", "triturado_min", "triturado_max",
]

CATEGORIES = ["Alfarroba Inteira", "Alfarroba Graínha", "Alfarroba Triturado Grosso"]
PRICE_TYPES = ["Mais Frequente (Freq)", "Mínimo (Min)", "Máximo (Max)"]

line_styles = {"Mais Frequente (Freq)": "solid", "Mínimo (Min)": "dash", "Máximo (Max)": "dot"}
cat_colors = {
    "Alfarroba Inteira": "#D97706",
    "Alfarroba Graínha": "#2563EB",
    "Alfarroba Triturado Grosso": "#059669",
}
clean_cat_names = {
    "Alfarroba Inteira": "Inteira",
    "Alfarroba Graínha": "Graínha",
    "Alfarroba Triturado Grosso": "Triturado",
}
clean_ptypes = {
    "Mais Frequente (Freq)": "Freq",
    "Mínimo (Min)": "Min",
    "Máximo (Max)": "Max",
}
field_map = {
    (cat, ptype): f"{clean_cat_names[cat].lower().replace('graínha', 'grainha')}_{clean_ptypes[ptype].lower()}"
    for cat in CATEGORIES for ptype in PRICE_TYPES
}


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
        # ROBUSTNESS FIX: the old check was `if df[col].dtype == object`.
        # On pandas builds that back strings with pyarrow (the default from
        # pandas 3.0), that comparison is False even for text columns, so the
        # comma->dot swap was skipped and every European-formatted value
        # ("0,45") silently became NaN. is_numeric_dtype is backend-agnostic.
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].astype(str).str.replace(",", ".", regex=False).str.strip()
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

    for c in VALUE_COLS:
        if c not in pivoted.columns:
            pivoted[c] = pd.NA

    final = pivoted.reset_index().sort_values("date").reset_index(drop=True)
    val_cols = [c for c in final.columns if c != "date"]
    final[val_cols] = final[val_cols].ffill()

    # PERF: force numeric dtype once here, so no per-render pd.to_numeric is needed later
    for c in val_cols:
        final[c] = pd.to_numeric(final[c], errors="coerce")

    return final


# PERF: single cached entry point. Previously sync_and_get_master_data() ran on
# EVERY rerun (every checkbox tick / dropdown change), meaning a live HTTP request
# to SIMA and a CSV rewrite to disk each time. Now it runs at most once an hour.
@st.cache_data(ttl=3600, show_spinner="Loading SIMA market data…")
def load_market_data():
    return process_data(sync_and_get_master_data())


# PERF: apply the unit multiplier once per (data, multiplier) pair instead of
# re-multiplying inside every single chart trace on every rerun.
@st.cache_data(show_spinner=False)
def get_scaled(df, multiplier):
    if multiplier == 1.0:
        return df
    out = df.copy()
    for c in VALUE_COLS:
        if c in out.columns:
            out[c] = out[c] * multiplier
    return out


# --- 6. LOAD DATA ---
df_all = load_market_data()

if df_all.empty:
    st.warning("No SIMA data found. Place your SIMA export CSV in this folder and restart.")
    st.stop()

last_date = df_all["date"].max().strftime("%Y-%m-%d")
latest_date = df_all["date"].max()
min_available_date = df_all["date"].min()


# --- 7. SIDEBAR ---
st.sidebar.header("⚙️ Filters")

if st.sidebar.button("🔄 Sync Latest SIMA Quotes"):
    # PERF: just invalidate + rerun. The old version re-called sync and process
    # inline, doing the same expensive work twice in one click.
    load_market_data.clear()
    st.rerun()

time_range = st.sidebar.radio("Range:", ["All Time", "5 Years", "1 Year", "6 Months"], index=0)

max_date = latest_date
if time_range == "6 Months":
    min_date = max_date - pd.DateOffset(months=6)
elif time_range == "1 Year":
    min_date = max_date - pd.DateOffset(years=1)
elif time_range == "5 Years":
    min_date = max_date - pd.DateOffset(years=5)
else:
    min_date = min_available_date

unit_mode = st.sidebar.selectbox("Unit:", ["EUR / kg", "EUR / arroba (15 kg)"])
multiplier = 15.0 if "arroba" in unit_mode else 1.0
unit_label = "€/@" if "arroba" in unit_mode else "€/kg"

selected_cats = st.sidebar.multiselect("Categories:", CATEGORIES, default=CATEGORIES)
selected_price_types = st.sidebar.multiselect("Price Types:", PRICE_TYPES,
                                              default=["Mais Frequente (Freq)"])

# Scaled + range-filtered frames, computed once for the whole render
df_scaled = get_scaled(df_all, multiplier)
df = df_scaled[(df_scaled["date"] >= min_date) & (df_scaled["date"] <= max_date)].copy()

# latest/scaled row for the cards
latest = df_scaled.iloc[-1]


# --- 8. HEADER ---
st.title("🌿 Algarve Carob Market Prices")
st.caption(f"🟢 Live SIMA data | Latest entry: {last_date}")


# --- 9. METRIC CARDS ---
st.markdown("### 📍 Current Quotes")


def fmt(val):
    return f"{val:.2f} {unit_label}" if pd.notna(val) else "N/A"


def price_card(title, css_class, freq_key, min_key, max_key):
    st.markdown(f"""
    <div class="price-card {css_class}">
        <div class="card-title">{title}</div>
        <div class="card-row"><span>Freq</span><span class="card-val">{fmt(latest.get(freq_key))}</span></div>
        <div class="card-row"><span>Min</span><span class="card-val">{fmt(latest.get(min_key))}</span></div>
        <div class="card-row"><span>Max</span><span class="card-val">{fmt(latest.get(max_key))}</span></div>
    </div>
    """, unsafe_allow_html=True)


price_card("🟠 Alfarroba Inteira",         "inteira",   "inteira_freq",   "inteira_min",   "inteira_max")
price_card("🔵 Alfarroba Graínha",          "grainha",   "grainha_freq",   "grainha_min",   "grainha_max")
price_card("🟢 Alfarroba Triturado Grosso", "triturado", "triturado_freq", "triturado_min", "triturado_max")


# --- 9.5. PRICE COMPARISON ---
st.markdown("### 📊 Price Change Comparison")

comp_col_select, comp_col_toggle = st.columns([3, 2])
with comp_col_select:
    comp_period = st.selectbox(
        "Compare price changes across period:",
        ["None (Off)", "1 Week", "1 Month", "3 Months", "6 Months",
         "Year-to-Date (YTD)", "1 Year", "5 Years", "Max (All Time)",
         "📅 Custom Date Range"],
        index=0,
    )
with comp_col_toggle:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    show_highlight = st.checkbox(
        "Highlight period on chart",
        value=False,
        disabled=(comp_period == "None (Off)"),
    )

# INTERACTIVITY: one shared resolver, instead of the long if/elif chain that was
# duplicated between the comparison block and the sidebar range.
PERIOD_OFFSETS = {
    "1 Week":   {"weeks": 1},
    "1 Month":  {"months": 1},
    "3 Months": {"months": 3},
    "6 Months": {"months": 6},
    "1 Year":   {"years": 1},
    "5 Years":  {"years": 5},
}


def resolve_period_start(label):
    if label == "Year-to-Date (YTD)":
        return pd.Timestamp(year=latest_date.year, month=1, day=1)
    if label in PERIOD_OFFSETS:
        return latest_date - pd.DateOffset(**PERIOD_OFFSETS[label])
    return min_available_date


def clamp_default(ts):
    """ROBUSTNESS FIX: st.date_input raises if its default `value` falls outside
    [min_value, max_value]. Defaults like "6 months back" do exactly that whenever
    the dataset spans less than 6 months (fresh install, or a short SIMA window),
    crashing the zoom control. Clamping keeps the default inside the real range."""
    d = ts.date() if hasattr(ts, "date") else ts
    return min(max(d, min_available_date.date()), latest_date.date())


if comp_period == "None (Off)":
    start_date = end_date = crop_start = crop_end = None
    chart_h_start = chart_h_end = None
    st.info("💡 Select a time period or custom range above to compare price changes.")
else:
    if comp_period == "📅 Custom Date Range":
        col_start, col_end = st.columns(2)
        with col_start:
            picked_start = st.date_input(
                "Start Date:",
                value=clamp_default(latest_date - pd.DateOffset(months=1)),
                min_value=min_available_date.date(),
                max_value=latest_date.date(),
                key="comp_start_date",
            )
        with col_end:
            picked_end = st.date_input(
                "End Date:",
                value=clamp_default(latest_date),
                min_value=min_available_date.date(),
                max_value=latest_date.date(),
                key="comp_end_date",
            )
        # FIX: previously an inverted range collapsed to a zero-width window
        # (end was set to start). Now the two are swapped so the comparison
        # still returns something meaningful.
        if picked_start > picked_end:
            picked_start, picked_end = picked_end, picked_start
            st.warning("⚠️ Start was later than End — the dates have been swapped.")
        start_date = pd.Timestamp(picked_start)
        end_date = pd.Timestamp(picked_end)
    else:
        end_date = latest_date
        start_date = resolve_period_start(comp_period)

    crop_start, crop_end = start_date, end_date
    chart_h_start = start_date if show_highlight else None
    chart_h_end = end_date if show_highlight else None

    start_df = df_scaled[df_scaled["date"] <= start_date]
    start_row = start_df.iloc[-1] if not start_df.empty else df_scaled.iloc[0]
    end_df = df_scaled[df_scaled["date"] <= end_date]
    end_row = end_df.iloc[-1] if not end_df.empty else df_scaled.iloc[-1]

    st.caption(
        f"Comparing baseline prices from **{start_row['date'].strftime('%d/%m/%Y')}** "
        f"to **{end_row['date'].strftime('%d/%m/%Y')}**"
    )

    categories_info = [("🟠 Inteira", "inteira"), ("🔵 Graínha", "grainha"), ("🟢 Triturado", "triturado")]

    grid_parts = ['<div class="comp-container">']
    for title, key in categories_info:
        grid_parts.append(f'<div class="comp-col"><div class="comp-header">{title}</div>')
        for ptype, pkey in [("Freq", f"{key}_freq"), ("Min", f"{key}_min"), ("Max", f"{key}_max")]:
            end_v, start_v = end_row.get(pkey), start_row.get(pkey)
            if pd.notna(end_v) and pd.notna(start_v) and start_v > 0:
                diff = end_v - start_v
                pct = (diff / start_v) * 100
                cls = "pos" if diff > 0 else ("neg" if diff < 0 else "neutral")
                grid_parts.append(
                    f'<div class="comp-metric-item">'
                    f'<span class="comp-label">{ptype}</span>'
                    f'<span class="comp-val">{end_v:.2f} {unit_label}</span>'
                    f'<span class="comp-delta {cls}">{diff:+.2f} ({pct:+.1f}%)</span>'
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
def build_chart(categories_to_plot, crop_start=None, crop_end=None,
                highlight_start=None, highlight_end=None):
    fig = go.Figure()

    # PERF: slice once for the y-range calculation instead of re-slicing per trace
    if crop_start and crop_end:
        mask = (df["date"] >= pd.Timestamp(crop_start)) & (df["date"] <= pd.Timestamp(crop_end))
        df_slice = df[mask]
    else:
        df_slice = df

    visible_min, visible_max = None, None

    for ptype in selected_price_types:
        for cat in categories_to_plot:
            col_name = field_map.get((cat, ptype))
            if not col_name or col_name not in df.columns:
                continue

            # PERF: values are already numeric and already scaled — no conversion here
            y_data = df[col_name]

            s = df_slice[col_name].dropna()
            if not s.empty:
                lo, hi = s.min(), s.max()
                visible_min = lo if visible_min is None else min(visible_min, lo)
                visible_max = hi if visible_max is None else max(visible_max, hi)

            fig.add_trace(go.Scatter(
                x=df["date"],
                y=y_data,
                name=f"{clean_cat_names.get(cat, cat)} ({clean_ptypes.get(ptype, ptype)})",
                line=dict(color=cat_colors[cat], dash=line_styles[ptype], width=2),
                connectgaps=True,
            ))

    xaxis_config = dict(type="date")
    yaxis_config = dict(type="linear", tickformat=".2f" if multiplier == 1.0 else ".1f")

    if crop_start and crop_end:
        xaxis_config["range"] = [crop_start, crop_end]

    if visible_min is not None:
        span = visible_max - visible_min
        padding = span * 0.08 if span > 0 else (visible_max * 0.05 if visible_max > 0 else 0.5)
        yaxis_config["range"] = [max(0, visible_min - padding), visible_max + padding]
        yaxis_conf