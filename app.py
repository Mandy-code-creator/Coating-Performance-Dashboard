import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="塗料生產績效儀表板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("Power BI-style Cascading Filter Dashboard")

# ==========================================
# DATA UPLOAD
# ==========================================
st.sidebar.header("📂 資料匯入")
uploaded_file = st.sidebar.file_uploader("上傳 CSV / Excel", type=['csv', 'xlsx'])

if uploaded_file is not None:

    # =====================
    # LOAD DATA
    # =====================
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, engine='python', sep=None)
    else:
        df = pd.read_excel(uploaded_file)

    df = df.dropna(subset=['塗料編號'])

    # format 年月
    if '年月' in df.columns:
        df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True)

    # categorical columns
    cat_cols = ['線別', '油漆廠商', '顏色', '樹脂', '用途']
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('未定義').astype(str)

    # numeric conversion
    numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # KPI calc
    if '合計績效%' not in df.columns:
        df['合計績效%'] = np.where(
            df['合計實際耗用'] != 0,
            (df['合計理論耗用'] / df['合計實際耗用']) * 100,
            np.nan
        )

    df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
    df['Δ%'] = np.where(
        df['合計理論耗用'] != 0,
        df['Δ耗用 (Deviation)'] / df['合計理論耗用'] * 100,
        np.nan
    )

    # ==========================================
    # SAFE UNIQUE FUNCTION
    # ==========================================
    def get_unique(col, data):
        return sorted(data[col].dropna().unique()) if col in data.columns else []

    # ==========================================
    # SIDEBAR FILTER (CASCADING)
    # ==========================================
    st.sidebar.header("🔍 Filters (Cascading)")

    # 1️⃣ TIME
    sel_month = st.sidebar.multiselect(
        "年月",
        options=get_unique('年月', df),
        default=get_unique('年月', df)
    )
    df_f1 = df[df['年月'].isin(sel_month)]

    # 2️⃣ LINE
    sel_line = st.sidebar.multiselect(
        "線別",
        options=get_unique('線別', df_f1),
        default=get_unique('線別', df_f1)
    )
    df_f2 = df_f1[df_f1['線別'].isin(sel_line)]

    # 3️⃣ PURPOSE (NEW)
    sel_usage = st.sidebar.multiselect(
        "用途",
        options=get_unique('用途', df_f2),
        default=get_unique('用途', df_f2)
    )
    df_f3 = df_f2[df_f2['用途'].isin(sel_usage)]

    # 4️⃣ COLOR
    sel_color = st.sidebar.multiselect(
        "顏色",
        options=get_unique('顏色', df_f3),
        default=get_unique('顏色', df_f3)
    )
    df_f4 = df_f3[df_f3['顏色'].isin(sel_color)]

    # 5️⃣ RESIN
    sel_resin = st.sidebar.multiselect(
        "樹脂",
        options=get_unique('樹脂', df_f4),
        default=get_unique('樹脂', df_f4)
    )
    df_f5 = df_f4[df_f4['樹脂'].isin(sel_resin)]

    # 6️⃣ SUPPLIER
    sel_supplier = st.sidebar.multiselect(
        "廠商",
        options=get_unique('油漆廠商', df_f5),
        default=get_unique('油漆廠商', df_f5)
    )

    filtered_df = df_f5[df_f5['油漆廠商'].isin(sel_supplier)].copy()

    # ==========================================
    # KPI
    # ==========================================
    st.markdown("### 🎯 KPI Overview")

    if not filtered_df.empty:
        c1, c2, c3, c4 = st.columns(4)

        avg_perf = filtered_df['合計績效%'].mean()
        total_dev = filtered_df['Δ耗用 (Deviation)'].sum()
        worst = filtered_df.loc[filtered_df['合計績效%'].idxmin()]

        c1.metric("平均績效", f"{avg_perf:.2f}%")
        c2.metric("總Δ耗用", f"{total_dev:,.0f}")
        c3.metric("最低績效", worst['塗料編號'], f"{worst['合計績效%']:.2f}%")
        c4.metric("資料筆數", len(filtered_df))
    else:
        st.warning("無資料符合條件")

    st.divider()

    # ==========================================
    # TABS
    # ==========================================
    tab1, tab2, tab3, tab4 = st.tabs([
        "Heatmap",
        "Theoretical vs Actual",
        "Deviation",
        "Trend"
    ])

    # -----------------------------
    # HEATMAP (FIXED VERSION)
    # -----------------------------
    with tab1:
        st.subheader("班別績效 Heatmap")

        shift_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in filtered_df.columns]

        if shift_cols:
            df_melt = pd.melt(
                filtered_df,
                id_vars=['塗料編號'],
                value_vars=shift_cols,
                var_name='班別',
                value_name='績效'
            )

            df_melt['班別'] = df_melt['班別'].str.replace('班績效%', '')
            df_melt = df_melt.dropna()

            pivot = df_melt.pivot_table(
                index='塗料編號',
                columns='班別',
                values='績效',
                aggfunc='mean'
            )

            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                colorscale='RdYlGn'
            ))

            fig.update_layout(height=600)
            st.plotly_chart(fig, use_container_width=True)

    # -----------------------------
    # BAR
    # -----------------------------
    with tab2:
        st.subheader("理論 vs 實際")

        df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()

        fig = go.Figure()
        fig.add_bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name="理論")
        fig.add_bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name="實際")
        fig.update_layout(barmode='group')

        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------
    # DEVIATION
    # -----------------------------
    with tab3:
        st.subheader("Δ耗用分析")

        df_dev = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()

        df_dev['type'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗', '節省')

        fig = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='type',
                     color_discrete_map={'超耗': 'red', '節省': 'green'})

        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------
    # TREND
    # -----------------------------
    with tab4:
        st.subheader("趨勢分析")

        trend = filtered_df.groupby('年月')['合計績效%'].mean().reset_index()

        fig = px.line(trend, x='年月', y='合計績效%', markers=True)

        st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # RAW DATA
    # ==========================================
    with st.expander("Data View"):
        st.dataframe(filtered_df)

else:
    st.info("請上傳資料")
