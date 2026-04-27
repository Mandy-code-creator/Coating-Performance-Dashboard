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

# Áp dụng CSS để tạo khung viền chuyên nghiệp (Đã sửa lỗi unsafe_allow_html)
st.markdown("""
<style>
.stPlotlyChart {
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    background-color: white;
    padding: 10px;
    margin-bottom: 20px;
}
[data-testid="stKPIs"] div{
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 10px;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (進階根因分析與高對比版)")

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

        # 1. 數據清洗 (Làm sạch dữ liệu)
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # 2. 數值轉換 (Chuyển đổi kiểu số)
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

        # 3. 補算指標 (Tính toán các cột chỉ số)
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

        viz_tab1, viz_tab2, viz_tab3, viz_tab4, viz_tab5 = st.tabs([
            "🎯 績效燈號 (Scatter)", "📊 耗用對比 (Bar)", "📉 差異分析 (Deviation)", "🚨 異常柏拉圖 (Pareto)", "📦 穩定度分析 (Box Plot)"
        ])

        # --- TAB 1: SCATTER PLOT ---
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
                        
                        # Đường mục tiêu 100%
                        fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=2.5)
                        fig.add_annotation(
                            x=1.01, y=100, xref="paper", yref="y",
                            text="<b>🎯 目標 100%</b>", showarrow=False,
                            xanchor="left", yanchor="middle", font=dict(color="red", size=14)
                        )
                        
                        fig.update_traces(marker=dict(opacity=1.0, line=dict(width=1.5, color='black')))
                        
                        min_perf, max_perf = plot_df['合計績效%'].min(), plot_df['合計績效%'].max()
                        y_min_pad, y_max_pad = math.floor(min_perf / 10) * 10 - 5, math.ceil(max_perf / 10) * 10 + 10
                        
                        fig.update_layout(
                            plot_bgcolor='white', font=dict(color='black', size=13), margin=dict(r=100),
                            xaxis=dict(dtick=1, tickangle=-90, categoryorder='array', categoryarray=current_batch, showline=True, linewidth=1.5, linecolor='black', mirror=True, tickfont=dict(size=11)),
                            yaxis=dict(title="<b>合計績效 (%)</b>", dtick=10, range=[y_min_pad, y_max_pad], gridcolor='#999999', gridwidth=1, zeroline=False, showline=True, linewidth=1.5, linecolor='black', mirror=True),
                            height=650, title=f"<b>第 {i+1} 組塗料績效 ({start_idx+1} - {end_idx})</b>"
                        )
                        st.plotly_chart(fig, use_container_width=True)

        # --- TAB 2: BAR CHART ---
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
                    plot_bgcolor='white', font=dict(color='black'), barmode='group', 
                    xaxis=dict(dtick=1, tickangle=-90, categoryorder='array', categoryarray=current_batch, showline=True, linewidth=1.5, linecolor='black', mirror=True),
                    yaxis=dict(title="<b>耗用量</b>", gridcolor='#999999', gridwidth=1, zeroline=False, showline=True, linewidth=1.5, linecolor='black', mirror=True),
                    height=600, title=f"<b>第 {i+1} 組耗用對比</b>"
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        # --- TAB 3: DEVIATION CHART ---
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
                fig_dev.add_annotation(x=1.01, y=0, xref="paper", yref="y", text="<b>基準 0</b>", showarrow=False, xanchor="left", yanchor="middle", font=dict(color="black", size=14))
                
                fig_dev.update_layout(
                    plot_bgcolor='white', font=dict(color='black'), margin=dict(r=80),
                    xaxis=dict(dtick=1, tickangle=-90, categoryorder='array', categoryarray=current_batch, showline=True, linewidth=1.5, linecolor='black', mirror=True),
                    yaxis=dict(title="<b>差異量 (Δ耗用)</b>", gridcolor='#999999', gridwidth=1, zeroline=False, showline=True, linewidth=1.5, linecolor='black', mirror=True),
                    height=600, title=f"<b>第 {i+1} 組差異分析</b>"
                )
                st.plotly_chart(fig_dev, use_container_width=True)

        # --- TAB 4: PARETO CHART ---
        with viz_tab4:
            st.subheader("4. 異常超耗柏拉圖 (Pareto Chart) - 優先改善清單")
            st.info("💡 **決策重點：** 找出造成最多浪費的關鍵少數塗料 (80/20法則)。請優先處理累積曲線(藍線)前段的塗料。")
            
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            if not pareto_df.empty:
                pareto_df = pareto_df.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_pareto = pareto_df.head(40) # Hiển thị Top 40 để không bị chật

                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=top_pareto['塗料編號'], y=top_pareto['Δ耗用 (Deviation)'], name='超耗量 (單位)', marker_color='#d73027'))
                fig_pareto.add_trace(go.Scatter(x=top_pareto['塗料編號'], y=top_pareto['累計%'], name='累計影響 (%)', yaxis='y2', line=dict(color='#4575b4', width=3), mode='lines+markers'))

                fig_pareto.update_layout(
                    plot_bgcolor='white', font=dict(color='black'),
                    xaxis=dict(tickangle=-90, showline=True, linewidth=1.5, linecolor='black', mirror=True),
                    yaxis=dict(title="<b>超耗量</b>", showline=True, linewidth=1.5, linecolor='black', mirror=True, gridcolor='#999999'),
                    yaxis2=dict(title="<b>累計影響 (%)</b>", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=1.5, linecolor='black'),
                    height=650, title="<b>Top 40 超耗塗料排行</b>",
                    legend=dict(x=0.5, y=1.1, orientation="h", xanchor="center")
                )
                st.plotly_chart(fig_pareto, use_container_width=True)
            else:
                st.success("🎉 目前無超耗記錄，所有塗料皆達標或節省！")

        # --- TAB 5: BOX PLOTS ---
        with viz_tab5:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("5. 供應商穩定度分析 (Box Plot)")
                st.info("💡 **讀圖提示：** 觀察各廠商的績效分布範圍，**盒子越長代表品質越不穩定**。")
                if '油漆廠商' in filtered_df.columns and not filtered_df.empty:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", hover_data=['塗料編號'])
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red")
                    fig_box1.update_layout(
                        plot_bgcolor='white', font=dict(color='black'),
                        xaxis=dict(showline=True, linewidth=1.5, linecolor='black', mirror=True),
                        yaxis=dict(title="<b>合計績效 (%)</b>", showline=True, linewidth=1.5, linecolor='black', mirror=True, gridcolor='#999999'),
                        height=550
                    )
                    st.plotly_chart(fig_box1, use_container_width=True)

            with col2:
                st.subheader("6. 班別交叉分析")
                st.info("💡 **讀圖提示：** 比對不同班別(A/B/C/D)的作業績效，**尋找操作差異的根因**。")
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna(subset=['績效%'])
                    shift_df['班別'] = shift_df['班別'].str.replace('班績效%', '班')
                    
                    if not shift_df.empty:
                        fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all", hover_data=['塗料編號'])
                        fig_box2.add_hline(y=100, line_dash="dash", line_color="red")
                        fig_box2.update_layout(
                            plot_bgcolor='white', font=dict(color='black'),
                            xaxis=dict(showline=True, linewidth=1.5, linecolor='black', mirror=True),
                            yaxis=dict(title="<b>績效 (%)</b>", showline=True, linewidth=1.5, linecolor='black', mirror=True, gridcolor='#999999'),
                            height=550
                        )
                        st.plotly_chart(fig_box2, use_container_width=True)
                    else:
                        st.warning("無足夠班別數據")
                else:
                    st.warning("資料中未包含班別欄位")

        # --- RAW DATA ---
        with st.expander("🔍 檢視轉換後的底層資料 (Data View)"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"系統發生錯誤，請確認檔案格式是否正確。錯誤詳情：{e}")
else:
    st.info("👈 請於左側面板上傳您的資料集 (Data Source) 以驅動分析引擎。")
# --- 🌟 TÍNH NĂNG MỚI: TAB 6 PIE CHART ---
        with viz_tab6:
            st.subheader("7. 整體績效分佈佔比 (Pie Chart)")
            st.info("💡 **宏觀視角：** 快速檢視當前篩選條件下，各績效等級的塗料數量與比例。若紅色區塊過大，代表產線整體耗損嚴重。")
            
            pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
            if not pie_df.empty:
                # Đếm số lượng mã sơn theo từng nhóm màu
                pie_counts = pie_df['績效等級'].value_counts().reset_index()
                pie_counts.columns = ['績效等級', '塗料數量']
                
                # Vẽ biểu đồ Donut
                fig_pie = px.pie(
                    pie_counts, values='塗料數量', names='績效等級',
                    color='績效等級',
                    color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                    hole=0.4 # Biến thành Donut chart (có lỗ ở giữa) cho sang trọng
                )
                
                fig_pie.update_traces(
                    textposition='inside', 
                    textinfo='percent+label+value', # Hiển thị cả % + Tên nhãn + Số lượng
                    marker=dict(line=dict(color='white', width=2)), # Viền trắng giữa các lát cắt
                    textfont_size=14
                )
                
                fig_pie.update_layout(
                    plot_bgcolor='white', font=dict(color='black', size=14),
                    height=550, title="<b>塗料績效等級分佈 (總數與比例)</b>",
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.05)
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.warning("無有效的績效數據可供繪製。")

        with st.expander("🔍 數據明細"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"系統錯誤：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案。")
