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
@media (max-width: 768px) {
    .block-container { padding: 1rem 0.75rem !important; }
    [data-testid="stTabs"] > div:first-child {
        overflow-x: auto !important;
        white-space: nowrap !important;
    }
    h1 { font-size: 1.4rem !important; }
    h3 { font-size: 1.1rem !important; }
}
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

def build_chart(categories_to_plot):
    fig = go.Figure()
    for cat in categories_to_plot:
        for ptype in selected_price_types:
            col_name = field_map.get((cat, ptype))
            if col_name and col_name in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["date"],
                    y=df[col_name] * multiplier,
                    name=f"{cat} - {ptype}",
                    line=dict(color=cat_colors[cat], dash=line_styles[ptype], width=2.2),
                    connectgaps=True,
                ))
    fig.update_layout(
    title=dict(
        text=f"Price History ({min_date.strftime('%Y')} - {max_date.strftime('%Y')})",
        y=0.98,
        x=0,
        xanchor="left",
        yanchor="top",
    ),
    xaxis_title="Date",
    yaxis=dict(
        title=f"Price ({unit_label})",
        type="log",
    ),
    hovermode="x unified",
    template="plotly_white",
    height=420,
    margin=dict(t=140, b=40, l=50, r=10),
    legend=dict(
        orientation="h",
        yanchor="top",
        y=0.91,
        xanchor="left",
        x=0,
        font=dict(size=11),
    ),
)
    return fig

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 All", "🟠 Inteira", "🔵 Graínha", "🟢 Triturado"]
)
with tab1:
    st.plotly_chart(build_chart(selected_cats), use_container_width=True, key="all")
with tab2:
    st.plotly_chart(build_chart(["Alfarroba Inteira"]), use_container_width=True, key="inteira")
with tab3:
    st.plotly_chart(build_chart(["Alfarroba Graínha"]), use_container_width=True, key="grainha")
with tab4:
    st.plotly_chart(build_chart(["Alfarroba Triturado Grosso"]), use_container_width=True, key="triturado")

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
