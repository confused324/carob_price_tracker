# app.py
import os
import io
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

MASTER_FILE = "sima_master.csv"
SIMA_EXPORT_URL = "https://sima.pt/sima/export"  # SIMA data endpoint


# --- 2. AUTOMATED DATA FETCHING & MERGING ---
def fetch_latest_sima_data():
    """
    Attempts to download the latest raw carob export directly from SIMA.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(SIMA_EXPORT_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                df = pd.read_csv(io.StringIO(response.text), sep=";", encoding="latin1")
            except Exception:
                df = pd.read_csv(io.StringIO(response.text), encoding="utf-8-sig")
            return df
    except Exception as e:
        st.warning(f"Could not auto-fetch online data from SIMA: {e}")
    return pd.DataFrame()


def sync_and_get_master_data():
    """
    Loads local master file and merges any newly fetched rows seamlessly.
    """
    # 1. Load existing local file if available
    local_df = pd.DataFrame()
    if os.path.exists(MASTER_FILE):
        try:
            local_df = pd.read_csv(MASTER_FILE, sep=";", encoding="utf-8-sig")
        except Exception:
            pass

    # Fall back to any initial SIMA file in folder
    if local_df.empty:
        for f in os.listdir("."):
            if f.endswith((".csv", ".xlsx", ".xls")) and "sima" in f.lower():
                try:
                    if f.endswith(".csv"):
                        local_df = pd.read_csv(f, sep=";", encoding="latin1")
                    else:
                        local_df = pd.read_excel(f)
                    break
                except Exception:
                    continue

    # 2. Try fetching fresh online data
    online_df = fetch_latest_sima_data()

    # 3. Merge online data with local data if available
    if not online_df.empty:
        if not local_df.empty:
            combined = pd.concat([local_df, online_df], ignore_index=True)
            # Remove exact duplicates across key columns
            dedup_cols = [c for c in ["Produto", "Data", "Mercado"] if c in combined.columns]
            if dedup_cols:
                combined = combined.drop_duplicates(subset=dedup_cols, keep="last")
            local_df = combined
        else:
            local_df = online_df

    # 4. Save persistent master copy to disk
    if not local_df.empty:
        local_df.to_csv(MASTER_FILE, sep=";", index=False, encoding="utf-8-sig")

    return local_df


# --- 3. DATA PROCESSING ENGINE ---
@st.cache_data(ttl=300)
def process_data(df_raw):
    if df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = ["Produto", "Data", "Mínima", "Máxima", "Freq"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        return pd.DataFrame()

    # Parse Dates (DD/MM/YYYY)
    df["date"] = pd.to_datetime(df["Data"], format="%d/%m/%Y", errors="coerce")
    if df["date"].isna().all():
        df["date"] = pd.to_datetime(
            df["Data"], dayfirst=True, format="mixed", errors="coerce"
        )
    df = df.dropna(subset=["date"])

    # Clean numeric fields
    price_fields = ["Mínima", "Máxima", "Freq"]
    for p in price_fields:
        if df[p].dtype == object:
            df[p] = df[p].astype(str).str.replace(",", ".").str.strip()
        df[p] = pd.to_numeric(df[p], errors="coerce")
        df[p] = df[p].replace(0, pd.NA)

    # Categorize from Produto
    def categorize_produto(val):
        v = str(val).lower()
        if "grainha" in v or "graínha" in v or "semente" in v:
            return "grainha"
        elif "triturado" in v or "bagaço" in v:
            return "triturado"
        return "inteira"

    df["specie_key"] = df["Produto"].apply(categorize_produto)

    # Aggregate & Pivot
    grouped = (
        df.groupby(["date", "specie_key"])[price_fields].mean().reset_index()
    )
    pivoted = grouped.pivot(
        index="date", columns="specie_key", values=["Freq", "Mínima", "Máxima"]
    )
    pivoted.columns = [f"{col[1]}_{col[0].lower()}" for col in pivoted.columns]

    rename_map = {
        "inteira_mínima": "inteira_min",
        "inteira_máxima": "inteira_max",
        "grainha_mínima": "grainha_min",
        "grainha_máxima": "grainha_max",
        "triturado_mínima": "triturado_min",
        "triturado_máxima": "triturado_max",
    }
    pivoted = pivoted.rename(columns=rename_map)

    for c in [
        "inteira_freq", "inteira_min", "inteira_max",
        "grainha_freq", "grainha_min", "grainha_max",
        "triturado_freq", "triturado_min", "triturado_max",
    ]:
        if c not in pivoted.columns:
            pivoted[c] = pd.NA

    final_df = pivoted.reset_index().sort_values(by="date", ascending=True).reset_index(drop=True)
    val_cols = [c for c in final_df.columns if c != "date"]
    final_df[val_cols] = final_df[val_cols].ffill()

    return final_df


# --- 4. HEADER & INTERFACE ---
st.title("🌿 Algarve Carob Exact Market Prices")

raw_sima_data = sync_and_get_master_data()
df_all = process_data(raw_sima_data)

if df_all.empty:
    st.warning("No SIMA data found! Please place your initial SIMA export file in this folder.")
    st.stop()

last_date = df_all["date"].max().strftime("%Y-%m-%d")

# --- 5. SIDEBAR FILTERS & MANUAL SYNC BUTTON ---
st.sidebar.header("⚙️ Data Filters")

if st.sidebar.button("🔄 Sync Latest SIMA Quotes"):
    st.cache_data.clear()
    raw_sima_data = sync_and_get_master_data()
    df_all = process_data(raw_sima_data)
    st.sidebar.success("Database synchronized!")

time_range = st.sidebar.radio(
    "Select Range:",
    ["All Time", "5 Years", "1 Year", "6 Months"],
    index=0,
)

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
multiplier = 15.0 if unit_mode == "EUR / arroba (15 kg)" else 1.0
unit_label = "€/@" if unit_mode == "EUR / arroba (15 kg)" else "€/kg"

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

st.caption(f"🟢 Database Status: Synced (`sima_master.csv`) | Latest Entry: {last_date}")

# --- 6. METRIC CARDS ---
st.markdown("### 📍 Current SIMA Quotes")
latest = df_all.iloc[-1]

def fmt(val):
    return f"{val * multiplier:.2f} {unit_label}" if pd.notna(val) else "N/A"

cols = st.columns(3)
with cols[0]:
    st.markdown("#### Alfarroba Inteira")
    st.write(f"• **Freq:** {fmt(latest.get('inteira_freq'))}")
    st.write(f"• **Min:** {fmt(latest.get('inteira_min'))}")
    st.write(f"• **Max:** {fmt(latest.get('inteira_max'))}")

with cols[1]:
    st.markdown("#### Alfarroba Graínha")
    st.write(f"• **Freq:** {fmt(latest.get('grainha_freq'))}")
    st.write(f"• **Min:** {fmt(latest.get('grainha_min'))}")
    st.write(f"• **Max:** {fmt(latest.get('grainha_max'))}")

with cols[2]:
    st.markdown("#### Alfarroba Triturado Grosso")
    st.write(f"• **Freq:** {fmt(latest.get('triturado_freq'))}")
    st.write(f"• **Min:** {fmt(latest.get('triturado_min'))}")
    st.write(f"• **Max:** {fmt(latest.get('triturado_max'))}")

st.divider()

# --- 7. GRAPH HELPER ---
line_styles = {
    "Mais Frequente (Freq)": "solid",
    "Mínimo (Min)": "dash",
    "Máximo (Max)": "dot",
}
cat_colors = {
    "Alfarroba Inteira": "#D97706",
    "Alfarroba Graínha": "#2563EB",
    "Alfarroba Triturado Grosso": "#059669",
}
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

def build_chart(categories_to_plot):
    fig = go.Figure()
    for cat in categories_to_plot:
        for ptype in selected_price_types:
            col_name = field_map.get((cat, ptype))
            if col_name and col_name in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df[col_name] * multiplier,
                        name=f"{cat} - {ptype}",
                        line=dict(color=cat_colors[cat], dash=line_styles[ptype], width=2.2),
                        connectgaps=True,
                    )
                )
    fig.update_layout(
        title=f"Price History ({min_date.strftime('%Y')} - {max_date.strftime('%Y')})",
        xaxis_title="Date",
        yaxis_title=f"Price ({unit_label})",
        hovermode="x unified",
        template="plotly_white",
        height=550,
    )
    return fig

# --- 8. CATEGORY TABS ---
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 All Categories", "🟠 Alfarroba Inteira", "🔵 Alfarroba Graínha", "🟢 Triturado Grosso"]
)

with tab1:
    st.plotly_chart(build_chart(selected_cats), use_container_width=True, key="chart_tab_all")

with tab2:
    st.plotly_chart(build_chart(["Alfarroba Inteira"]), use_container_width=True, key="chart_tab_inteira")

with tab3:
    st.plotly_chart(build_chart(["Alfarroba Graínha"]), use_container_width=True, key="chart_tab_grainha")

with tab4:
    st.plotly_chart(build_chart(["Alfarroba Triturado Grosso"]), use_container_width=True, key="chart_tab_triturado")

# --- 9. RAW DATA TABLE VIEW ---
with st.expander("📋 View Processed Data Table"):
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