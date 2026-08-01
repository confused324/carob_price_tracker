# app.py — Algarve Carob Market Prices
import os
import io
from datetime import datetime, timedelta

import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ============================================================
# 1. PAGE CONFIG (must be first Streamlit call)
# ============================================================
st.set_page_config(
    page_title="Algarve Carob Market Prices",
    layout="wide",
    page_icon="🌿",
)

# ============================================================
# 2. DESIGN SYSTEM — grounded in the actual product. Native
#    Streamlit widgets (sidebar, radios, selects) are themed
#    via .streamlit/config.toml, not CSS overrides — more
#    durable across Streamlit versions.
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg:        #16130F;
    --surface:   #241E17;
    --surface-2: #2C251C;
    --text:      #E8DFC8;
    --text-dim:  #A69D8A;
    --pulp:      #B5652D;
    --seed:      #8B7355;
    --kibble:    #5B6B4F;
    --accent:    #3D5A5B;
    --delta-up:  #7A9B76;
    --delta-down:#B25C4F;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.eyebrow {
    font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--text-dim); margin-bottom: 0.15rem;
}
.display-title {
    font-family: 'Fraunces', serif; font-weight: 600; font-size: 2.1rem;
    color: var(--text); margin: 0 0 0.3rem 0; line-height: 1.15;
}
.chart-heading {
    font-family: 'Fraunces', serif; font-weight: 600; font-size: 1.3rem;
    color: var(--text); margin: 0 0 0.5rem 0;
}
.chart-legend {
    display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 0.8rem;
    font-size: 0.85rem; color: var(--text-dim);
}
.chart-legend span.dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    margin-right: 6px; vertical-align: middle;
}

.card {
    background: var(--surface); border-radius: 10px; padding: 14px 18px;
    margin-bottom: 12px; border-left: 3px solid;
}
.card.pulp   { border-color: var(--pulp); }
.card.seed   { border-color: var(--seed); }
.card.kibble { border-color: var(--kibble); }
.card-label {
    font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--text-dim); margin-bottom: 4px;
}
.card-title {
    font-family: 'Fraunces', serif; font-size: 1.05rem; font-weight: 600;
    color: var(--text); margin-bottom: 8px;
}
.card-row {
    display: flex; justify-content: space-between; align-items: baseline;
    font-size: 0.86rem; color: var(--text-dim); padding: 2px 0;
}
.card-val { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--text); }
.delta-badge {
    font-size: 0.78rem; font-weight: 600; padding: 1px 7px; border-radius: 20px;
    font-variant-numeric: tabular-nums;
}
.delta-up   { background: rgba(122,155,118,0.18); color: var(--delta-up); }
.delta-down { background: rgba(178,92,79,0.18);  color: var(--delta-down); }
.delta-flat { background: rgba(166,157,138,0.15); color: var(--text-dim); }

.section-divider { border: none; border-top: 1px solid var(--surface-2); margin: 1.6rem 0 1.2rem 0; }

