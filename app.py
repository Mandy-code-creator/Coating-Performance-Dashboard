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
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # 核心計算
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        if '合計績效%' not in df.columns or df['合計績效%'].sum() == 0:
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, 0)
        
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # Phân cấp màu chuẩn
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {
            '🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000',
            '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'
        }

        # ==========================================
        # 🔥 [2. MODE SELECTOR]
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [2] 分析視角選擇")
        view_mode = st.sidebar.radio("選擇模式 (View Mode):", ["View 1: All Items", "View 2: Deviation ≥ 500"])

        if "View 2" in view_mode:
            df_active = df[df['Δ耗用 (Deviation)'] >= 500].copy()
            st.sidebar.warning(f"當前模式: 僅分析超耗 ≥ 500 的項目")
        else:
            df_active = df.copy()

        # Áp dụng Grade cho tập dữ liệu đang chọn
        conds = [df_active['合計績效%'] < 80, (df_active['合計績效%'] < 90), (df_active['合計績效%'] < 100), (df_active['合計績效%'] <= 110), df_active['合計績效%'] > 110]
        df_active['績效等級'] = np.select(conds, labels_global, default='未知')

        # Filters
        available_months = sorted(df_active['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=available_months, default=available_months[:1])
        df_s1 = df_active[df_active['年月'].isin(sel_month)]
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=sorted(df_s1['線別'].unique()), default=df_s1['線別'].unique())
        filtered_df = df_s1[df_s1['線別'].isin(sel_line)]

        # ==========================================
        # [ 3. VISUALIZATION ] 
        # ==========================================
        st.markdown(f"### 📈 績效分析結果 ({view_mode})")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [總覽]", "🚨 [決策]", "📦 [根因]", "🎯 [全景]", "📊 [明細] 耗用", "📉 [明細] 差異"
        ])

        common_layout = dict(
            plot_bgcolor='white', font=dict(color='black', family='Arial', size=13, weight='bold'),
            yaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True, gridcolor='#e6e6e6', title_font=dict(weight='bold'))
        )

        with tab_overview:
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                k1.metric("分析區間平均績效", f"{filtered_df['合計績效%'].mean():.2f}%")
                k2.metric("總差異耗用 (實際 - 理論)", f"{filtered_df['Δ耗用 (Deviation)'].sum():,.0f}", delta_color="inverse")
                k3.metric("塗料總數", f"{total_paints} 支")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            with col_pie:
                pie_counts = filtered_df['績效等級'].value_counts().reset_index()
                fig_pie = px.pie(pie_counts, values='count', names='績效等級', color='績效等級', color_discrete_map=perf_color_map, hole=0.4, category_orders={"績效等級": labels_global})
                fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', marker=dict(line=dict(color='black', width=2)), textfont_size=14)
                fig_pie.update_layout(title="<b>塗料績效等級比例</b>")
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_table:
                st.markdown("##### 🚨 Top 10 嚴重超耗清單")
                st.dataframe(filtered_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)[['塗料編號', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']].style.format({'合計績效%': '{:.2f}%', 'Δ耗用 (Deviation)': '{:,.0f}'}), hide_index=True)

        with tab_scatter:
            st.subheader(f"4. 塗料績效燈號全景 (共 {total_paints} 支)")
            plot_df = filtered_df[filtered_df['合計理論耗用'] > 0].copy()
            if not plot_df.empty:
                seq_map = {code: i+1 for i, code in enumerate(sort_order)}
                plot_df['Seq'] = plot_df['塗料編號'].map(seq_map)
                fig_sc = px.scatter(plot_df, x='Seq', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30, hover_name='塗料編號', category_orders={"績效等級": labels_global})
                
                # Chỉnh trục Y = 120 và Label không bị đè
                fig_sc.update_yaxes(range=[plot_df['合計績效%'].min()-5, 120])
                fig_sc.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                fig_sc.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                fig_sc.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                
                fig_sc.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, bgcolor="rgba(255,255,255,0.7)")
                fig_sc.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, bgcolor="rgba(255,255,255,0.7)")
                
                fig_sc.update_layout(**common_layout, height=700)
                fig_sc.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                st.plotly_chart(fig_sc, use_container_width=True)

        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index().sort_values(by='Δ耗用 (Deviation)', ascending=False)
            if not pareto_df.empty:
                pareto_df['Cum%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_p = pareto_df.head(40)
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(x=top_p['塗料編號'], y=top_p['Δ耗用 (Deviation)'], marker_color='#990000', name='超耗量'))
                fig_p.add_trace(go.Scatter(x=top_p['塗料編號'], y=top_p['Cum%'], yaxis='y2', line=dict(color='#00008B', width=3), name='累計%'))
                fig_p.update_layout(**common_layout, height=650, yaxis2=dict(overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'))
                fig_p.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_p, use_container_width=True)

        with tab_bar:
            for i in range(num_charts):
                batch_df = filtered_df[filtered_df['塗料編號'].isin(sort_order[i*40 : (i+1)*40])]
                fig_b = go.Figure()
                fig_b.add_trace(go.Bar(x=batch_df['塗料編號'], y=batch_df['合計理論耗用'], name='理論', marker_color='#34495e', marker_line_color='black', marker_line_width=1.5))
                fig_b.add_trace(go.Bar(x=batch_df['塗料編號'], y=batch_df['合計實際耗用'], name='實際', marker_color='#3498db', marker_line_color='black', marker_line_width=1.5))
                fig_b.update_layout(**common_layout, barmode='group', height=550)
                fig_b.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_b, use_container_width=True)

        with tab_dev:
            for i in range(num_charts):
                batch_df = filtered_df[filtered_df['塗料編號'].isin(sort_order[i*40 : (i+1)*40])].copy()
                batch_df['Color'] = np.where(batch_df['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_d = px.bar(batch_df, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#990000', '節省': '#008000'})
                fig_d.add_hline(y=0, line_color="black", line_width=2)
                fig_d.update_layout(**common_layout, height=550)
                fig_d.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_d, use_container_width=True)

        with st.expander("🔍 檢視底層明細資料 (Raw Data View)"):
            st.dataframe(filtered_df)

        # ==========================================
        # [ 4. HTML EXPORT ] - MIRRORING APP DESIGN
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [4] 快速匯出報表")
        if st.sidebar.button(f"📄 產生當前視角報表 ({view_mode})"):
            try:
                latest_month = filtered_df['年月'].max()
                html_content = f"""
                <html><head><meta charset='UTF-8'><style>
                    body {{ font-family: Segoe UI, sans-serif; padding: 20px; background: #f4f7f6; }}
                    .container {{ background: white; padding: 30px; border-radius: 10px; max-width: 1200px; margin: auto; }}
                    h1 {{ text-align: center; color: #2c3e50; border-bottom: 2px solid #3498db; }}
                    h2 {{ color: #e67e22; border-bottom: 1px dashed #ccc; padding: 5px; }}
                    .styled-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                    .styled-table thead tr {{ background: #009879; color: white; }}
                    .styled-table th, .styled-table td {{ padding: 10px; border: 1px solid #ddd; text-align: center; }}
                </style></head><body><div class='container'>
                    <h1>📊 塗料生產績效報告 - {latest_month}</h1>
                    <p style='text-align:center;'><b>模式: {view_mode}</b></p>
                """
                for line in sorted(filtered_df['線別'].unique()):
                    html_content += f"<h2>🏭 線別: {line}</h2>"
                    df_line = filtered_df[filtered_df['線別'] == line].copy()
                    
                    # Mirror Scatter Plot
                    fig_sc_exp = px.scatter(df_line, x='塗料編號', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30)
                    fig_sc_exp.update_yaxes(range=[df_line['合計績效%'].min()-5, 120])
                    fig_sc_exp.add_hline(y=100, line_dash="dash", line_color="red")
                    fig_sc_exp.update_layout(plot_bgcolor='white', height=600)
                    html_content += fig_sc_exp.to_html(full_html=False, include_plotlyjs='cdn')
                    
                    # Mirror Pareto Plot
                    pareto_exp = df_line[df_line['Δ耗用 (Deviation)'] > 0].sort_values(by='Δ耗用 (Deviation)', ascending=False).head(40)
                    if not pareto_exp.empty:
                        pareto_exp['Cum%'] = pareto_exp['Δ耗用 (Deviation)'].cumsum() / pareto_exp['Δ耗用 (Deviation)'].sum() * 100
                        fig_p_exp = go.Figure()
                        fig_p_exp.add_trace(go.Bar(x=pareto_exp['塗料編號'], y=pareto_exp['Δ耗用 (Deviation)'], marker_color='#990000', name='超耗'))
                        fig_p_exp.add_trace(go.Scatter(x=pareto_exp['塗料編號'], y=pareto_exp['Cum%'], yaxis='y2', line=dict(color='#00008B', width=3), name='累計%'))
                        fig_p_exp.update_layout(plot_bgcolor='white', height=600, yaxis2=dict(overlaying='y', side='right', range=[0, 105]))
                        html_content += "<h3>🚨 異常超耗柏拉圖</h3>" + fig_p_exp.to_html(full_html=False, include_plotlyjs='cdn')

                    # Top 10 Table
                    html_content += "<h3>📋 嚴重超耗清單 (Top 10)</h3><table class='styled-table'><thead><tr><th>塗料編號</th><th>績效%</th><th>超耗量 (kg)</th></tr></thead><tbody>"
                    for _, row in df_line.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10).iterrows():
                        html_content += f"<tr><td>{row['塗料編號']}</td><td>{row['合計績效%']:.2f}%</td><td>{row['Δ耗用 (Deviation)']:,.0f}</td></tr>"
                    html_content += "</tbody></table>"

                html_content += "</div></body></html>"
                st.sidebar.download_button("📥 下載報表", data=html_content.encode('utf-8'), file_name=f"Performance_Report_{latest_month}.html", mime="text/html")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 請上傳 MES 數據檔案以開始分析。")
