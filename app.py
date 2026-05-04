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
st.markdown("依據 MES/Excel 數據進行系統化分析 (高階決策最佳化佈局)")

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
        st.markdown("### 📈 數據分析圖表")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [總覽] 績效分佈", 
            "🚨 [決策] 改善清單", 
            "📦 [根因] 穩定度分析", 
            "🎯 [全景] 績效燈號", 
            "📊 [明細] 耗用對比", 
            "📉 [明細] 差異分析"
        ])

        with tab_overview:
            st.subheader("1. 產線整體績效總覽 (Macro Overview)")
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                avg_perf = filtered_df['合計績效%'].mean()
                total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
                k1.metric("平均總績效", f"{avg_perf:.2f}%")
                k2.metric("總差異耗用", f"{total_delta:,.0f}", delta_color="inverse")
                k3.metric("分析塗料總數", f"{total_paints} 支")
            
            st.divider()
            pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
            col_pie, col_table = st.columns([4, 6])
            
            with col_pie:
                if not pie_df.empty:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '數量']
                    fig_pie = px.pie(
                        pie_counts, values='數量', names='績效等級', color='績效等級',
                        color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'}, hole=0.4
                    )
                    fig_pie.update_layout(plot_bgcolor='white', font=dict(color='black', size=14), height=450, title="<b>塗料績效等級比例</b>", showlegend=False)
                    st.plotly_chart(fig_pie, use_container_width=True)

            with col_table:
                st.markdown("##### 🚨 Top 10 嚴重超耗塗料清單")
                over_used_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].copy()
                if not over_used_df.empty:
                    decision_table = over_used_df.sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)
                    st.dataframe(decision_table[['塗料編號', '油漆廠商', '線別', '合計績效%', 'Δ耗用 (Deviation)']], use_container_width=True, hide_index=True)

        with tab_pareto:
            st.subheader("2. 異常超耗柏拉圖 (Pareto Priority)")
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            if not pareto_df.empty:
                pareto_df = pareto_df.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                pareto_df['累計%'] = pareto_df['Δ耗用 (Deviation)'].cumsum() / pareto_df['Δ耗用 (Deviation)'].sum() * 100
                top_pareto = pareto_df.head(40)
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=top_pareto['塗料編號'], y=top_pareto['Δ耗用 (Deviation)'], name='超耗量', marker_color='#d73027', hovertext=top_pareto['塗料編號']))
                fig_pareto.add_trace(go.Scatter(x=top_pareto['塗料編號'], y=top_pareto['累計%'], name='累計百分比', yaxis='y2', line=dict(color='#4575b4', width=3), mode='lines+markers'))
                fig_pareto.update_layout(
                    yaxis2=dict(overlaying='y', side='right', range=[0, 105]),
                    xaxis=dict(tickangle=-45, automargin=True, title=""),
                    height=650, margin=dict(b=150)
                )
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_rootcause:
            col1, col2 = st.columns(2)
            NO_RED_PALETTE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#7f7f7f', '#bcbd22', '#17becf']
            with col1:
                st.subheader("3A. 供應商品質穩定度")
                if '油漆廠商' in filtered_df.columns and not filtered_df.empty:
                    fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                    fig_box1.add_hline(y=100, line_dash="dash", line_color="red", line_width=2.5)
                    fig_box1.update_layout(xaxis=dict(automargin=True), plot_bgcolor='white', height=550)
                    st.plotly_chart(fig_box1, use_container_width=True)
            with col2:
                st.subheader("3B. 班別操作穩定度")
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效%').dropna(subset=['績效%'])
                    if not shift_df.empty:
                        fig_box2 = px.box(shift_df, x='班別', y='績效%', color='班別', points="all", hover_data=['塗料編號'], color_discrete_sequence=NO_RED_PALETTE)
                        fig_box2.update_layout(xaxis=dict(automargin=True), plot_bgcolor='white', height=550)
                        st.plotly_chart(fig_box2, use_container_width=True)

        with tab_scatter:
            st.subheader(f"4. 塗料績效燈號全景總覽 (共 {total_paints} 支)")
            plot_df = filtered_df.dropna(subset=['合計理論耗用', '合計績效%']).sort_values('塗料編號')
            if not plot_df.empty:
                fig_sc = px.scatter(
                    plot_df, x='塗料編號', y='合計績效%', color='績效等級', 
                    size='合計理論耗用', size_max=25,
                    hover_name='塗料編號',
                    hover_data={'塗料編號': False, '線別': True, '合計理論耗用': True, '合計實際耗用': True},
                    color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'}
                )
                fig_sc.add_hline(y=100, line_dash="dash", line_color="red", line_width=2.5)
                fig_sc.update_layout(xaxis=dict(tickangle=-45, automargin=True, title=""), margin=dict(b=150), height=700)
                st.plotly_chart(fig_sc, use_container_width=True)

        with tab_bar:
            st.subheader("5. 單一塗料：理論耗用 vs 實際耗用明細")
            for i in range(num_charts):
                batch = sort_order[i*items_per_chart : (i+1)*items_per_chart]
                df_bar = filtered_df[filtered_df['塗料編號'].isin(batch)].groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論', marker_color='#34495e', hovertext=df_bar['塗料編號']))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際', marker_color='#3498db', hovertext=df_bar['塗料編號']))
                fig_bar.update_layout(barmode='group', xaxis=dict(tickangle=-45, automargin=True, title=""), margin=dict(b=150), height=600)
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            st.subheader("6. 單一塗料：耗用差異絕對值")
            for i in range(num_charts):
                batch = sort_order[i*items_per_chart : (i+1)*items_per_chart]
                df_dev = filtered_df[filtered_df['塗料編號'].isin(batch)].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', 
                                 hover_name='塗料編號',
                                 color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
                fig_dev.update_layout(xaxis=dict(tickangle=-45, automargin=True, title=""), margin=dict(b=150), height=600)
                st.plotly_chart(fig_dev, use_container_width=True)

        # ==========================================
        # [ 4. EXPORT REPORT TO HTML ]
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [3] 匯出報表 (Export)")
        report_sel_month = st.sidebar.selectbox("選擇欲匯出報表的月份", options=available_months)
        
        if st.sidebar.button("📄 產生 正面漆 績效報表"):
            with st.spinner("報表生成中..."):
                try:
                    df_rep = df[(df['用途'] == '正面漆') & (df['年月'] == report_sel_month)].copy()
                    if df_rep.empty:
                        st.sidebar.error(f"❌ {report_sel_month} 無數據")
                    else:
                        html_content = f"""
                        <html>
                        <head>
                            <meta charset='utf-8'>
                            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                            <style>
                                body {{ font-family: sans-serif; background-color: #ffffff; padding: 30px; }}
                                .card {{ border: 1px solid #ddd; padding: 20px; margin-bottom: 40px; border-radius: 8px; }}
                                h1 {{ text-align: center; color: #2c3e50; }}
                                h2 {{ color: #e67e22; border-left: 5px solid #e67e22; padding-left: 10px; }}
                            </style>
                        </head>
                        <body>
                            <h1>📊 生產績效分析報表 - 正面漆 ({report_sel_month})</h1>
                        """
                        for line in sorted(df_rep['線別'].unique()):
                            line_data = df_rep[df_rep['線別'] == line].sort_values('塗料編號')
                            html_content += f"<h2>🏭 線別: {line}</h2>"
                            
                            f1 = px.scatter(line_data, x='塗料編號', y='合計績效%', color='績效等級', hover_name='塗料編號',
                                            color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'})
                            f1.update_layout(paper_bgcolor='white', plot_bgcolor='white', xaxis=dict(tickangle=-45, automargin=True, title=""), margin=dict(b=100))
                            
                            f3 = px.bar(line_data.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index(), x='塗料編號', y='Δ耗用 (Deviation)', hover_name='塗料編號')
                            f3.update_layout(paper_bgcolor='white', plot_bgcolor='white', xaxis=dict(tickangle=-45, automargin=True, title=""), margin=dict(b=100))

                            html_content += f"<div class='card'>{f1.to_html(full_html=False, include_plotlyjs=False)}</div>"
                            html_content += f"<div class='card'>{f3.to_html(full_html=False, include_plotlyjs=False)}</div>"

                        html_content += "</body></html>"
                        st.sidebar.download_button("📥 下載報表 (HTML)", data=html_content.encode('utf-8'), file_name=f"Report_{report_sel_month}.html", mime="text/html")
                except Exception as e:
                    st.sidebar.error(f"錯誤: {e}")

    except Exception as e:
        st.error(f"系統錯誤: {e}")
else:
    st.info("👈 請先上傳數據檔案。")