@media (max-width: 768px) {
    .block-container { padding: 1rem 0.75rem !important; }
    [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 100% !important; }
    .display-title { font-size: 1.5rem; }
    [data-testid="stTabs"] > div:first-child { overflow-x: auto !important; white-space: nowrap !important; }
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# 3. CONSTANTS
# ============================================================
MASTER_FILE = "sima_master.csv"
GET_COTACOES_URL = "https://regsima.gpp.pt/regsima/consulta/get_cotacoes"

CATEGORY_META = {
    "Alfarroba Inteira":          {"key": "inteira",   "css": "pulp",   "color": "#B5652D", "short": "Inteira"},
    "Alfarroba Graínha":          {"key": "grainha",   "css": "seed",   "color": "#8B7355", "short": "Graínha"},
    "Alfarroba Triturado Grosso": {"key": "triturado", "css": "kibble", "color": "#5B6B4F", "short": "Triturado"},
}
PRICE_TYPE_META = {
    "Mais Frequente (Freq)": {"field": "freq", "dash": "solid"},
    "Mínimo (Min)":          {"field": "min",  "dash": "dash"},
    "Máximo (Max)":          {"field": "max",  "dash": "dot"},
}

# ============================================================
# 4. DATA FETCHING (cached)
# ============================================================
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
        res = requests.get(GET_COTACOES_URL, params=params,
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        res.raise_for_status()
        res.encoding = "windows-1252"
        return pd.read_csv(io.StringIO(res.text), sep=";")
    except Exception as e:
        st.warning(f"Could not reach SIMA: {e}")
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


# ============================================================
# 5. DATA PROCESSING
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
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


# ============================================================
# 6. SHARED HELPERS
# ============================================================
def resolve_period_start(period_label, latest_date, earliest_date):
    if period_label in ("All Time", "Max (All Time)"):
        return earliest_date
    if period_label == "Year-to-Date (YTD)":
        return pd.Timestamp(year=latest_date.year, month=1, day=1)
    offsets = {
        "1 Week": {"weeks": 1}, "1 Month": {"months": 1}, "3 Months": {"months": 3},
        "6 Months": {"months": 6}, "1 Year": {"years": 1}, "5 Years": {"years": 5},
    }
    kwargs = offsets.get(period_label)
    return latest_date - pd.DateOffset(**kwargs) if kwargs else earliest_date


def fmt_price(val, multiplier, unit_label):
    return f"{val * multiplier:.2f} {unit_label}" if pd.notna(val) else "N/A"


def render_card(category_label, freq, min_v, max_v, multiplier, unit_label, delta_pct=None):
    meta = CATEGORY_META[category_label]
    delta_html = ""
    if delta_pct is not None:
        cls = "delta-up" if delta_pct > 0.05 else "delta-down" if delta_pct < -0.05 else "delta-flat"
        arrow = "▲" if delta_pct > 0.05 else "▼" if delta_pct < -0.05 else "–"
        delta_html = f'<span class="delta-badge {cls}">{arrow} {abs(delta_pct):.1f}%</span>'
    st.markdown(f"""
    <div class="card {meta['css']}">
        <div class="card-label">{meta['short']}</div>
        <div class="card-title">{category_label} {delta_html}</div>
        <div class="card-row"><span>Freq</span><span class="card-val">{fmt_price(freq, multiplier, unit_label)}</span></div>
        <div class="card-row"><span>Min</span><span class="card-val">{fmt_price(min_v, multiplier, unit_label)}</span></div>
        <div class="card-row"><span>Max</span><span class="card-val">{fmt_price(max_v, multiplier, unit_label)}</span></div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# 7. LOAD DATA
# ============================================================
raw_sima_data = sync_and_get_master_data()
df_all = process_data(raw_sima_data)

if df_all.empty:
    st.warning("No SIMA data found. Place a SIMA export CSV in this folder and restart.")
    st.stop()

last_date = df_all["date"].max().strftime("%Y-%m-%d")
earliest_date = df_all["date"].min()
latest_date = df_all["date"].max()

# ============================================================
# 8. SIDEBAR — only genuinely sidebar-appropriate, global
#    settings live here now. Range and Categories were
#    removed: both duplicated controls already on the main
#    page (chart tabs, chart zoom).
# ============================================================
st.sidebar.header("Filters")

if st.sidebar.button("Refresh SIMA data"):
    st.cache_data.clear()
    st.rerun()

unit_mode = st.sidebar.selectbox("Unit", ["EUR / kg", "EUR / arroba (15 kg)"])
multiplier = 15.0 if "arroba" in unit_mode else 1.0
unit_label = "€/@" if "arroba" in unit_mode else "€/kg"

selected_price_types = st.sidebar.multiselect(
    "Price types", list(PRICE_TYPE_META.keys()), default=["Mais Frequente (Freq)"]
)

# ============================================================
# 9. HEADER
# ============================================================
st.markdown('<div class="eyebrow">Algarve · SIMA Market Data</div>', unsafe_allow_html=True)
st.markdown('<div class="display-title">Carob Market Prices</div>', unsafe_allow_html=True)
st.caption(f"Latest entry {last_date} · farm-gate quotes, Alfarroba Inteira / Graínha / Triturado Grosso")

# ============================================================
# 10. CURRENT SNAPSHOT
# ============================================================
st.markdown("### Current quotes")
latest = df_all.iloc[-1]
cols = st.columns(3, gap="medium")
for col, cat_label in zip(cols, CATEGORY_META.keys()):
    key = CATEGORY_META[cat_label]["key"]
    with col:
        render_card(cat_label, latest.get(f"{key}_freq"), latest.get(f"{key}_min"),
                    latest.get(f"{key}_max"), multiplier, unit_label)

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ============================================================
# 11. PRICE CHANGE COMPARISON
# ============================================================
st.markdown("### Price change comparison")
st.caption("Compares the latest quote against a chosen point in the past.")

comp_period = st.selectbox(
    "Compare latest quote to",
    ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year", "Custom range"], index=1,
)
if comp_period == "Custom range":
    c1, c2 = st.columns(2)
    picked_start = c1.date_input("From", value=(latest_date - pd.DateOffset(months=1)).date())
    picked_end = c2.date_input("To (baseline)", value=latest_date.date())
    if picked_start > picked_end:
        picked_start, picked_end = picked_end, picked_start
        st.info("Start and end were swapped to keep a valid range.")
    baseline_date = pd.Timestamp(picked_start)
else:
    baseline_date = resolve_period_start(comp_period, latest_date, earliest_date)

baseline_row = df_all[df_all["date"] <= baseline_date]
baseline_row = baseline_row.iloc[-1] if not baseline_row.empty else None

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
        render_card(cat_label, latest_freq, latest.get(f"{key}_min"), latest.get(f"{key}_max"),
                    multiplier, unit_label, delta_pct=delta_pct)

if baseline_row is not None:
    st.caption(f"Baseline: {baseline_row['date'].strftime('%Y-%m-%d')}")

st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

# ============================================================
# 12. CHART — title and legend are now plain Streamlit
#     elements above the figure, not Plotly-internal ones.
# ============================================================
selected_cats_for_chart = list(CATEGORY_META.keys())

legend_html = '<div class="chart-legend">' + "".join(
    f'<span><span class="dot" style="background:{m["color"]}"></span>{m["short"]}</span>'
    for m in CATEGORY_META.values()
) + '</div>'

st.markdown(f'<div class="chart-heading">Price history</div>{legend_html}', unsafe_allow_html=True)

with st.expander("Zoom to a specific window"):
    use_zoom = st.checkbox("Apply custom zoom", value=False)
    zoom_start, zoom_end = earliest_date, latest_date
    if use_zoom:
        zc1, zc2 = st.columns(2)
        zoom_start = pd.Timestamp(zc1.date_input("From", value=earliest_date.date(), key="zoom_start"))
        zoom_end = pd.Timestamp(zc2.date_input("To", value=latest_date.date(), key="zoom_end"))
        if zoom_start > zoom_end:
            zoom_start, zoom_end = zoom_end, zoom_start
            st.info("Start and end were swapped to keep a valid range.")

df = df_all

def build_chart(categories_to_plot):
    fig = go.Figure()
    for cat in categories_to_plot:
        meta = CATEGORY_META[cat]
        key = meta["key"]
        for ptype in selected_price_types:
            pmeta = PRICE_TYPE_META[ptype]
            col_name = f"{key}_{pmeta['field']}"
            if col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df[col_name] * multiplier,
                    name=f"{meta['short']} · {ptype.split(' ')[0]}",
                    line=dict(color=meta["color"], dash=pmeta["dash"], width=2.2),
                    connectgaps=True,
                ))
    fig.update_layout(
        paper_bgcolor="#16130F", plot_bgcolor="#1D1811",
        font=dict(color="#E8DFC8", family="Inter, sans-serif"),
        showlegend=False,
        xaxis=dict(title="Date", gridcolor="#2C251C", linecolor="#2C251C"),
        yaxis=dict(
            title=f"Price ({unit_label})", type="log",
            dtick=1,
            gridcolor="#2C251C",
        ),
        hovermode="x unified",
        height=420,
        margin=dict(t=20, b=40, l=50, r=10),
    )
    if use_zoom:
        fig.update_xaxes(range=[zoom_start, zoom_end])
    return fig

tab1, tab2, tab3, tab4 = st.tabs(["All", "Inteira", "Graínha", "Triturado"])
with tab1:
    st.plotly_chart(build_chart(selected_cats_for_chart), use_container_width=True, key="all")
with tab2:
    st.plotly_chart(build_chart(["Alfarroba Inteira"]), use_container_width=True, key="inteira")
with tab3:
    st.plotly_chart(build_chart(["Alfarroba Graínha"]), use_container_width=True, key="grainha")
with tab4:
    st.plotly_chart(build_chart(["Alfarroba Triturado Grosso"]), use_container_width=True, key="triturado")

# ============================================================
# 13. RAW DATA
# ============================================================
with st.expander("Raw data"):
    table_df = df_all.copy()
    num_cols = [c for c in table_df.columns if c != "date"]
    if multiplier != 1.0:
        for col in num_cols:
            table_df[col] = table_df[col] * multiplier
    table_df["date"] = table_df["date"].dt.strftime("%d/%m/%Y")
    st.dataframe(table_df[["date"] + num_cols].sort_values("date", ascending=False),
                 use_container_width=True)

# ============================================================
# 14. FOOTER
# ============================================================
st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
st.markdown("""
<div style="font-size: 0.8rem; color: var(--text-dim); line-height: 1.6;">
<strong>Data source:</strong> GPP / SIMA (regsima.gpp.pt), Portugal's public agricultural market
information system. Independently collected and processed; not affiliated with or endorsed by
GPP or IPMA.<br>
<strong>Code license:</strong> PolyForm Noncommercial 1.0.0 — free for personal, research, and
noncommercial use. Commercial use requires permission.<br>
<strong>Disclaimer:</strong> figures shown are informational and may not reflect the exact price
achievable in any individual transaction. Verify independently before relying on them.
</div>
""", unsafe_allow_html=True)
