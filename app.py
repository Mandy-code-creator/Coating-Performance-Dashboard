import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(page_title="塗料 Dashboard", layout="wide")

st.title("📊 塗料生產績效分析 Dashboard (Fixed Version)")

# ==========================================
# UPLOAD
# ==========================================
st.sidebar.header("📂 Upload Data")
uploaded_file = st.sidebar.file_uploader("CSV / Excel", type=['csv', 'xlsx'])

# ==========================================
# LOAD
# ==========================================
if uploaded_file is not None:

    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, engine='python', sep=None)
    else:
        df = pd.read_excel(uploaded_file)

    df = df.dropna(subset=['塗料編號'])

    # format month
    if '年月' in df.columns:
        df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True)

    # categorical
    for col in ['線別', '油漆廠商', '顏色', '樹脂', '用途']:
        if col in df.columns:
            df[col] = df[col].fillna('未定義').astype(str)

    # numeric
    num_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # KPI calc
    df['Δ耗用'] = df['合計實際耗用'] - df['合計理論耗用']

    if '合計績效%' not in df.columns:
        df['合計績效%'] = np.where(
            df['合計實際耗用'] != 0,
            df['合計理論耗用'] / df['合計實際耗用'] * 100,
            np.nan
        )

    # ==========================================
    # SAFE FUNCTION
    # ==========================================
    def opt(col, data):
        return sorted(data[col].dropna().unique()) if col in data.columns else []

    # ==========================================
    # CASCADING FILTER
    # ==========================================

    st.sidebar.header("🔍 Filters (Cascading)")

    # 1 TIME
    sel_month = st.sidebar.multiselect("年月", opt('年月', df), default=opt('年月', df))
    df1 = df[df['年月'].isin(sel_month)]

    # 2 LINE
    sel_line = st.sidebar.multiselect("線別", opt('線別', df1), default=opt('線別', df1))
    df2 = df1[df1['線別'].isin(sel_line)]

    # 3 PURPOSE
    sel_usage = st.sidebar.multiselect("用途", opt('用途', df2), default=opt('用途', df2))
    df3 = df2[df2['用途'].isin(sel_usage)]

    # 4 COLOR
    sel_color = st.sidebar.multiselect("顏色", opt('顏色', df3), default=opt('顏色', df3))
    df4 = df3[df3['顏色'].isin(sel_color)]

    # 5 RESIN
    sel_resin = st.sidebar.multiselect("樹脂", opt('樹脂', df4), default=opt('樹脂', df4))
    df5 = df4[df4['樹脂'].isin(sel_resin)]

    # 6 SUPPLIER
    sel_supplier = st.sidebar.multiselect("廠商", opt('油漆廠商', df5), default=opt('油漆廠商', df5))
    filtered_df = df5[df5['油漆廠商'].isin(sel_supplier)].copy()

    # ==========================================
    # KPI
    # ==========================================
    st.markdown("## 🎯 KPI")

    if not filtered_df.empty:
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("平均績效", f"{filtered_df['合計績效%'].mean():.2f}%")
        c2.metric("Δ耗用", f"{filtered_df['Δ耗用'].sum():,.0f}")
        c3.metric("資料筆數", len(filtered_df))
        c4.metric("塗料數", filtered_df['塗料編號'].nunique())

    else:
        st.warning("No data")

    st.divider()

    # ==========================================
    # TABS
    # ==========================================
    tab1, tab2, tab3 = st.tabs(["Heatmap", "Bar", "Trend"])

    # ==========================================
    # HEATMAP (FIXED - KEEP ALL 41 LINES)
    # ==========================================
    with tab1:
        st.subheader("班別 Heatmap (FIXED)")

        shift_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in filtered_df.columns]

        if shift_cols:

            df_melt = pd.melt(
                filtered_df,
                id_vars=['塗料編號'],
                value_vars=shift_cols,
                var_name='班別',
                value_name='績效'
            )

            # FIX: không dropna
            df_melt['績效'] = df_melt['績效'].fillna(0)

            pivot = df_melt.pivot_table(
                index='塗料編號',
                columns='班別',
                values='績效',
                aggfunc='mean'
            )

            # 🔥 FIX: giữ đủ ALL LINE (41 line fix ở đây)
            pivot = pivot.reindex(filtered_df['塗料編號'].unique())

            pivot = pivot.fillna(0)

            fig = go.Figure(data=go.Heatmap(
                z=pivot.values,
                x=pivot.columns,
                y=pivot.index,
                colorscale='RdYlGn'
            ))

            fig.update_layout(
                height=700,
                yaxis_title="塗料編號",
                xaxis_title="班別"
            )

            st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # BAR
    # ==========================================
    with tab2:
        st.subheader("理論 vs 實際")

        df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()

        fig = go.Figure()
        fig.add_bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name="理論")
        fig.add_bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name="實際")

        fig.update_layout(barmode='group')

        st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # TREND (FIX MULTI LINE)
    # ==========================================
    with tab3:
        st.subheader("Trend (ALL MATERIALS)")

        if '年月' in filtered_df.columns:

            trend_df = filtered_df.groupby(['年月', '塗料編號'])['合計績效%'].mean().reset_index()

            fig = px.line(
                trend_df,
                x='年月',
                y='合計績效%',
                color='塗料編號',   # 🔥 FIX: show all materials
                markers=True
            )

            st.plotly_chart(fig, use_container_width=True)

    # ==========================================
    # RAW DATA
    # ==========================================
    with st.expander("DATA VIEW"):
        st.dataframe(filtered_df)

else:
    st.info("Upload file to start")
