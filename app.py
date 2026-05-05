import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# [ 0. PAGE CONFIG & CSS ] - GIỮ NGUYÊN BẢN GỐC
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

        # [ COLOR MAP LOGIC ]
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {'🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000', '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'}
        
        # Thêm cột Grade vào df gốc để đảm bảo Export không bị lỗi
        conds_init = [df['合計績效%'] < 80, (df['合計績效%'] < 90), (df['合計績效%'] < 100), (df['合計績效%'] <= 110), df['合計績效%'] > 110]
        df['績效等級'] = np.select(conds_init, labels_global, default='未知')

        # ==========================================
        # 🔥 [VIEW SWITCH] - Mandy's Requirement
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [模式切換] 分析視角")
        view_mode = st.sidebar.radio("選擇模式 (View):", ["View 1: All Items (全體)", "View 2: Deviation > 500 (超耗 > 500)"])

        if "View 2" in view_mode:
            df_active = df[df['Δ耗用 (Deviation)'] >= 500].copy()
        else:
            df_active = df.copy()

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
        # [ 3. VISUALIZATION ] - GIỮ NGUYÊN 6 TAB NGUYÊN BẢN
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
                k1.metric("平均總績效 (理論值基準)", f"{filtered_df['合計績效%'].mean():.2f}%")
                k2.metric("總差異耗用 (實際 - 理論)", f"{filtered_df['Δ耗用 (Deviation)'].sum():,.0f}", delta_color="inverse")
                k3.metric("分析區間內塗料總數", f"{total_paints} 支")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            with col_pie:
                pie_counts = filtered_df['績效等級'].value_counts().reset_index()
                fig_pie = px.pie(pie_counts, values='count', names='績效等級', color='績效等級',
                                 color_discrete_map=perf_color_map, hole=0.4, category_orders={"績效等級": labels_global})
                fig_pie.update_traces(textposition='inside', textinfo='percent+label+value', marker=dict(line=dict(color='black', width=2)))
                fig_pie.update_layout(title="<b>塗料績效等級比例 (Performance Distribution)</b>", showlegend=True)
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_table:
                st.markdown("##### 🚨 Top 10 嚴重超耗塗料清單 (Top 10 Over-consumption)")
                st.dataframe(filtered_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)[['塗料編號', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']].style.format({'合計績效%': '{:.2f}%', 'Δ耗用 (Deviation)': '{:,.0f}'}), use_container_width=True, hide_index=True)

        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index().sort_values(by='Δ耗用 (Deviation)', ascending=False)
            if not pareto_df.empty:
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_p = pareto_df.head(40)
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=top_p['塗料編號'], y=top_p['Δ耗用 (Deviation)'], name='超耗量 (Over-used)', marker_color='#990000'))
                fig_pareto.add_trace(go.Scatter(x=top_p['塗料編號'], y=top_p['累計%'], name='累計% (Cumulative %)', yaxis='y2', line=dict(color='#00008B', width=3)))
                fig_pareto.update_layout(**common_layout)
                fig_pareto.update_layout(xaxis=dict(tickangle=-90), yaxis2=dict(title="<b>累計% (Cumulative %)</b>", overlaying='y', side='right', range=[0, 105], showline=True, linewidth=2, linecolor='black'))
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_rootcause:
            st.subheader("3. 穩定度分析 (Stability Analysis)")
            col1, col2 = st.columns(2)
            pal = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#7f7f7f', '#bcbd22', '#17becf']
            with col1:
                fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", color_discrete_sequence=pal)
                fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                fig_box1.update_layout(**common_layout, title="<b>供應商品質穩定度 (Supplier QC)</b>")
                st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                s_cols = [c for c in filtered_df.columns if '班績效%' in c]
                if s_cols:
                    s_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=s_cols, var_name='班別', value_name='績效%').dropna()
                    fig_box2 = px.box(s_df, x='班別', y='績效%', color='班別', points="all", color_discrete_sequence=pal)
                    fig_box2.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                    fig_box2.update_layout(**common_layout, title="<b>班別操作穩定度 (Shift Operations)</b>")
                    st.plotly_chart(fig_box2, use_container_width=True)

        with tab_scatter:
            st.subheader(f"4. 塗料績效燈號全景總覽 (共 {total_paints} 支)")
            if not filtered_df.empty:
                plot_df = filtered_df[filtered_df['合計理論耗用'] > 0].copy()
                seq_map = {code: i+1 for i, code in enumerate(sort_order)}
                plot_df['塗料序號'] = plot_df['塗料編號'].map(seq_map)
                fig = px.scatter(plot_df, x='塗料序號', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, 
                                 size='合計理論耗用', size_max=30, category_orders={"績效等級": labels_global}, hover_name='塗料編號')
                
                # 🔥 [FIX] Trục Y lên 120 và Label có nền trắng
                fig.update_yaxes(range=[max(0, plot_df['合計績效%'].min() - 10), 120])
                fig.add_hline(y=100, line_dash="dash", line_color="red", line_width=3)
                fig.add_hline(y=90, line_dash="dot", line_color="deepskyblue", line_width=2)
                fig.add_hline(y=110, line_dash="dot", line_color="deepskyblue", line_width=2)
                fig.add_annotation(x=0.99, y=100, xref="paper", yref="y", text="<b>🎯 Target: 100%</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=8, bgcolor="rgba(255,255,255,0.8)", font=dict(color="red", size=14))
                fig.add_annotation(x=0.99, y=110, xref="paper", yref="y", text="<b>110% Bound</b>", showarrow=False, xanchor="right", yanchor="bottom", yshift=5, bgcolor="rgba(255,255,255,0.8)", font=dict(color="deepskyblue", size=12))

                fig.update_layout(**common_layout, height=700, title="<b>全廠塗料績效分佈圖 (Overall Performance Scatter)</b>")
                fig.update_xaxes(showline=True, linewidth=2, linecolor='black', mirror=True)
                fig.update_traces(marker=dict(line=dict(width=1, color='black')))
                st.plotly_chart(fig, use_container_width=True)
                
                st.info("💡 **Chấm LỚN:** Lượng dùng lý thuyết cao (Mã trọng điểm). **Chấm ĐỎ:** Hiệu suất thấp, cần ưu tiên xử lý.")

        with tab_bar:
            st.subheader("5. 單一塗料：理論耗用 vs 實際耗用明細")
            for i in range(num_charts):
                batch = filtered_df[filtered_df['塗料編號'].isin(sort_order[i*40 : (i+1)*40])]
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=batch['塗料編號'], y=batch['合計理論耗用'], name='理論 (Theoretical)', marker_color='#34495e', marker_line_color='black', marker_line_width=1.5))
                fig_bar.add_trace(go.Bar(x=batch['塗料編號'], y=batch['合計實際耗用'], name='實際 (Actual)', marker_color='#3498db', marker_line_color='black', marker_line_width=1.5))
                fig_bar.update_layout(**common_layout, barmode='group', height=550)
                fig_bar.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            st.subheader("6. 單一塗料：耗用差異絕對值")
            for i in range(num_charts):
                batch = filtered_df[filtered_df['塗料編號'].isin(sort_order[i*40 : (i+1)*40])].copy()
                batch['Color'] = np.where(batch['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(batch, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#990000', '節省': '#008000'})
                fig_dev.add_hline(y=0, line_color="black", line_width=2)
                fig_dev.update_layout(**common_layout, height=550)
                fig_dev.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_dev, use_container_width=True)

        with st.expander("🔍 檢視底層明細資料 (Raw Data View)"):
            st.dataframe(filtered_df)

        # ==========================================
        # [ 4. EXPORT REPORT TO HTML ] - KHÔI PHỤC LOGIC GỐC + SYNC DESIGN
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [4] 快速匯出報表")
        export_sel = st.sidebar.radio("選擇匯出視角:", ["Mirror Current View (當前視角)", "All Data (View 1)", "High Deviation (View 2)"])
        
        if st.sidebar.button("📄 產生 HTML 報表"):
            try:
                latest_m = df['年月'].dropna().max()
                # Chọn data dựa trên export_sel
                if "View 2" in export_sel:
                    df_word = df[(df['用途'] == '正面漆') & (df['年月'] == latest_m) & (df['Δ耗用 (Deviation)'] >= 500)].copy()
                elif "View 1" in export_sel:
                    df_word = df[(df['用途'] == '正面漆') & (df['年月'] == latest_m)].copy()
                else:
                    df_word = filtered_df[filtered_df['用途'] == '正面漆'].copy()

                if df_word.empty: st.sidebar.error("❌ 找不到可匯出的數據。")
                else:
                    html_content = f"<html><head><meta charset='UTF-8'><style>body {{ font-family: Segoe UI, sans-serif; padding: 20px; background: #f4f7f6; }} .container {{ background: white; padding: 30px; border-radius: 10px; max-width: 1200px; margin: auto; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }} h1 {{ text-align: center; color: #2c3e50; border-bottom: 2px solid #3498db; }} h2 {{ color: #e67e22; border-bottom: 1px dashed #ccc; padding: 5px; }} .styled-table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }} .styled-table thead tr {{ background-color: #009879; color: white; }} .styled-table th, .styled-table td {{ padding: 10px; border: 1px solid #ddd; text-align: center; }}</style></head><body><div class='container'><h1>📊 塗料生產績效報告 - {latest_m}</h1>"
                    for line in sorted(df_word['線別'].unique()):
                        html_content += f"<h2>🏭 線別: {line}</h2>"
                        df_line = df_word[df_word['線別'] == line].copy()
                        # Scatter Plot
                        fig_sc_exp = px.scatter(df_line, x='塗料編號', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, size='合計理論耗用', size_max=30)
                        fig_sc_exp.update_yaxes(range=[max(0, df_line['合計績效%'].min() - 10), 120])
                        fig_sc_exp.add_hline(y=100, line_dash="dash", line_color="red")
                        html_content += fig_sc_exp.to_html(full_html=False, include_plotlyjs='cdn')
                        # Pareto
                        p_line = df_line[df_line['Δ耗用 (Deviation)'] > 0].sort_values(by='Δ耗用 (Deviation)', ascending=False).head(40)
                        if not p_line.empty:
                            p_line['Cum%'] = p_line['Δ耗用 (Deviation)'].cumsum() / p_line['Δ耗用 (Deviation)'].sum() * 100
                            fig_p_exp = go.Figure()
                            fig_p_exp.add_trace(go.Bar(x=p_line['塗料編號'], y=p_line['Δ耗用 (Deviation)'], marker_color='#990000'))
                            fig_p_exp.add_trace(go.Scatter(x=p_line['塗料編號'], y=p_line['Cum%'], yaxis='y2', line=dict(color='#00008B', width=3)))
                            fig_p_exp.update_layout(plot_bgcolor='white', height=600, yaxis2=dict(overlaying='y', side='right', range=[0, 105]))
                            html_content += "<h3>🚨 異常超耗柏拉圖</h3>" + fig_p_exp.to_html(full_html=False, include_plotlyjs='cdn')
                        # Table
                        html_content += "<h3>📋 嚴重超耗清單</h3><table class='styled-table'><thead><tr><th>ID</th><th>Supplier</th><th>Perf %</th><th>Over (kg)</th></tr></thead><tbody>"
                        for _, r in df_line.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10).iterrows():
                            html_content += f"<tr><td>{r['塗料編號']}</td><td>{r['油漆廠商']}</td><td>{r['合計績效%']:.2f}%</td><td>{r['Δ耗用 (Deviation)']:,.0f}</td></tr>"
                        html_content += "</tbody></table>"
                    html_content += "</div></body></html>"
                    st.sidebar.download_button("📥 下載報表", data=html_content.encode('utf-8'), file_name=f"Report_{latest_m}.html", mime="text/html")
            except Exception as e: st.sidebar.error(f"Error: {e}")

    except Exception as e: st.error(f"System Error: {e}")
else: st.info("👈 請上傳 MES 數據檔案。")
