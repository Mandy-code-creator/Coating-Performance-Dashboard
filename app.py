import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("🤖 AI QE System – 塗料製程診斷平台 (Stable Version)")

# =========================
# LOAD DATA
# =========================
file = st.sidebar.file_uploader("Upload CSV / Excel", type=["csv", "xlsx"])

@st.cache_data
def load_data(file):
    if file.name.endswith("csv"):
        df = pd.read_csv(file, encoding="utf-8-sig")
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    # numeric convert safe
    num_cols = [c for c in df.columns if "耗用" in c or "績效" in c]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")

    # KPI
    df["績效%"] = np.where(
        df.get("合計實際耗用", 0) > 0,
        df.get("合計理論耗用", 0) / df.get("合計實際耗用", 1) * 100,
        np.nan
    )

    df["超耗"] = df.get("合計實際耗用", 0) - df.get("合計理論耗用", 0)

    return df


if file:

    df = load_data(file)

    # =========================
    # FILTER SAFE
    # =========================
    st.sidebar.header("Filter")

    def safe_multiselect(col):
        if col in df.columns:
            return st.sidebar.multiselect(col, df[col].dropna().unique(), df[col].dropna().unique())
        return None

    if "年月" in df.columns:
        sel_month = safe_multiselect("年月")
        if sel_month:
            df = df[df["年月"].isin(sel_month)]

    if "線別" in df.columns:
        sel_line = safe_multiselect("線別")
        if sel_line:
            df = df[df["線別"].isin(sel_line)]

    if "用途" in df.columns:
        sel_usage = safe_multiselect("用途")
        if sel_usage:
            df = df[df["用途"].isin(sel_usage)]

    # =========================
    # FOCUS MODE
    # =========================
    focus = st.sidebar.toggle("只看異常 (<95%)")
    if focus:
        df = df[df["績效%"] < 95]

    # =========================
    # AGG SAFE
    # =========================
    agg = df.groupby("塗料編號", dropna=False).agg({
        "績效%": "mean",
        "超耗": "sum",
        "合計理論耗用": "sum",
        "線別": "first",
        "用途": "first"
    }).reset_index()

    # clean
    agg = agg.replace([np.inf, -np.inf], np.nan)
    agg = agg.dropna(subset=["績效%", "合計理論耗用"])

    agg["超耗"] = agg["超耗"].fillna(0)
    agg["size"] = agg["超耗"].clip(lower=0) + 1

    # =========================
    # AI DETECTION (IQR)
    # =========================
    Q1 = agg["績效%"].quantile(0.25)
    Q3 = agg["績效%"].quantile(0.75)
    IQR = Q3 - Q1
    lower = Q1 - 1.5 * IQR

    agg["異常"] = agg["績效%"] < lower
    agg["異常"] = agg["異常"].fillna(False)

    # =========================
    # KPI
    # =========================
    st.markdown("## 🎯 KPI")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("平均績效%", f"{agg['績效%'].mean():.2f}")
    c2.metric("總超耗", f"{agg['超耗'].sum():,.0f}")
    c3.metric("塗料數", agg["塗料編號"].nunique())
    c4.metric("異常數", int(agg["異常"].sum()))

    # =========================
    # SCATTER (SAFE)
    # =========================
    st.markdown("## 🎯 AI Scatter")

    try:
        fig1 = px.scatter(
            agg,
            x="合計理論耗用",
            y="績效%",
            size="size",
            color=agg["異常"].astype(str),
            hover_data=["塗料編號"]
        )

        fig1.add_hline(y=100, line_dash="dash")
        fig1.add_hline(y=lower, line_dash="dash", line_color="red")

        st.plotly_chart(fig1, use_container_width=True)

    except Exception as e:
        st.warning("Scatter error")
        st.write(agg.head())

    # =========================
    # PARETO
    # =========================
    st.markdown("## 🚨 Pareto")

    pareto = agg[agg["超耗"] > 0].sort_values("超耗", ascending=False)

    if not pareto.empty:
        pareto["累積%"] = pareto["超耗"].cumsum() / pareto["超耗"].sum() * 100

        fig2 = go.Figure()
        fig2.add_bar(x=pareto["塗料編號"], y=pareto["超耗"])
        fig2.add_scatter(x=pareto["塗料編號"], y=pareto["累積%"], yaxis="y2")

        fig2.update_layout(yaxis2=dict(overlaying="y", side="right"))
        st.plotly_chart(fig2, use_container_width=True)

    else:
        st.info("無超耗")

    # =========================
    # HEATMAP SAFE
    # =========================
    st.markdown("## 🔥 Heatmap")

    try:
        if "線別" in df.columns and "用途" in df.columns:
            heat = df.pivot_table(
                index="線別",
                columns="用途",
                values="績效%",
                aggfunc="mean"
            )

            if not heat.empty:
                fig3 = px.imshow(heat, color_continuous_scale="RdYlGn")
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Heatmap 無資料")

    except:
        st.warning("Heatmap error")

    # =========================
    # ROOT CAUSE
    # =========================
    st.markdown("## 🧠 Root Cause")

    col1, col2 = st.columns(2)

    with col1:
        if "油漆廠商" in df.columns:
            fig4 = px.box(df, x="油漆廠商", y="績效%", points="outliers")
            fig4.add_hline(y=100, line_dash="dash")
            st.plotly_chart(fig4, use_container_width=True)

    with col2:
        # =========================
        # SHIFT SAFE FIX (IMPORTANT)
        # =========================
        shift_cols = [c for c in df.columns if "班績效%" in c]
        shift_cols = [c for c in shift_cols if c in df.columns]

        if len(shift_cols) > 0:

            shift_df = pd.melt(
                df,
                id_vars=["塗料編號"],
                value_vars=shift_cols,
                var_name="班別",
                value_name="績效%"
            )

            shift_df = shift_df.dropna(subset=["績效%"])

            if not shift_df.empty:
                shift_df["班別"] = shift_df["班別"].str.replace("班績效%", "班")

                fig5 = px.box(shift_df, x="班別", y="績效%", points="outliers")
                fig5.add_hline(y=100, line_dash="dash")

                st.plotly_chart(fig5, use_container_width=True)

            else:
                st.info("班別資料為空")

        else:
            st.info("無班別欄位")

    # =========================
    # ACTION LIST
    # =========================
    st.markdown("## 🎯 AI Action List")

    action = agg[agg["異常"]].sort_values("超耗", ascending=False).head(20)

    st.dataframe(action)

else:
    st.info("👈 Upload file to start")
