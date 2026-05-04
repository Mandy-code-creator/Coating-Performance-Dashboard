import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# [ 0. 頁面配置與樣式設定 ]
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
# [ 1. 資料匯入 ]
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
        # [ 2. 篩選控制台 ]
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
        # [ 3. 視覺化圖表區 ]
        # ==========================================
        st.markdown("### 📈 數據分析圖表")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_scatter, tab_dev = st.tabs([
            "🍩 績效概覽", 
            "🚨 超耗分析", 
            "🎯 績效全景", 
            "📉 差異明細"
        ])

        with tab_overview:
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                k1.metric("平均總績效", f"{filtered_df['合計績效%'].mean():.2f}%")
                k2.metric("總差異耗用 (Deviation)", f"{filtered_df['Δ耗用 (Deviation)'].sum():,.0f}", delta_color="inverse")
                k3.metric("分析塗料總數", f"{total_paints} 支")
            
            st.divider()
            pie_df = filtered_df.dropna(subset=['合計績效%', '績效等級'])
            if not pie_df.empty:
                col_p, col_t = st.columns([4, 6])
                with col_p:
                    pie_counts = pie_df['績效等級'].value_counts().reset_index()
                    pie_counts.columns = ['績效等級', '數量']
                    fig_pie = px.pie(pie_counts, values='數量', names='績效等級', color='績效等級',
                                    color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'}, hole=0.4)
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_t:
                    st.markdown("##### 🚨 Top 10 嚴重超耗清單")
                    over_used = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].sort_values(by='Δ耗用 (Deviation)', ascending=False).head(10)
                    st.dataframe(over_used[['塗料編號', '線別', '合計績效%', 'Δ耗用 (Deviation)']], use_container_width=True, hide_index=True)

        with tab_pareto:
            pareto_data = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            if not pareto_data.empty:
                pareto_data = pareto_data.sort_values(by='Δ耗用 (Deviation)', ascending=False)
                pareto_data['累計%'] = pareto_data['Δ耗用 (Deviation)'].cumsum() / pareto_data['Δ耗用 (Deviation)'].sum() * 100
                fig_pareto = go.Figure()
                fig_pareto.add_trace(go.Bar(x=pareto_data['塗料編號'][:40], y=pareto_data['Δ耗用 (Deviation)'][:40], name='超耗量', marker_color='#d73027'))
                fig_pareto.add_trace(go.Scatter(x=pareto_data['塗料編號'][:40], y=pareto_data['累計%'][:40], name='累計百分比', yaxis='y2', line=dict(color='#4575b4')))
                fig_pareto.update_layout(yaxis2=dict(overlaying='y', side='right', range=[0, 105]), xaxis=dict(tickangle=-90, automargin=True, title=""), margin=dict(b=150))
                st.plotly_chart(fig_pareto, use_container_width=True)

        with tab_dev:
            for i in range(num_charts):
                batch = sort_order[i*items_per_chart : (i+1)*items_per_chart]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch)].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                batch_df['Status'] = np.where(batch_df['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(batch_df, x='塗料編號', y='Δ耗用 (Deviation)', color='Status', color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
                fig_dev.update_layout(xaxis=dict(tickangle=-90, automargin=True, title=""), margin=dict(b=150))
                st.plotly_chart(fig_dev, use_container_width=True)

        # ==========================================
        # [ 4. 報表匯出功能 (HTML) ]
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [3] 匯出報表 (Export)")
        report_target_month = st.sidebar.selectbox("請選擇欲匯出的月份", options=available_months)
        
        if st.sidebar.button("📄 產生 正面漆 績效報表"):
            with st.spinner("報表處理中..."):
                df_rep = df[(df['用途'] == '正面漆') & (df['年月'] == report_target_month)].copy()
                if df_rep.empty:
                    st.sidebar.error(f"⚠️ {report_target_month} 無 正面漆 相關數據")
                else:
                    lines = sorted(df_rep['線別'].unique())
                    html_code = f"<html><head><meta charset='utf-8'><title>Report_{report_target_month}</title>"
                    html_code += "<style>body{font-family:sans-serif;padding:30px;} .box{margin-bottom:60px; border:1px solid #ddd; padding:20px; border-radius:10px;}</style></head><body>"
                    html_code += f"<h1 style='text-align:center;'>📊 生產績效分析報表 - 正面漆 ({report_target_month})</h1>"
                    
                    for line in lines:
                        df_line = df_rep[df_rep['線別'] == line].copy()
                        html_code += f"<h2>🏭 線別: {line}</h2>"
                        
                        # 1. Scatter Chart
                        f1 = px.scatter(df_line, x='塗料編號', y='合計績效%', color='績效等級', title=f"[{line}] 績效分佈全景")
                        f1.update_layout(xaxis=dict(tickangle=-90, automargin=True, title=""))
                        html_code += f"<div class='box'>{f1.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
                        
                        # 2. Pareto Chart
                        p_data = df_line[df_line['Δ耗用 (Deviation)'] > 0].groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index().sort_values(by='Δ耗用 (Deviation)', ascending=False)
                        if not p_data.empty:
                            f2 = px.bar(p_data.head(40), x='塗料編號', y='Δ耗用 (Deviation)', title=f"[{line}] 異常超耗柏拉圖 (Top 40)")
                            f2.update_layout(xaxis=dict(tickangle=-90, automargin=True, title=""))
                            html_code += f"<div class='box'>{f2.to_html(full_html=False, include_plotlyjs='cdn')}</div>"
                            
                        # 3. Deviation Chart
                        f3 = px.bar(df_line.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index(), x='塗料編號', y='Δ耗用 (Deviation)', title=f"[{line} 耗用差異明細]")
                        f3.update_layout(xaxis=dict(tickangle=-90, automargin=True, title=""))
                        html_code += f"<div class='box'>{f3.to_html(full_html=False, include_plotlyjs='cdn')}</div>"

                    html_code += "</body></html>"
                    st.sidebar.success(f"✅ {report_target_month} 報表已生成")
                    st.sidebar.download_button("📥 下載報表 (HTML)", data=html_code, file_name=f"Performance_Report_{report_target_month}_Topcoat.html", mime="text/html")

    except Exception as e:
        st.error(f"系統運行錯誤: {e}")
else:
    st.info("👈 請先上傳 MES/Excel 數據檔案以開始分析")
