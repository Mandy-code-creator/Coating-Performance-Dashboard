import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("🤖 AI QE System – 塗料製程診斷平台")

# =========================
# LOAD DATA
# =========================
file = st.sidebar.file_uploader("Upload CSV/Excel", type=["csv","xlsx"])

@st.cache_data
def load_data(file):
    if file.name.endswith("csv"):
        df = pd.read_csv(file, encoding='utf-8-sig')
    else:
        df = pd.read_excel(file)

    df.columns = df.columns.str.strip()

    num_cols = [c for c in df.columns if '耗用' in c or '績效' in c]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(',',''), errors='coerce')

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
    # FILTER
    # =========================
    sel_month = st.sidebar.multiselect("年月", df['年月'].unique(), df['年月'].unique())
    df = df[df['年月'].isin(sel_month)]

    # =========================
    # AGG
    # =========================
    agg = df.groupby('塗料編號').agg({
        '績效%':'mean',
        '超耗':'sum',
        '合計理論耗用':'sum',
        '線別':'first',
        '用途':'first'
    }).reset_index()

    # =========================
    # 🔍 AI MODULE 1: ANOMALY DETECTION
    # =========================
    st.markdown("## 🚨 AI Detection (Anomaly)")

    Q1 = agg['績效%'].quantile(0.25)
    Q3 = agg['績效%'].quantile(0.75)
    IQR = Q3 - Q1

    lower = Q1 - 1.5 * IQR

    agg['異常'] = agg['績效%'] < lower

    anomaly_df = agg[agg['異常'] == True]

    st.metric("異常塗料數", len(anomaly_df))

    st.dataframe(anomaly_df.sort_values("績效%"))

    # =========================
    # 📊 VISUAL ANOMALY
    # =========================
    fig1 = px.scatter(
        agg,
        x='合計理論耗用',
        y='績效%',
        color='異常',
        size='超耗',
        hover_data=['塗料編號','線別','用途']
    )

    fig1.add_hline(y=lower, line_dash="dash", line_color="red")

    st.plotly_chart(fig1, use_container_width=True)

    # =========================
    # 🔍 AI MODULE 2: ROOT CAUSE RANKING
    # =========================
    st.markdown("## 🧠 AI Diagnosis")

    # Supplier impact
    supplier_impact = df.groupby('油漆廠商')['績效%'].mean().sort_values()

    # Line impact
    line_impact = df.groupby('線別')['績效%'].mean().sort_values()

    col1,col2 = st.columns(2)

    with col1:
        st.subheader("供應商影響排名")
        st.dataframe(supplier_impact)

    with col2:
        st.subheader("線別影響排名")
        st.dataframe(line_impact)

    # =========================
    # 🔮 AI MODULE 3: TREND PREDICTION
    # =========================
    st.markdown("## 🔮 AI Prediction")

    trend = df.groupby('年月')['績效%'].mean().reset_index()

    # simple moving average
    trend['預測'] = trend['績效%'].rolling(3).mean()

    fig2 = px.line(trend, x='年月', y=['績效%','預測'], markers=True)

    st.plotly_chart(fig2, use_container_width=True)

    # =========================
    # 🔥 HEATMAP
    # =========================
    st.markdown("## 🔥 Heatmap")

    heat = df.pivot_table(
        index='線別',
        columns='用途',
        values='績效%',
        aggfunc='mean'
    )

    fig3 = px.imshow(heat, color_continuous_scale='RdYlGn')
    st.plotly_chart(fig3, use_container_width=True)

    # =========================
    # 📋 ACTION LIST (AI)
    # =========================
    st.markdown("## 🎯 AI Action Recommendation")

    action = anomaly_df.sort_values("超耗", ascending=False).head(10)

    st.dataframe(action[['塗料編號','績效%','超耗','線別','用途']])

else:
    st.info("Upload data to start AI system")
