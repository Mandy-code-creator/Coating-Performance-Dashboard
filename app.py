import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.markdown("""
<style>
.stPlotlyChart {
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    background-color: white;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 塗料生產績效分析儀表板 (Refactored)")
st.markdown("Decision-driven dashboard | QE / Production Analytics")

# ==========================================
# CACHE DATA PREPROCESS
# ==========================================
@st.cache_data
def preprocess(df):
    df.columns = df.columns.str.strip()
    df = df.dropna(how='all')

    # clean string cols
    cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().fillna("未定義")

    # numeric clean
    num_cols = [c for c in df.columns if any(k in c for k in ['耗用', '績效'])]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', ''), errors='coerce')

    # KPI FIXED
    df['合計績效%'] = np.where(
        (df['合計實際耗用'] > 0),
        (df['合計理論耗用'] / df['合計實際耗用']) * 100,
        np.nan
    )

    # deviation FIXED
    df['超耗量'] = df['合計實際耗用'] - df['合計理論耗用']

    # grouping
    df['Sort_Group'] = df['塗料編號'].apply(
        lambda x: 'GE00_01_Group' if 'GE00' in str(x) or 'GE01' in str(x) else str(x)
    )

    # performance level
    df['績效等級'] = np.select(
        [
            df['合計績效%'] < 85,
            (df['合計績效%'] >= 85) & (df['合計績效%'] < 95),
            (df['合計績效%'] >= 95) & (df['合計績效%'] < 100),
            df['合計績效%'] >= 100
        ],
        ['🔴 <85%', '🟡 85-95%', '🔵 95-100%', '🟢 ≥100%'],
        default='未知'
    )

    return df


# ==========================================
# LOAD DATA
# ==========================================
st.sidebar.header("📂 Data Upload")
uploaded_file = st.sidebar.file_uploader("Upload CSV / Excel", type=['csv', 'xlsx'])

if uploaded_file:

    if uploaded_file.name.endswith("csv"):
        df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
    else:
        df = pd.read_excel(uploaded_file)

    df = preprocess(df)

    # ==========================================
    # FILTER
    # ==========================================
    st.sidebar.header("🔍 Filters")

    sel_month = st.sidebar.multiselect("年月", df['年月'].unique(), default=df['年月'].unique())
    df1 = df[df['年月'].isin(sel_month)]

    sel_line = st.sidebar.multiselect("線別", df1['線別'].unique(), default=df1['線別'].unique())
    df2 = df1[df1['線別'].isin(sel_line)]

    sel_use = st.sidebar.multiselect("用途", df2['用途'].unique(), default=df2['用途'].unique())
    filtered = df2[df2['用途'].isin(sel_use)]

    # ==========================================
    # KPI LAYER (DECISION)
    # ==========================================
    st.markdown("## 🎯 Executive KPI")

    c1, c2, c3 = st.columns(3)

    c1.metric("平均績效%", f"{filtered['合計績效%'].mean():.2f}")
    c2.metric("總超耗量", f"{filtered['超耗量'].sum():,.0f}")
    c3.metric("塗料數", f"{filtered['塗料編號'].nunique()}")

    # ==========================================
    # TOP ISSUE TABLE (MOST IMPORTANT)
    # ==========================================
    st.markdown("## 🚨 Top Issue (Action List)")

    top_issue = filtered.sort_values("超耗量", ascending=False).head(10)

    st.dataframe(
        top_issue[[
            "塗料編號",
            "用途",
            "合計績效%",
            "超耗量"
        ]]
    )

    st.divider()

    # ==========================================
    # PARETO
    # ==========================================
    st.markdown("## 📊 Pareto Analysis")

    pareto = filtered.groupby("塗料編號")["超耗量"].sum().reset_index()
    pareto = pareto.sort_values("超耗量", ascending=False)

    pareto["累積%"] = pareto["超耗量"].cumsum() / pareto["超耗量"].sum() * 100

    fig = go.Figure()

    fig.add_bar(x=pareto["塗料編號"], y=pareto["超耗量"], name="超耗量")
    fig.add_scatter(
        x=pareto["塗料編號"],
        y=pareto["累積%"],
        name="累積%",
        yaxis="y2",
        mode="lines+markers"
    )

    fig.add_hline(y=80, line_dash="dash")

    fig.update_layout(
        yaxis=dict(title="超耗量"),
        yaxis2=dict(title="累積%", overlaying="y", side="right"),
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # BOX PLOT (SIMPLIFIED)
    # ==========================================
    st.markdown("## 📦 Stability Analysis")

    col1, col2 = st.columns(2)

    with col1:
        fig1 = px.box(
            filtered,
            x="油漆廠商",
            y="合計績效%",
            points="outliers"
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = px.box(
            filtered,
            x="用途",
            y="合計績效%",
            points="outliers"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ==========================================
    # SCATTER (TOP N ONLY)
    # ==========================================
    st.markdown("## 🎯 Performance Scatter")

    top_n = st.slider("Top N", 20, 100, 50)

    scatter_df = filtered.sort_values("合計績效%", ascending=True).head(top_n)

    fig3 = px.scatter(
        scatter_df,
        x="塗料編號",
        y="合計績效%",
        size="合計理論耗用",
        color="績效等級",
        hover_data=["線別", "用途"]
    )

    fig3.add_hline(y=100, line_dash="dash")

    st.plotly_chart(fig3, use_container_width=True)

    # ==========================================
    # RAW DATA
    # ==========================================
    with st.expander("Raw Data"):
        st.dataframe(filtered)

else:
    st.info("⬅ Upload data to start analysis")
