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
st.markdown("依據 MES/Excel 數據進行系統化分析 (全功能整合最佳化佈局)")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (CSV 或 Excel)", type=['csv', 'xlsx'])

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
        shift_cols = []
        for shift in ['A', 'B', 'C', 'D']:
            cols = [f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%']
            numeric_cols.extend(cols)
            if f'{shift}班績效%' in df.columns:
                shift_cols.append(f'{shift}班績效%')
                
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if '合計績效%' not in df.columns or df['合計績效%'].isnull().all():
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # Phân loại hiệu suất cho Pie Chart
        conds_global = [df['合計績效%'] < 85, (df['合計績效%'] >= 85) & (df['合計績效%'] < 95), (df['合計績效%'] >= 95) & (df['合計績效%'] < 100), df['合計績效%'] >= 100]
        labels_global = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
        df['績效等級'] = np.select(conds_global, labels_global, default='未知')

        # ==========================================
        # [ 2. DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=sorted(df['年月'].unique()), default=df['年月'].unique())
        df_s1 = df[df['年月'].isin(sel_month)]
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=sorted(df_s1['線別'].unique()), default=df_s1['線別'].unique())
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        sel_usage = st.sidebar.multiselect("3. 選擇用途", options=sorted(df_s2['用途'].unique()), default=df_s2['用途'].unique())
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 3. VISUALIZATION LAYOUT ]
        # ==========================================
        st.markdown("### 📈 視覺化分析與根因探討")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart)

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [總覽] 績效分佈", "🚨 [決策] 優先改善清單", "📦 [根因] 穩定度分析", 
            "🎯 [明細] 績效燈號", "📊 [明細] 耗用對比", "📉 [明細] 差異分析"
        ])

        # --- 1. OVERVIEW (KPIs + Pie) ---
        with tab_overview:
            st.subheader("1. 產線整體績效總覽")
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                k1.metric("平均總績效", f"{filtered_df['合計績效%'].mean():.2f}%")
                k2.metric("總差異耗用", f"{filtered_df['Δ耗用 (Deviation)'].sum():,.0f}", delta_color="inverse")
                k3.metric("分析區間內塗料總數", f"{total_paints} 支")
                st.divider()
                pie_counts = filtered_df['績效等級'].value_counts().reset_index()
                pie_counts.columns = ['績效等級', '數量']
                fig_pie = px.pie(pie_counts, values='數量', names='績效等級', hole=0.4,
                                 color='績效等級', color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'})
                fig_pie.update_layout(height=550)
                st.plotly_chart(fig_pie, use_container_width=True)

        # --- 2. PARETO ---
        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖")
            pareto_data = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index().sort_values(by='Δ耗用 (Deviation)', ascending=False)
            if not pareto_data.empty:
                pareto_data['累計%'] = pareto_data['Δ耗用 (Deviation)'].cumsum() / pareto_data['Δ耗_ (Deviation)'].sum() * 100
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=pareto_data['塗料編號'].head(40), y=pareto_data['Δ耗用 (Deviation)'].head(40), name='超耗量', marker_color='#d73027'))
                fig_pareto.add_trace(go.Scatter(x=pareto_data['塗料編號'].head(40), y=pareto_data['累計%'].head(40), name='累計%', yaxis='y2', line=dict(color='#4575b4', width=3)))
                fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 105]), height=600, plot_bgcolor='white', xaxis=dict(tickangle=-90))
                st.plotly_chart(fig_pareto, use_container_width=True)

        # --- 3. ROOT CAUSE (Box Plots with COOL Palette) ---
        with tab_rootcause:
            st.subheader("3. 穩定度分析 (排除紅色干擾)")
            col1, col2 = st.columns(2)
            COOL_PALETTE = ['#1f77b4', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            with col1:
                if '油漆廠商' in filtered_df.columns:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", color_discrete_sequence=COOL_PALETTE)
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box1.update_layout(showlegend=True, margin=dict(r=130), height=550, plot_bgcolor='white', yaxis=dict(gridcolor='#999999'))
                    st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna(subset=['績效%'])
                    shift_df['班別'] = shift_df['班別'].str.replace('班績效%', '班')
                    fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all", color_discrete_sequence=COOL_PALETTE)
                    fig_box2.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box2.update_layout(showlegend=True, margin=dict(r=100), height=550, plot_bgcolor='white', yaxis=dict(gridcolor='#999999'))
                    st.plotly_chart(fig_box2, use_container_width=True)

        # --- 4. SCATTER (Khôi phục chia nhóm 40 & Label -90) ---
        with tab_scatter:
            st.subheader("4. 單一塗料績效燈號 (明細版)")
            for i in range(num_charts):
                start_idx = i * items_per_chart
                current_batch = sort_order[start_idx : start_idx + items_per_chart]
                plot_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)].copy().dropna(subset=['合計績效%'])
                if not plot_df.empty:
                    fig = px.scatter(plot_df, x='塗料編號', y='合計績效%', color='績效等級', size='合計理論耗用', size_max=35,
                                     color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                                     category_orders={"績效等級": labels_global})
                    fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=2)
                    # padding Y axis
                    y_min, y_max = plot_df['合計績效%'].min(), plot_df['合計績效%'].max()
                    fig.update_layout(xaxis=dict(tickangle=-90, dtick=1, showline=True, linecolor='black', mirror=True),
                                      yaxis=dict(range=[math.floor(y_min/10)*10-5, math.ceil(y_max/10)*10+10], gridcolor='#999999', showline=True, linecolor='black', mirror=True),
                                      height=650, plot_bgcolor='white', title=f"第 {i+1} 組塗料績效")
                    fig.update_traces(marker=dict(line=dict(width=1.5, color='black')))
                    st.plotly_chart(fig, use_container_width=True)

        # --- 5. BAR (Khôi phục chia nhóm 40) ---
        with tab_bar:
            st.subheader("5. 理論 vs 實際耗用明細")
            for i in range(num_charts):
                current_batch = sort_order[i*40 : (i+1)*40]
                df_bar = filtered_df[filtered_df['塗料編號'].isin(current_batch)].groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論', marker_color='#2c3e50'))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際', marker_color='#3498db'))
                fig_bar.update_layout(xaxis=dict(tickangle=-90, dtick=1, showline=True, linecolor='black', mirror=True), height=600, barmode='group', plot_bgcolor='white')
                st.plotly_chart(fig_bar, use_container_width=True)

        # --- 6. DEVIATION (Khôi phục chia nhóm 40) ---
        with tab_dev:
            st.subheader("6. 耗用差異明細 (實際 - 理論)")
            for i in range(num_charts):
                current_batch = sort_order[i*40 : (i+1)*40]
                df_dev = filtered_df[filtered_df['塗料編號'].isin(current_batch)].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
                fig_dev.add_hline(y=0, line_color="black", line_width=2.5)
                fig_dev.update_layout(xaxis=dict(tickangle=-90, dtick=1, showline=True, linecolor='black', mirror=True), height=600, plot_bgcolor='white')
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 原始數據檢視"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"系統錯誤：{e}")
else:
    st.info("👈 請上傳數據檔案。")
