import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")
st.title("📊 塗料生產績效分析 (QE Decision Dashboard)")

# =========================
# DATA LOAD
# =========================
file = st.sidebar.file_uploader("Upload file", type=["csv","xlsx"])

@st.cache_data
def load_data(file):
    if file.name.endswith("csv"):
        df = pd.read_csv(file, encoding='utf-8-sig')
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    num_cols = [c for c in df.columns if "耗用" in c or "績效" in c]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',',''), errors='coerce')

    # KPI FIX
    df['績效%'] = np.where(
        df['合計實際耗用'] > 0,
        df['合計理論耗用'] / df['合計實際耗用'] * 100,
        np.nan
    )

    df['超耗'] = df['合計實際耗用'] - df['合計理論耗用']

    return df

if file:

    df = load_data(file)

    # =========================
    # FILTER FLOW (RẤT QUAN TRỌNG)
    # =========================
    st.sidebar.header("Filter")

    sel_month = st.sidebar.multiselect("年月", sorted(df['年月'].unique()), default=df['年月'].unique())
    df1 = df[df['年月'].isin(sel_month)]

    sel_usage = st.sidebar.multiselect("用途", sorted(df1['用途'].unique()), default=df1['用途'].unique())
    df2 = df1[df1['用途'].isin(sel_usage)]

    sel_paint = st.sidebar.multiselect("塗料編號", sorted(df2['塗料編號'].unique()), default=df2['塗料編號'].unique())
    df3 = df2[df2['塗料編號'].isin(sel_paint)]

    sel_line = st.sidebar.multiselect("線別", sorted(df3['線別'].unique()), default=df3['線別'].unique())
    filtered = df3[df3['線別'].isin(sel_line)]

    # =========================
    # KPI
    # =========================
    st.markdown("## 🎯 KPI")

    c1, c2, c3 = st.columns(3)

    c1.metric("平均績效%", f"{filtered['績效%'].mean():.2f}")
    c2.metric("總超耗", f"{filtered['超耗'].sum():,.0f}")
    c3.metric("塗料數", filtered['塗料編號'].nunique())

    # =========================
    # 1️⃣ OVERVIEW (用途)
    # =========================
    st.markdown("## 🧭 用途別表現")

    usage_perf = filtered.groupby("用途")['績效%'].mean().reset_index()

    fig1 = px.bar(
        usage_perf,
        x="用途",
        y="績效%",
        color="績效%",
        color_continuous_scale="RdYlGn"
    )

    fig1.add_hline(y=100, line_dash="dash")

    st.plotly_chart(fig1, use_container_width=True)

    # =========================
    # 2️⃣ TOP PROBLEM (核心)
    # =========================
    st.markdown("## 🚨 Top Problem Paint")

    top = filtered.groupby("塗料編號").agg({
        "超耗":"sum",
        "績效%":"mean"
    }).reset_index()

    top = top.sort_values("超耗", ascending=False).head(15)

    st.dataframe(top)

    # =========================
    # 3️⃣ SCATTER (FOCUS)
    # =========================
    st.markdown("## 🎯 問題塗料分佈")

    fig2 = px.scatter(
        top,
        x="塗料編號",
        y="績效%",
        size="超耗",
        color="績效%",
        color_continuous_scale="RdYlGn"
    )

    fig2.add_hline(y=100, line_dash="dash")

    st.plotly_chart(fig2, use_container_width=True)

    # =========================
    # 4️⃣ ROOT CAUSE (SUPPLIER)
    # =========================
    st.markdown("## 🏭 供應商影響")

    fig3 = px.box(
        filtered,
        x="油漆廠商",
        y="績效%",
        points="outliers"
    )

    fig3.add_hline(y=100, line_dash="dash")

    st.plotly_chart(fig3, use_container_width=True)

    # =========================
    # 5️⃣ ROOT CAUSE (SHIFT)
    # =========================
    st.markdown("## 👷 班別影響")

    shift_cols = [c for c in df.columns if "班績效%" in c]

    if shift_cols:
        shift_df = pd.melt(
            filtered,
            id_vars=['塗料編號'],
            value_vars=shift_cols,
            var_name='班別',
            value_name='績效%'
        ).dropna()

        fig4 = px.box(
            shift_df,
            x="班別",
            y="績效%",
            points="outliers"
        )

        fig4.add_hline(y=100, line_dash="dash")

        st.plotly_chart(fig4, use_container_width=True)

    # =========================
    # 6️⃣ TREND (CỰC QUAN TRỌNG)
    # =========================
    st.markdown("## 📈 Trend")

    trend = filtered.groupby("年月")['績效%'].mean().reset_index()

    fig5 = px.line(trend, x="年月", y="績效%", markers=True)

    fig5.add_hline(y=100, line_dash="dash")

    st.plotly_chart(fig5, use_container_width=True)

    # =========================
    # RAW
    # =========================
    with st.expander("Raw Data"):
        st.dataframe(filtered)

else:
    st.info("Upload file to start")
