import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (高對比度專業報表版)")

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

        # 1. 數據清洗
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # 2. 數值轉換
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 3. 補算指標
        if '合計績效%' not in df.columns or df['合計績效%'].isnull().all():
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

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
        st.markdown("### 🎯 決策指標 (Decision Making KPIs)")
        if not filtered_df.empty:
            k1, k2, k3, k4 = st.columns(4)
            avg_perf = filtered_df['合計績效%'].mean()
            total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
            
            k1.metric("平均總績效", f"{avg_perf:.2f}%")
            k2.metric("總差異耗用", f"{total_delta:,.0f}", delta_color="inverse")
            
            worst_perf_df = filtered_df.dropna(subset=['合計績效%'])
            if not worst_perf_df.empty:
                worst_row = worst_perf_df.loc[worst_perf_df['合計績效%'].idxmin()]
                k3.metric("優先改善對象", f"{worst_row['塗料編號']}", f"{worst_row['合計績效%']:.2f}%")
            k4.metric("分析塗料總數", f"{len(filtered_df['塗料編號'].unique())} 支")

        st.divider()

        # ==========================================
        # [ 4. VISUALIZATION ]
        # ==========================================
        st.markdown("### 📊 核心視覺化分析")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart)

        viz_tab1, viz_tab2, viz_tab3 = st.tabs(["🎯 績效燈號散佈圖", "📊 耗用量對比", "📉 差異分析"])

        with viz_tab1:
            st.subheader(f"1. 塗料績效散佈圖 (共 {total_paints} 支，分 {num_charts} 組)")
            
            st.info("""
            **💡 讀圖提示：**
            * **🎨 顏色：** 代表績效狀態 (🔴 嚴重超耗 < 85% | 🟡 注意 85-95% | 🔵 接近理論 95-100% | 🟢 達標/節省 ≥ 100%)
            * **⭕ 圓圈大小：** 代表**「合計理論耗用量」**。圓圈越大，代表該塗料在產線上的使用量與占比越大。
            * **🔥 決策重點：** 請優先尋找**「大紅圈」** (使用量極大且嚴重超耗的塗料)，這代表最大的成本流失！
            """)
            
            if not filtered_df.empty and total_paints > 0:
                for i in range(num_charts):
                    start_idx = i * items_per_chart
                    end_idx = min(start_idx + items_per_chart, total_paints)
                    current_batch = sort_order[start_idx:end_idx]
                    
                    plot_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)].copy()
                    plot_df = plot_df.dropna(subset=['合計理論耗用', '合計績效%'])
                    plot_df = plot_df[plot_df['合計理論耗用'] > 0] 

                    if not plot_df.empty:
                        conds = [plot_df['合計績效%'] < 85, (plot_df['合計績效%'] < 95), (plot_df['合計績效%'] < 100), plot_df['合計績效%'] >= 100]
                        labels = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
                        plot_df['績效等級'] = np.select(conds, labels, default='未知')
                        
                        plot_df['合計績效%'] = plot_df['合計績效%'].round(2)
                        
                        fig = px.scatter(
                            plot_df, x='塗料編號', y='合計績效%', color='績效等級',
                            color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                            size='合計理論耗用', size_max=35,
                            category_orders={"績效等級": labels},
                            hover_data=['線別', '用途', '合計理論耗用', '合計實際耗用']
                        )
                        
                        # Vẽ đường nét đứt 100%
                        fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=2.5)
                        
                        # --- 💡 DỜI NHÃN RA NGOÀI BIỂU ĐỒ ---
                        fig.add_annotation(
                            x=1.01, # Tọa độ X ngoài mép phải khung hình
                            y=100, 
                            xref="paper", yref="y",
                            text="<b>🎯 目標 100%</b>", 
                            showarrow=False,
                            xanchor="left", yanchor="middle",
                            font=dict(color="red", size=14)
                        )
                        
                        fig.update_traces(marker=dict(opacity=1.0, line=dict(width=1.5, color='black')))
                        
                        min_perf = plot_df['合計績效%'].min()
                        max_perf = plot_df['合計績效%'].max()
                        y_min_pad = math.floor(min_perf / 10) * 10 - 5
                        y_max_pad = math.ceil(max_perf / 10) * 10 + 10
                        
                        fig.update_layout(
                            plot_bgcolor='white', 
                            font=dict(color='black', size=13),
                            margin=dict(r=100), # Mở rộng biên phải 100px để không bị mất chữ
                            xaxis=dict(
                                dtick=1, tickangle=-90, categoryorder='array', categoryarray=current_batch,
                                showline=True, linewidth=1.5, linecolor='black', mirror=True, 
                                tickfont=dict(color='black', size=11)
                            ),
                            yaxis=dict(
                                title="<b>合計績效 (%)</b>", 
                                dtick=10,             
                                range=[y_min_pad, y_max_pad], 
                                gridcolor='#999999', gridwidth=1, 
                                zeroline=False,
                                showline=True, linewidth=1.5, linecolor='black', mirror=True, 
                                tickfont=dict(color='black', size=12)
                            ),
                            height=650,
                            title=f"<b>第 {i+1} 組塗料績效 ({start_idx+1} - {end_idx})</b>"
                        )
                        st.plotly_chart(fig, use_container_width=True)

        with viz_tab2:
            st.subheader("2. 理論耗用 vs 實際耗用")
            for i in range(num_charts):
                start_idx = i * items_per_chart
                current_batch = sort_order[start_idx : start_idx + items_per_chart]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                
                df_bar = batch_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用', marker_color='#34495e'))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用', marker_color='#3498db'))
                
                fig_bar.update_layout(
                    plot_bgcolor='white', font=dict(color='black'),
                    barmode='group', 
                    xaxis=dict(
                        dtick=1, tickangle=-90, categoryorder='array', categoryarray=current_batch,
                        showline=True, linewidth=1.5, linecolor='black', mirror=True, tickfont=dict(color='black')
                    ),
                    yaxis=dict(
                        title="<b>耗用量</b>",
                        gridcolor='#999999', gridwidth=1, zeroline=False,
                        showline=True, linewidth=1.5, linecolor='black', mirror=True, tickfont=dict(color='black')
                    ),
                    height=600,
                    title=f"<b>第 {i+1} 組耗用對比</b>"
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        with viz_tab3:
            st.subheader("3. 耗用差異 (Δ 實際 - 理論)")
            for i in range(num_charts):
                start_idx = i * items_per_chart
                current_batch = sort_order[start_idx : start_idx + items_per_chart]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)]
                
                df_dev = batch_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
                
                fig_dev.add_hline(y=0, line_dash="solid", line_color="black", line_width=2.5)
                
                # --- 💡 DỜI NHÃN RA NGOÀI BIỂU ĐỒ ---
                fig_dev.add_annotation(
                    x=1.01, 
                    y=0, 
                    xref="paper", yref="y",
                    text="<b>基準 0</b>", 
                    showarrow=False,
                    xanchor="left", yanchor="middle",
                    font=dict(color="black", size=14)
                )
                
                fig_dev.update_layout(
                    plot_bgcolor='white', font=dict(color='black'),
                    margin=dict(r=80), # Mở rộng biên phải
                    xaxis=dict(
                        dtick=1, tickangle=-90, categoryorder='array', categoryarray=current_batch,
                        showline=True, linewidth=1.5, linecolor='black', mirror=True, tickfont=dict(color='black')
                    ),
                    yaxis=dict(
                        title="<b>差異量 (Δ耗用)</b>",
                        gridcolor='#999999', gridwidth=1, zeroline=False,
                        showline=True, linewidth=1.5, linecolor='black', mirror=True, tickfont=dict(color='black')
                    ),
                    height=600, 
                    title=f"<b>第 {i+1} 組差異分析</b>"
                )
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 數據明細"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"系統錯誤：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案。")
