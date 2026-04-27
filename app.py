import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("🤖 AI QE System – Stable Production Version")

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

    return df


if file:

    df = load_data(file)

    # =========================
    # SAFE NUMERIC CONVERT
    # =========================
    def to_num(df, cols):
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
        return df

    df = to_num(df, ["合計理論耗用", "合計實際耗用", "績效%"])

    # KPI SAFE CALC
    if "合計理論耗用" in df.columns and "合計實際耗用" in df.columns:
        df["績效%"] = np.where(
            df["合計實際耗用"] > 0,
            df["合計理論耗用"] / df["合計實際耗用"] * 100,
            np.nan
        )
        df["超耗"] = df["合計實際耗用"] - df["合計理論耗用"]
    else:
        df["績效%"] = np.nan
        df["超耗"] = 0

    # =========================
    # FILTER SAFE
    # =========================
    st.sidebar.header("Filter")

    def safe_filter(col):
        if col in df.columns:
            vals = df[col].dropna().unique()
            sel = st.sidebar.multiselect(col, vals, vals)
            return df[df[col].isin(sel)]
        return df

    df = safe_filter("年月")
    df = safe_filter("線別")
    df = safe_filter("用途")

    # =========================
    # FOCUS MODE
    # =========================
    focus = st.sidebar.toggle("只看異常 (<95%)")
    if focus and "績效%" in df.columns:
        df = df[df["績效%"] < 95]

    # =========================
    # AGG SAFE
    # =========================
    if "塗料編號" not in df.columns:
        st.error("缺少 塗料編號 欄位")
        st.stop()

    agg = df.groupby("塗料編號").agg({
        "績效%": "mean",
        "超耗": "sum",
        "合計理論耗用": "sum" if "合計理論耗用" in df.columns else "count",
        "線別": "first" if "線別" in df.columns else "first",
        "用途": "first" if "用途" in df.columns else "first"
    }).reset_index()

    agg = agg.replace([np.inf, -np.inf], np.nan).dropna(subset=["績效%"])

    agg["超耗"] = agg["超耗"].fillna(0)
    agg["size"] = agg["超耗"].clip(lower=0) + 1

    # =========================
    # AI ANOMALY (IQR)
    # =========================
    q1 = agg["績效%"].quantile(0.25)
    q3 = agg["績效%"].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr

    agg["異常"] = agg["績效%"] < lower
    agg["異常"] = agg["異常"].fillna(False)

    # =========================
    # KPI
    # =========================
    st.markdown("## 🎯 KPI")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("平均績效%", f"{agg['績效%'].mean():.2f}")
    c2.metric("總超耗", f"{agg['超耗'].sum():,.0f}")
    c3.metric("塗料數", len(agg))
    c4.metric("異常數", int(agg["異常"].sum()))

    # =========================
    # SAFE SCATTER
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

    except:
        st.warning("Scatter error")

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
        st.info("無超耗數據")

    # =========================
    # HEATMAP SAFE
    # =========================
    st.markdown("## 🔥 Heatmap")

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

    # =========================
    # SHIFT SAFE (FIXED MELT)
    # =========================
    st.markdown("## 👷 Shift Analysis")

    shift_cols = [c for c in df.columns if "班績效%" in c]

    # only valid columns
    shift_cols = [c for c in shift_cols if c in df.columns]

    if len(shift_cols) > 0:

        df[shift_cols] = df[shift_cols].apply(pd.to_numeric, errors="coerce")

        shift_df = pd.melt(
            df,
            id_vars=["塗料編號"],
            value_vars=shift_cols,
            var_name="班別",
            value_name="績效"
        )

        shift_df = shift_df.dropna(subset=["績效"])

        if not shift_df.empty:

            shift_df["班別"] = shift_df["班別"].astype(str).str.replace("班績效%", "班")

            fig4 = px.box(
                shift_df,
                x="班別",
                y="績效",
                points="outliers"
            )

            fig4.add_hline(y=100, line_dash="dash")

            st.plotly_chart(fig4, use_container_width=True)

    else:
        st.info("無班別資料")

    # =========================
    # ACTION LIST
    # =========================
    st.markdown("## 🎯 AI Action List")

    st.dataframe(
        agg[agg["異常"]].sort_values("超耗", ascending=False).head(20)
    )

else:
    st.info("Upload file to start")
