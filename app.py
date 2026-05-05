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

        if '合計績效%' not in df.columns or df['合計績效%'].isnull().all() or (df['合計績效%'] == 0).all():
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ COLOR MAP & GRADING ] - Tạo sẵn trên df gốc để tránh lỗi cột
        # ==========================================
        conds_global = [
            df['合計績效%'] < 80, 
            (df['合計績效%'] >= 80) & (df['合計績效%'] < 90), 
            (df['合計績效%'] >= 90) & (df['合計績效%'] < 100), 
            (df['合計績效%'] >= 100) & (df['合計績效%'] <= 110),
            df['合計績效%'] > 110
        ]
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {'🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000', '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'}
        df['績效等級'] = np.select(conds_global, labels_global, default='未知')

        # ==========================================
        # 🔥 [VIEW SWITCH] - CHỌN VIEW 1 HOẶC VIEW 2
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [模式切換] 分析視角")
        view_mode = st.sidebar.radio("選擇模式 (View):", ["View 1: All Items (全體)", "View 2: Deviation > 500 (超耗 > 500)"])

        if "View 2" in view_mode:
            df_active = df[df['Δ耗用 (Deviation)'] > 500].copy()
            st.sidebar.warning(f"目前顯示: View 2 (共 {len(df_active)} 支)")
        else:
            df_active = df.copy()
            st.sidebar.success(f"目前顯示: View 1 (共 {len(df_active)} 支)")

        # ==========================================
        # [ 2. DASHBOARD FILTER ] - Áp dụng trên df_active
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
                k1.metric("平均總績效 (理論值基準)", f"{avg_perf:.2f}%")
                k2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f}", delta_color="inverse")
                k3.metric("分析區間內塗料總數", f"{total_paints} 支")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            with col_pie:
                pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
                if not pie_df.empty:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '塗料數量']
                    fig_pie = px.pie(pie_counts, values='塗料數量', names='績效等級', color='績效等級', color_discrete_map=perf_color_map, hole=0.4, category_orders={"績效等級": labels_global})
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', marker=dict(line=dict(color='black', width=2)), textfont_size=14)
                    fig_pie.update_layout(title="<b>塗料績效等級比例 (Performance Distribution)</b>", showlegend=True, font=dict(weight='bold', color='black'))
                    st.plotly_chart(fig_pie, use_container_width=True)
            with col_table:
                st.markdown("##### 🚨 Top 10 嚴重超耗塗料清單 (Top 10 Over-consumption)")
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
                fig_pareto.add_trace(go.Bar(x=top_pareto['塗料編號'], y=top_pareto['Δ耗用 (Deviation)'], name='超耗量 (Over-used)', marker_color='#990000'))
                fig_pareto.add_trace(go.Scatter(x=top_pareto['塗料編號'], y=top_pareto['累計%'], name='累計% (Cumulative %)', yaxis='y2', line=dict(color='#00008B', width=3)))
                fig_pareto.update_layout(**common_layout)
                fig_pareto.update_layout(xaxis=dict(title=dict(text="<b>塗料編號 (Paint ID)</b>", standoff=40), tickangle=-90, automargin=True),
                                         yaxis=dict(title="<b>超耗量 (Over-used Volume)</b>"),
                                         yaxis2=dict(title="<b>累計% (Cumulative %)</b>", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'),
                                         height=650, title="<b>Top 40 成本流失最大塗料排行 (Top 40 Highest Cost Loss)</b>", showlegend=True, margin=dict(b=160))
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_rootcause:
            st.subheader("3. 穩定度分析 (Stability Analysis)")
            col1, col2 = st.columns(2)
            NO_RED_PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#7f7f7f', '#bcbd22', '#17becf']
            with col1:
                if '油漆廠商' in filtered_df.columns and not filtered_df.empty:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box1.update_layout(**common_layout, height=550, title="<b>供應商品質穩定度 (Supplier QC)</b>", xaxis_title="<b>油漆廠商 (Supplier)</b>", yaxis_title="<b>合計績效 (%)</b>", showlegend=False)
                    st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna(subset=['績效%'])
                    shift_df['班別'] = shift_df['班別'].str.replace('班績效%', '班')
                    if not shift_df.empty:
                        fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                        fig_box2.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                        fig_box2.update_layout(**common_layout, height=550, title="<b>班別操作穩定度 (Shift Operations)</b>", xaxis_title="<b>班別 (Shift)</b>", yaxis_title="<b>績效 (%)</b>", showlegend=False)
                        st.plotly_chart(fig_box2, use_container_width=True)

        with tab_scatter:
            st.subheader(f"4. 塗料績效燈號全景總覽 (共 {total_paints} 支)")
            if not filtered_df.empty:
                plot_df = filtered_df.dropna(subset=['合計理論耗用', '合計績效%']).copy()
                plot_df = plot_df[plot_df['合計理論耗用'] > 0]
                if not plot_df.empty:
                    seq_map = {code: i+1 for i, code in enumerate(sort_order)}
                    plot_df['塗料序號'] = plot_df['塗料編號'].map(seq_map)
                    fig = px.scatter(plot_df, x='塗料序號', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30, category_orders={"績效等級": labels_global}, hover_name='塗料編號')
                    
                    # 🔥 [FIX] Chỉnh trục Y lên 120 và xử lý label bị đè
                    fig.update_yaxes(range=[plot_df['合計績效%'].min() - 5, 120])
                    fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                    fig.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                    
                    fig.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, bgcolor="rgba(255,255,255,0.7)", font=dict(color="red", size=16))
                    fig.add_annotation(x=0.99, y=90, xref="paper", yref="y", text="<b>90% Bound</b>", showarrow=False, xanchor="right", yanchor="top", yshift=-5, bgcolor="rgba(255,255,255,0.7)", font=dict(color="deepskyblue", size=13))
                    fig.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, bgcolor="rgba(255,255,255,0.7)", font=dict(color="deepskyblue", size=13))

                    fig.update_layout(**common_layout, height=700, title="<b>全廠塗料績效分佈圖 (Overall Performance Scatter)</b>", xaxis=dict(title=f"<b>塗料排序序號 - 總計: {total_paints} 支</b>", showline=True, linewidth=2, linecolor='black', mirror=True))
                    fig.update_traces(marker=dict(line=dict(width=1, color='black')))
                    st.plotly_chart(fig, use_container_width=True)

        with tab_bar:
            st.subheader("5. 單一塗料：理論耗用 vs 實際耗用明細")
            for i in range(num_charts):
                batch_codes = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch_codes)]
                df_bar = batch_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論 (Theoretical)', marker_color='#34495e', marker_line_color='black', marker_line_width=1.5))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際 (Actual)', marker_color='#3498db', marker_line_color='black', marker_line_width=1.5))
                fig_bar.update_layout(**common_layout)
                fig_bar.update_layout(barmode='group', height=550, title=f"<b>第 {i+1} 組耗用對比 (Group {i+1})</b>", xaxis=dict(title="<b>塗料編號 (Paint ID)</b>", tickangle=-90, automargin=True), yaxis=dict(title="<b>耗用量 (Consumption)</b>"), margin=dict(b=160))
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            st.subheader("6. 單一塗料：耗用差異絕對值")
            for i in range(num_charts):
                batch_codes = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch_codes)].copy()
                df_dev = batch_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗 (Over)', '節省 (Save)')
                fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗 (Over)': '#990000', '節省 (Save)': '#008000'})
                fig_dev.add_hline(y=0, line_color="black", line_width=2)
                fig_dev.update_layout(**common_layout)
                fig_dev.update_layout(height=550, title=f"<b>第 {i+1} 組差異明細 (Group {i+1})</b>", xaxis=dict(title="<b>塗料編號 (Paint ID)</b>", tickangle=-90, automargin=True), yaxis=dict(title="<b>差異量 (Deviation)</b>"), margin=dict(b=160))
                fig_dev.update_traces(marker=dict(line=dict(width=1.5, color='black')))
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 檢視底層明細資料 (Raw Data View)"):
            st.dataframe(filtered_df)

        # ==========================================
        # [ 4. EXPORT REPORT TO HTML ]
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [4] 快速匯出報表 (HTML Export)")
        export_choice = st.sidebar.radio("選擇匯出視角 (Choose Export View):", ["Export View 1 (All)", "Export View 2 (>500)"])
        
        if st.sidebar.button("📄 產生 HTML 報表 (Generate Report)"):
            try:
                latest_month = df['年月'].dropna().max()
                # Chọn dữ liệu nguồn theo export_choice
                if "View 2" in export_choice:
                    df_for_html = df[(df['用途'] == '正面漆') & (df['年月'] == latest_month) & (df['Δ耗用 (Deviation)'] > 500)].copy()
                else:
                    df_for_html = df[(df['用途'] == '正面漆') & (df['年月'] == latest_month)].copy()
                
                if df_for_html.empty:
                    st.sidebar.error("❌ 找不到選定視角的數據。")
                else:
                    lines = sorted(df_for_html['線別'].unique())
                    html_content = f"<html><head><meta charset='UTF-8'><style>body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }} .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 1200px; margin: auto; }} h1 {{ text-align: center; color: #2c3e50; border-bottom: 2px solid #3498db; }} h2 {{ color: #e67e22; border-bottom: 1px dashed #ccc; }} .styled-table {{ border-collapse: collapse; margin: 25px 0; width: 100%; }} .styled-table thead tr {{ background-color: #009879; color: white; }} .styled-table th, .styled-table td {{ padding: 12px 15px; border: 1px solid #ddd; text-align: center; }} .styled-table tbody tr:nth-of-type(even) {{ background-color: #f3f3f3; }}</style></head><body><div class='container'><h1>📊 塗料生產績效報告 - {latest_month}</h1><p style='text-align:center;'><b>分析模式: {export_choice}</b></p>"
                    
                    for line in lines:
                        html_content += f"<h2>🏭 線別 (Line): {line}</h2>"
                        df_line = df_for_html[df_for_html['線別'] == line].copy()
                        sort_order_line = df_line.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
                        
                        # Scatter Plot HTML
                        plot_df_line = df_line[df_line['合計理論耗用'] > 0].copy()
                        if not plot_df_line.empty:
                            seq_map_line = {code: i+1 for i, code in enumerate(sort_order_line)}
                            plot_df_line['塗料序號'] = plot_df_line['塗料編號'].map(seq_map_line)
                            fig_line = px.scatter(plot_df_line, x='塗料序號', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30, category_orders={"績效等級": labels_global}, hover_name='塗料編號')
                            fig_line.update_yaxes(range=[plot_df_line['合計績效%'].min()-5, 120])
                            fig_line.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                            fig_line.update_layout(plot_bgcolor='white', height=700, title=f"<b>Line {line} 績效概覽</b>")
                            html_content += fig_line.to_html(full_html=False, include_plotlyjs='cdn')
                        
                        # Pareto HTML
                        pareto_df_line = df_line[df_line['Δ耗用 (Deviation)'] > 0].sort_values(by='Δ耗用 (Deviation)', ascending=False)
                        if not pareto_df_line.empty:
                            pareto_df_line['累計%'] = pareto_df_line['Δ耗用 (Deviation)'].cumsum() / pareto_df_line['Δ耗用 (Deviation)'].sum() * 100
                            fig_p = go.Figure()
                            fig_p.add_trace(go.Bar(x=pareto_df_line.head(40)['塗料編號'], y=pareto_df_line.head(40)['Δ耗用 (Deviation)'], marker_color='#990000', name='超耗'))
                            fig_p.add_trace(go.Scatter(x=pareto_df_line.head(40)['塗料編號'], y=pareto_df_line.head(40)['累計%'], yaxis='y2', line=dict(color='#00008B', width=3), name='累計%'))
                            fig_p.update_layout(plot_bgcolor='white', height=600, yaxis2=dict(overlaying='y', side='right', range=[0, 105]))
                            html_content += f"<h3>🚨 異常超耗柏拉圖</h3>" + fig_p.to_html(full_html=False, include_plotlyjs='cdn')

                        # Table HTML
                        html_content += f"<h3>📋 Top 10 嚴重超耗清單</h3><table class='styled-table'><thead><tr><th>塗料編號</th><th>油漆廠商</th><th>合計績效%</th><th>🔥 超耗量</th></tr></thead><tbody>"
                        for _, row in df_line.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10).iterrows():
                            html_content += f"<tr><td>{row['塗料編號']}</td><td>{row['油漆廠商']}</td><td>{row['合計績效%']:.2f}%</td><td>{row['Δ耗用 (Deviation)']:,.0f}</td></tr>"
                        html_content += "</tbody></table>"
                        
                    html_content += "</div></body></html>"
                    st.sidebar.download_button("📥 下載報表 (Download HTML)", data=html_content.encode('utf-8'), file_name=f"Report_{latest_month}.html", mime="text/html")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

    except Exception as e:
        st.error(f"System Error：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案。(Please upload MES Data file)")
