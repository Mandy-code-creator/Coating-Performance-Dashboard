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
}
</style>
""", unsafe_allow_html=True)

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("MES Data | Decision Support Dashboard")

# ==========================================
# LOAD DATA
# ==========================================
st.sidebar.header("📂 Data Load")
file = st.sidebar.file_uploader("Upload CSV / Excel", type=['csv','xlsx'])

if file:

    if file.name.endswith(".csv"):
        df = pd.read_csv(file, encoding='utf-8-sig', dtype=str)
    else:
        df = pd.read_excel(file, dtype=str)

    df.columns = df.columns.str.strip()
    df = df.dropna(how='all')

    # clean category
    cat_cols = ['線別','塗料編號','用途','年月','油漆廠商','顏色','樹脂']
    for c in cat_cols:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().fillna("未定義")

    # numeric
    num_cols = [c for c in df.columns if '耗用' in c or '績效' in c]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',',''), errors='coerce')

    # KPI FIX
    df['合計績效%'] = np.where(
        df['合計實際耗用'] > 0,
        (df['合計理論耗用'] / df['合計實際耗用']) * 100,
        np.nan
    )

    # deviation
    df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']

    # performance level
    df['績效等級'] = np.select(
        [
            df['合計績效%'] < 85,
            (df['合計績效%'] >= 85) & (df['合計績效%'] < 95),
            (df['合計績效%'] >= 95) & (df['合計績效%'] < 100),
            df['合計績效%'] >= 100
        ],
        ['🔴 <85%','🟡 85-95%','🔵 95-100%','🟢 ≥100%'],
        default='未知'
    )

    # ==========================================
    # FILTER (FIXED LOGIC)
    # ==========================================
    st.sidebar.header("🔍 Filters")

    sel_month = st.sidebar.multiselect("1. 年月", df['年月'].unique(), df['年月'].unique())
    df1 = df[df['年月'].isin(sel_month)]

    sel_usage = st.sidebar.multiselect("2. 用途", df1['用途'].unique(), df1['用途'].unique())
    df2 = df1[df1['用途'].isin(sel_usage)]

    sel_paint = st.sidebar.multiselect("3. 塗料編號", df2['塗料編號'].unique(), df2['塗料編號'].unique())
    df3 = df2[df2['塗料編號'].isin(sel_paint)]

    sel_line = st.sidebar.multiselect("4. 線別", df3['線別'].unique(), df3['線別'].unique())
    filtered_df = df3[df3['線別'].isin(sel_line)]

    # ==========================================
    # KPI
    # ==========================================
    st.markdown("## 🎯 KPI")

    k1, k2, k3 = st.columns(3)

    k1.metric("平均績效%", f"{filtered_df['合計績效%'].mean():.2f}")
    k2.metric("總超耗量", f"{filtered_df['Δ耗用 (Deviation)'].sum():,.0f}")
    k3.metric("塗料數量", filtered_df['塗料編號'].nunique())

    # ==========================================
    # TOP ISSUE (NEW)
    # ==========================================
    st.markdown("## 🚨 Top Issues")

    top_issue = filtered_df.groupby('塗料編號').agg({
        'Δ耗用 (Deviation)': 'sum',
        '合計績效%': 'mean'
    }).reset_index().sort_values('Δ耗用 (Deviation)', ascending=False).head(10)

    st.dataframe(top_issue)

    # ==========================================
    # TABS (GIỮ NGUYÊN)
    # ==========================================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Overview","Pareto","Box","Scatter","Bar"
    ])

    # ---------- OVERVIEW ----------
    with tab1:
        pie_df = filtered_df['績效等級'].value_counts().reset_index()
        pie_df.columns = ['績效等級','數量']

        fig = px.pie(pie_df, values='數量', names='績效等級', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    # ---------- PARETO ----------
    with tab2:
        pareto = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
        pareto = pareto.sort_values('Δ耗用 (Deviation)', ascending=False)

        pareto['累積%'] = pareto['Δ耗用 (Deviation)'].cumsum() / pareto['Δ耗用 (Deviation)'].sum() * 100

        fig = go.Figure()
        fig.add_bar(x=pareto['塗料編號'], y=pareto['Δ耗用 (Deviation)'])
        fig.add_scatter(x=pareto['塗料編號'], y=pareto['累積%'], yaxis='y2')

        fig.add_hline(y=80, line_dash="dash")

        fig.update_layout(
            yaxis2=dict(overlaying='y', side='right')
        )

        st.plotly_chart(fig, use_container_width=True)

    # ---------- BOX ----------
    with tab3:
        fig1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', points="outliers")
        st.plotly_chart(fig1, use_container_width=True)

    # ---------- SCATTER ----------
    with tab4:
        top_n = st.slider("Top N", 20, 100, 50)

        plot_df = filtered_df.sort_values('合計績效%', ascending=True).head(top_n)

        fig = px.scatter(
            plot_df,
            x='塗料編號',
            y='合計績效%',
            size='合計理論耗用',
            color='績效等級'
        )

        fig.add_hline(y=100, line_dash="dash")

        st.plotly_chart(fig, use_container_width=True)

    # ---------- BAR ----------
    with tab5:
        bar_df = filtered_df.groupby('塗料編號')[['合計理論耗用','合計實際耗用']].sum().reset_index()

        fig = go.Figure()
        fig.add_bar(x=bar_df['塗料編號'], y=bar_df['合計理論耗用'], name='理論')
        fig.add_bar(x=bar_df['塗料編號'], y=bar_df['合計實際耗用'], name='實際')

        st.plotly_chart(fig, use_container_width=True)

    # RAW
    with st.expander("Raw Data"):
        st.dataframe(filtered_df)

else:
    st.info("Upload file to start")
