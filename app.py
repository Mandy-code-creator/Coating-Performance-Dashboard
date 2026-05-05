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
st.markdown("<b>依據 MES/Excel 數據進行系統化分析 (高階決策最佳化佈局)</b>", unsafe_allow_html=True)

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
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 核心邏輯計算
        if '合計績效%' not in df.columns or df['合計績效%'].isnull().all() or (df['合計績效%'] == 0).all():
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # 績效等級與配色
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {
            '🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000',
            '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'
        }
        
        # ==========================================
        # 🔥 [新增模式切換]：View 1 vs View 2
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [模式切換] 分析視角")
        view_mode = st.sidebar.radio(
            "請選擇分析視角：",
            ["View 1: 全體分析 (All Items)", 
             "View 2: 嚴重超耗分析 (Δ耗用 > 500)"],
            index=0
        )

        if "View 2" in view_mode:
            df_active = df[df['Δ耗用 (Deviation)'] > 500].copy()
            st.sidebar.warning(f"目前處於 View 2：僅分析超耗 > 500 的 {len(df_active)} 支塗料。")
        else:
            df_active = df.copy()
            st.sidebar.success(f"目前處於 View 1：分析全體 {len(df_active)} 支塗料。")

        # 根據活躍資料更新等級
        conds_global = [
            df_active['合計績效%'] < 80, 
            (df_active['合計績效%'] >= 80) & (df_active['合計績效%'] < 90), 
            (df_active['合計績效%'] >= 90) & (df_active['合計績效%'] < 100), 
            (df_active['合計績效%'] >= 100) & (df_active['合計績效%'] <= 110),
            df_active['合計績效%'] > 110
        ]
        df_active['績效等級'] = np.select(conds_global, labels_global, default='未知')

        # ==========================================
        # [ 2. DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        available_months = sorted(df_active['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=available_months, default=available_months[:1])
        df_s1 = df_active[df_active['年月'].isin(sel_month)]
        
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=sorted(df_s1['線別'].unique()), default=df_s1['線別'].unique())
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        sel_usage = st.sidebar.multiselect("3. 選擇用途", options=sorted(df_s2['用途'].unique()), default=df_s2['用途'].unique())
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 3. VISUALIZATION ] 
        # ==========================================
        st.markdown(f"### 📈 視覺化分析與根因探討 ({view_mode})")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [總覽] 績效分佈", "🚨 [決策] 優先改善清單", "📦 [根因] 穩定度分析", 
            "🎯 [全景] 績效燈號", "📊 [明細] 耗用對比", "📉 [明細] 差異分析"
        ])

        common_layout = dict(
            plot_bgcolor='white',
            font=dict(color='black', family='Arial', size=13, weight='bold'),
            yaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True, gridcolor='#e6e6e6', title_font=dict(weight='bold'))
        )

        with tab_overview:
            st.subheader("1. 產線整體績效總覽與行動清單")
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                avg_perf = filtered_df['合計績效%'].mean()
                total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
                k1.metric("分析區間平均績效", f"{avg_perf:.2f}%")
                k2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f}", delta_color="inverse")
                k3.metric("分析區間內塗料總數", f"{total_paints} 支")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            with col_pie:
                pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
                if not pie_df.empty:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '塗料數量']
                    fig_pie = px.pie(pie_counts, values='塗料數量', names='績效等級', color='績效等級',
                                     color_discrete_map=perf_color_map, hole=0.4, category_orders={"績效等級": labels_global})
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', marker=dict(line=dict(color='black', width=2)), textfont_size=14)
                    fig_pie.update_layout(title="<b>塗料績效等級比例 (Performance Distribution)</b>", showlegend=True)
                    st.plotly_chart(fig_pie, use_container_width=True)
            with col_table:
                st.markdown("##### 🚨 Top 10 嚴重超耗塗料清單")
                over_used_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].copy()
                if not over_used_df.empty:
                    decision_table = over_used_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)
                    show_cols = ['塗料編號', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']
                    decision_table = decision_table[show_cols]
                    decision_table.columns = ['塗料編號 (Paint ID)', '油漆廠商 (Supplier)', '線別 (Line)', '合計績效 (%)', '🔥 超耗量 (Over-used)']
                    st.dataframe(decision_table.style.format({'合計績效 (%)': '{:.2f}%', '🔥 超耗量 (Over-used)': '{:,.0f}'}), use_container_width=True, hide_index=True)

        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            if not pareto_df.empty:
                pareto_df = pareto_df.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_pareto = pareto_df.head(40)
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=top_pareto['塗料編號'], y=top_pareto['Δ耗用 (Deviation)'], name='超耗量', marker_color='#990000'))
                fig_pareto.add_trace(go.Scatter(x=top_pareto['塗料編號'], y=top_pareto['累計%'], name='累計%', yaxis='y2', line=dict(color='#00008B', width=3)))
                fig_pareto.update_layout(**common_layout)
                fig_pareto.update_layout(height=650, title="<b>Top 40 成本流失最大塗料排行</b>",
                                         yaxis2=dict(title="累計%", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'))
                fig_pareto.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True, tickangle=-90, automargin=True)
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_rootcause:
            st.subheader("3. 穩定度分析 (Stability Analysis)")
            col1, col2 = st.columns(2)
            NO_RED_PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#7f7f7f', '#bcbd22', '#17becf']
            with col1:
                if '油漆廠商' in filtered_df.columns and not filtered_df.empty:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box1.update_layout(**common_layout, height=550, title="<b>供應商品質穩定度</b>", showlegend=False)
                    st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna()
                    if not shift_df.empty:
                        fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all", color_discrete_sequence=NO_RED_PALETTE)
                        fig_box2.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                        fig_box2.update_layout(**common_layout, height=550, title="<b>班別操作穩定度</b>", showlegend=False)
                        st.plotly_chart(fig_box2, use_container_width=True)

        with tab_scatter:
            st.subheader(f"4. 塗料績效燈號全景總覽 (共 {total_paints} 支)")
            plot_df = filtered_df.dropna(subset=['合計理論耗用', '合計績效%']).copy()
            plot_df = plot_df[plot_df['合計理論耗用'] > 0]
            if not plot_df.empty:
                seq_map = {code: i+1 for i, code in enumerate(sort_order)}
                plot_df['塗料序號'] = plot_df['塗料編號'].map(seq_map)
                fig = px.scatter(plot_df, x='塗料序號', y='合計績效%', color='績效等級',
                                 color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30,
                                 category_orders={"績效等級": labels_global}, hover_name='塗料編號')
                
                # --- [FIXED] Y軸範圍設定 (至 120) ---
                y_min = plot_df['合計績效%'].min() - 5
                y_max = max(120, plot_df['合計績效%'].max() + 5)
                fig.update_yaxes(range=[y_min, y_max])
                
                fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                fig.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                fig.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                
                # --- [FIXED] 避免字體重疊，增加 yshift 與 bgcolor ---
                fig.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, font=dict(color="red", size=14), bgcolor="rgba(255,255,255,0.7)")
                fig.add_annotation(x=0.99, y=90, xref="paper", yref="y", text="<b>90% Bound</b>", showarrow=False, xanchor="right", yanchor="top", yshift=-5, font=dict(color="deepskyblue", size=13), bgcolor="rgba(255,255,255,0.7)")
                fig.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, font=dict(color="deepskyblue", size=13), bgcolor="rgba(255,255,255,0.7)")
                
                fig.update_layout(**common_layout, height=700, title="<b>全廠塗料績效分佈圖 (Overall Performance Scatter)</b>")
                fig.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                st.plotly_chart(fig, use_container_width=True)

        with tab_bar:
            st.subheader("5. 單一塗料：理論耗用 vs 實際耗用明細")
            for i in range(num_charts):
                batch_codes = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch_codes)]
                df_bar = batch_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論', marker_color='#34495e'))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際', marker_color='#3498db'))
                fig_bar.update_layout(**common_layout, barmode='group', height=550, title=f"<b>第 {i+1} 組耗用對比</b>")
                fig_bar.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True, tickangle=-90, automargin=True)
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            st.subheader("6. 單一塗料：耗用差異絕對值")
            for i in range(num_charts):
                batch_codes = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch_codes)].copy()
                batch_df['Color'] = np.where(batch_df['Δ耗用 (Deviation)'] > 0, '超耗 (Over)', '節省 (Save)')
                fig_dev = px.bar(batch_df, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', 
                                 color_discrete_map={'超耗 (Over)': '#990000', '節省 (Save)': '#008000'})
                fig_dev.add_hline(y=0, line_color="black", line_width=2)
                fig_dev.update_layout(**common_layout, height=550, title=f"<b>第 {i+1} 組差異明細</b>")
                fig_dev.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True, tickangle=-90, automargin=True)
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 檢視底層明細資料 (Raw Data View)"):
            st.dataframe(filtered_df)

        # ==========================================
        # ==========================================
        # [ 4. EXPORT REPORT TO HTML ]
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [4] 快速匯出報表 (HTML Export)")
        
        # Thêm nút chọn View cho báo cáo
        report_view_sel = st.sidebar.radio(
            "選擇報表內容 (Select Report Content):",
            ["View 1: All Items", "View 2: Deviation > 500"],
            key="report_export_view"
        )
        
        if st.sidebar.button("📄 產生 HTML 報表 (Generate Report)"):
            try:
                latest_month = df['年月'].dropna().max()
                # Lọc theo tháng và mục đích sử dụng ban đầu
                df_word = df[(df['用途'] == '正面漆') & (df['年月'] == latest_month)].copy()
                
                # 🔥 Áp dụng logic lọc theo lựa chọn của người dùng
                if "View 2" in report_view_sel:
                    df_word = df_word[df_word['Δ耗用 (Deviation)'] > 500]
                    report_title_suffix = "(Deviation > 500)"
                else:
                    report_title_suffix = "(Full Report)"

                if df_word.empty:
                    st.sidebar.error("❌ 該視角下找不到數據。(No data for selected view)")
                else:
                    lines = sorted(df_word['線別'].unique())
                    html_content = f"""
                    <html>
                    <head>
                        <meta charset='UTF-8'>
                        <title>Performance Report {report_title_suffix}</title>
                        <style>
                            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; background-color: #f4f7f6; }}
                            .container {{ background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 1200px; margin: auto; }}
                            h1 {{ color: #2c3e50; text-align: center; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                            h2 {{ color: #e67e22; margin-top: 50px; border-bottom: 1px dashed #ccc; padding-bottom: 5px; }}
                            h3 {{ color: #34495e; margin-top: 30px; }}
                            .styled-table {{ border-collapse: collapse; margin: 25px 0; font-size: 0.9em; width: 100%; box-shadow: 0 0 20px rgba(0, 0, 0, 0.15); }}
                            .styled-table thead tr {{ background-color: #009879; color: #ffffff; text-align: center; }}
                            .styled-table th, .styled-table td {{ padding: 12px 15px; border: 1px solid #ddd; text-align: center; }}
                            .styled-table tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}
                        </style>
                    </head>
                    <body>
                    <div class="container">
                        <h1>📊 塗料生產績效報告 - {latest_month} {report_title_suffix}</h1>
                    """
                    
                    for line in lines:
                        html_content += f"<h2>🏭 線別 (Line): {line}</h2>"
                        df_line = df_word[df_word['線別'] == line].copy()
                        
                        sort_order_line = df_line.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
                        total_paints_line = len(sort_order_line)
                        
                        # --- 1. SCATTER PLOT (HTML Export) ---
                        plot_df_line = df_line.dropna(subset=['合計理論耗用', '合計績效%']).copy()
                        plot_df_line = plot_df_line[plot_df_line['合計理論耗用'] > 0]
                        if not plot_df_line.empty:
                            seq_map_line = {code: i+1 for i, code in enumerate(sort_order_line)}
                            plot_df_line['塗料序號'] = plot_df_line['塗料編號'].map(seq_map_line)
                            
                            fig_line = px.scatter(plot_df_line, x='塗料序號', y='合計績效%', color='績效等級',
                                                color_discrete_map=perf_color_map, 
                                                size='合計理論耗用', size_max=30,
                                                category_orders={"績效等級": labels_global},
                                                hover_name='塗料編號')
                            
                            # Đồng bộ cấu trúc Y-axis 120 và Label như màn hình chính
                            y_min_exp = plot_df_line['合計績效%'].min() - 5
                            y_max_exp = max(120, plot_df_line['合計績效%'].max() + 5)
                            fig_line.update_yaxes(range=[y_min_exp, y_max_exp])
                            
                            fig_line.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                            fig_line.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                            fig_line.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                            
                            fig_line.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, font=dict(color="red", size=14), bgcolor="rgba(255,255,255,0.7)")
                            fig_line.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, font=dict(color="deepskyblue", size=13), bgcolor="rgba(255,255,255,0.7)")

                            fig_line.update_layout(**common_layout)
                            fig_line.update_layout(height=700, title=f"<b>Line {line} Performance Map</b>")
                            html_content += fig_line.to_html(full_html=False, include_plotlyjs='cdn')
                        
                        # --- 2. PARETO CHART (HTML Export) ---
                        html_content += f"<h3>🚨 異常超耗柏拉圖 (Pareto Priority)</h3>"
                        # ... (Giữ nguyên logic Pareto hiện tại của bạn)
                        
                        # --- 3. TOP 10 TABLE (HTML Export) ---
                        html_content += f"<h3>📋 Top 10 嚴重超耗清單</h3>"
                        # ... (Giữ nguyên logic Table hiện tại của bạn)
                        
                    html_content += "</div></body></html>"
                    st.sidebar.download_button("📥 下載報表 (Download HTML)", data=html_content.encode('utf-8'), file_name=f"Report_{latest_month}.html", mime="text/html")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")
