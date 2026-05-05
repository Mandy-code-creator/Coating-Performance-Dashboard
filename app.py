import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# [ 0. PAGE CONFIG & CSS ]
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
[data-testid="stKPIs"] div{
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 10px;
    background-color: #f9fbfd;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("<b>核心異常分析：僅鎖定超耗量 ≥ 500 之塗料 (High Priority Focus)</b>", unsafe_allow_html=True)

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            numeric_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
                
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 1. 計算績效與差異量
        if '合計績效%' not in df.columns or df['合計績效%'].sum() == 0:
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']

        # ==========================================
        # 🔥 [關鍵修正]：依照要求，僅保留超耗量 >= 500 的項目
        # ==========================================
        initial_count = len(df)
        df = df[df['Δ耗用 (Deviation)'] >= 500].copy()
        filtered_count = len(df)
        
        st.sidebar.success(f"篩選完成：已從 {initial_count} 筆中篩選出 {filtered_count} 筆超耗量 ≥ 500 的資料。")

        if df.empty:
            st.warning("⚠️ 目前資料中沒有超耗量大於等於 500 的塗料，請檢查數據或放寬標準。")
            st.stop()

        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # [ COLOR MAP ]
        conds_global = [
            df['合計績效%'] < 80, 
            (df['合計績效%'] >= 80) & (df['合計績效%'] < 90), 
            (df['合計績效%'] >= 90) & (df['合計績效%'] < 100), 
            (df['合計績效%'] >= 100) & (df['合計績效%'] <= 110),
            df['合計績效%'] > 110
        ]
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {
            '🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000',
            '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'
        }
        df['績效等級'] = np.select(conds_global, labels_global, default='未知')

        # ==========================================
        # [ 2. DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        available_months = sorted(df['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=available_months, default=available_months[:1])
        df_s1 = df[df['年月'].isin(sel_month)]
        
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=sorted(df_s1['線別'].unique()), default=df_s1['線別'].unique())
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        sel_usage = st.sidebar.multiselect("3. 選擇用途", options=sorted(df_s2['用途'].unique()), default=df_s2['用途'].unique())
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 3. VISUALIZATION ]
        # ==========================================
        st.markdown(f"### 📈 視覺化分析與根因探討 (當前顯示: {len(filtered_df)} 支)")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            " donuts [總覽] 績效分佈", "🚨 [決策] 優先改善清單", "📦 [根因] 穩定度分析", 
            "🎯 [全景] 績效燈號", "📊 [明細] 耗用對比", "📉 [明細] 差異分析"
        ])

        common_layout = dict(
            plot_bgcolor='white',
            font=dict(color='black', family='Arial', size=13, weight='bold'),
            xaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True),
            yaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True, gridcolor='#e6e6e6')
        )

        with tab_overview:
            st.subheader("1. 高超耗項目績效總覽")
            k1, k2, k3 = st.columns(3)
            avg_perf = filtered_df['合計績效%'].mean()
            total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
            k1.metric("異常組平均績效", f"{avg_perf:.2f}%")
            k2.metric("總超耗總量 (僅計算 ≥ 500 項目)", f"{total_delta:,.0f}", delta_color="inverse")
            k3.metric("需優先改善塗料數", f"{total_paints} 支")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            
            with col_pie:
                pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
                if not pie_df.empty:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '數量']
                    fig_pie = px.pie(pie_counts, values='數量', names='績效等級', color='績效等級',
                                     color_discrete_map=perf_color_map, hole=0.4)
                    fig_pie.update_layout(title="<b>超耗塗料之績效等級分佈</b>")
                    st.plotly_chart(fig_pie, use_container_width=True)
            
            with col_table:
                st.markdown("##### 🚨 嚴重超耗 Top 10 清單")
                decision_table = filtered_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)
                show_cols = ['塗料編號', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']
                st.dataframe(decision_table[show_cols].style.format({'合計績效%': '{:.2f}%', 'Δ耗用 (Deviation)': '{:,.0f}'}), 
                             use_container_width=True, hide_index=True)

        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index().sort_values(by='Δ耗用 (Deviation)', ascending=False)
            if not pareto_df.empty:
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_pareto = pareto_df.head(40)
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=top_pareto['塗料編號'], y=top_pareto['Δ耗用 (Deviation)'], name='超耗量', marker_color='#990000'))
                fig_pareto.add_trace(go.Scatter(x=top_pareto['塗料編號'], y=top_pareto['累計%'], name='累計%', yaxis='y2', line=dict(color='#00008B', width=3)))
                fig_pareto.update_layout(**common_layout)
                fig_pareto.update_layout(
                    yaxis2=dict(title="累計%", overlaying='y', side='right', range=[0, 105]),
                    xaxis=dict(tickangle=-90), height=600, title="<b>關鍵 80/20 改善優先順序 (超耗量 ≥ 500)</b>"
                )
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_rootcause:
            st.subheader("3. 穩定度分析 (僅限超耗大於 500 項目)")
            col1, col2 = st.columns(2)
            NO_RED_PALETTE = px.colors.qualitative.Safe
            with col1:
                fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", color_discrete_sequence=NO_RED_PALETTE)
                fig_box1.add_hline(y=100, line_dash="dash", line_color="red")
                fig_box1.update_layout(**common_layout, title="<b>供應商穩定度</b>")
                st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                shift_cols = [f'{s}班績效%' for s in ['A', 'B', 'C', 'D'] if f'{s}班績效%' in filtered_df.columns]
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna()
                    fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all")
                    fig_box2.add_hline(y=100, line_dash="dash", line_color="red")
                    fig_box2.update_layout(**common_layout, title="<b>班別操作穩定度</b>")
                    st.plotly_chart(fig_box2, use_container_width=True)

        with tab_scatter:
            st.subheader(f"4. 燈號全景總覽 (僅顯示異常項目)")
            if not filtered_df.empty:
                plot_df = filtered_df[filtered_df['合計理論耗用'] > 0].copy()
                seq_map = {code: i+1 for i, code in enumerate(sort_order)}
                plot_df['塗料序號'] = plot_df['塗料編號'].map(seq_map)
                fig = px.scatter(plot_df, x='塗料序號', y='合計績效%', color='績效等級',
                                 color_discrete_map=perf_color_map, size='合計理論耗用', hover_name='塗料編號')
                fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                fig.update_layout(**common_layout, height=700, title="<b>異常塗料績效分布 (點越大表示理論用量越高)</b>")
                st.plotly_chart(fig, use_container_width=True)

        with tab_dev:
            st.subheader("6. 耗用差異絕對值 (Deviation ≥ 500)")
            for i in range(num_charts):
                batch_df = filtered_df[filtered_df['塗料編號'].isin(sort_order[i*40 : (i+1)*40])].copy()
                batch_df['Color'] = np.where(batch_df['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(batch_df, x='塗料編號', y='Δ耗用 (Deviation)', color='Color',
                                 color_discrete_map={'超耗': '#990000', '節省': '#008000'})
                
                # 分開設定：先套用共用版面，再設定專屬屬性與 X 軸
                fig_dev.update_layout(**common_layout)
                fig_dev.update_layout(height=500)
                fig_dev.update_xaxes(tickangle=-90) # 單獨更新 X 軸角度，避免衝突
                
                st.plotly_chart(fig_dev, use_container_width=True)

        with tab_dev:
            st.subheader("6. 耗用差異絕對值 (Deviation ≥ 500)")
            for i in range(num_charts):
                batch_df = filtered_df[filtered_df['塗料編號'].isin(sort_order[i*40 : (i+1)*40])].copy()
                batch_df['Color'] = np.where(batch_df['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(batch_df, x='塗料編號', y='Δ耗用 (Deviation)', color='Color',
                                 color_discrete_map={'超耗': '#990000', '節省': '#008000'})
                fig_dev.update_layout(**common_layout, height=500, xaxis=dict(tickangle=-90))
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 檢視過濾後的明細資料"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"System Error：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案。系統將自動篩選超耗量 ≥ 500 的資料進行分析。")
