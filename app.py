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
st.markdown("依據 MES/Excel 數據進行系統化分析 (色彩對比最佳化版)")

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
        # [ 3. DECISION MAKING KPIs ]
        # ==========================================
        if not filtered_df.empty:
            avg_perf = filtered_df['合計績效%'].mean()
            total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
            total_paints = len(filtered_df['塗料編號'].unique())
        
        st.divider()

        # ==========================================
        # [ 4. VISUALIZATION ]
        # ==========================================
        st.markdown("### 📈 視覺化分析與根因探討")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        items_per_chart = 40
        num_charts = math.ceil(len(sort_order) / items_per_chart)

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [總覽] 績效分佈", "🚨 [決策] 優先改善清單", "📦 [根因] 穩定度分析", 
            "🎯 [明細] 績效燈號", "📊 [明細] 耗用對比", "📉 [明細] 差異分析"
        ])

        # --- TAB OVERVIEW ---
        with tab_overview:
            st.subheader("1. 產線整體績效總覽 (Macro Overview)")
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                k1.metric("平均總績效", f"{avg_perf:.2f}%")
                k2.metric("總差異耗用", f"{total_delta:,.0f}", delta_color="inverse")
                k3.metric("分析塗料總數", f"{total_paints} 支")
                st.divider()
                pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
                if not pie_df.empty:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '數量']
                    fig_pie = px.pie(pie_counts, values='數量', names='績效等級', hole=0.4,
                                     color='績效等級', color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'})
                    fig_pie.update_layout(height=550, plot_bgcolor='white')
                    st.plotly_chart(fig_pie, use_container_width=True)

        # --- TAB PARETO ---
        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            if not pareto_df.empty:
                pareto_df = pareto_df.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=pareto_df['塗料編號'].head(40), y=pareto_df['Δ耗用 (Deviation)'].head(40), name='超耗量', marker_color='#d73027'))
                fig_pareto.add_trace(go.Scatter(x=pareto_df['塗料編號'].head(40), y=pareto_df['累計%'].head(40), name='累計%', yaxis='y2', line=dict(color='#4575b4', width=3)))
                fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 105]), height=600, plot_bgcolor='white')
                st.plotly_chart(fig_pareto, use_container_width=True)

        # --- TAB ROOTCAUSE (FIX MÀU TẠI ĐÂY) ---
        with tab_rootcause:
            col1, col2 = st.columns(2)
            # 💡 Sử dụng Palette màu lạnh (Xanh dương, xanh lá, tím) để tránh trùng màu Đỏ của đường mục tiêu
            COOL_PALETTE = ['#1f77b4', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            
            with col1:
                st.subheader("3A. 供應商品質穩定度")
                if '油漆廠商' in filtered_df.columns and not filtered_df.empty:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all",
                                      color_discrete_sequence=COOL_PALETTE)
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box1.update_layout(showlegend=True, margin=dict(r=130), height=550, plot_bgcolor='white')
                    st.plotly_chart(fig_box1, use_container_width=True)

            with col2:
                st.subheader("3B. 班別操作穩定度")
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna(subset=['績效%'])
                    shift_df['班別'] = shift_df['班別'].str.replace('班績效%', '班')
                    if not shift_df.empty:
                        fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all",
                                          color_discrete_sequence=COOL_PALETTE)
                        fig_box2.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                        fig_box2.update_layout(showlegend=True, margin=dict(r=100), height=550, plot_bgcolor='white')
                        st.plotly_chart(fig_box2, use_container_width=True)

        # --- TAB SCATTER ---
        with tab_scatter:
            st.subheader("4. 單一塗料績效燈號追蹤")
            for i in range(num_charts):
                start_idx = i * items_per_chart
                current_batch = sort_order[start_idx : start_idx + items_per_chart]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                fig = px.scatter(batch_df, x='塗料編號', y='合計績效%', color='績效等級', size='合計理論耗用', size_max=35,
                                 color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'})
                fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=2)
                fig.update_layout(xaxis=dict(tickangle=-90), height=650, plot_bgcolor='white')
                st.plotly_chart(fig, use_container_width=True)

        # --- TAB BAR & DEV ---
        with tab_bar:
            for i in range(num_charts):
                current_batch = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                fig_bar = px.bar(batch_df, x='塗料編號', y=['合計理論耗用', '合計實際耗用'], barmode='group')
                fig_bar.update_layout(xaxis=dict(tickangle=-90), height=600, plot_bgcolor='white')
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            for i in range(num_charts):
                current_batch = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                batch_df['Color'] = np.where(batch_df['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(batch_df, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
                fig_dev.add_hline(y=0, line_color="black", line_width=2)
                fig_dev.update_layout(xaxis=dict(tickangle=-90), height=600, plot_bgcolor='white')
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 檢視底層明細資料 (Raw Data View)"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"系統錯誤：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案。")
