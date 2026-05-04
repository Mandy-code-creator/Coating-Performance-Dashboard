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

# Tối ưu CSS để giao diện sạch sẽ hơn
st.markdown("""
<style>
.stPlotlyChart {
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    background-color: white;
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
st.markdown("依據 MES/Excel 數據進行系統化分析")

# ==========================================
# [ 1. 資料匯入 ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (CSV 或 XLSX)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        # Xử lý dữ liệu cột
        for col in ['線別', '塗料編號', '用途', '年月', '油漆廠商']:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # Chuyển đổi số liệu
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Tính toán Mass Balance & Deviation
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        
        # Phân loại Performance Level
        conds = [df['合計績效%'] < 85, (df['合計績效%'] >= 85) & (df['合計績效%'] < 95), (df['合計績效%'] >= 95) & (df['合計績效%'] < 100), df['合計績效%'] >= 100]
        labels = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
        df['績效等級'] = np.select(conds, labels, default='未知')

        # ==========================================
        # [ 2. 篩選控制台 ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        available_months = sorted(df['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("選擇年月", options=available_months, default=available_months[:1])
        
        filtered_df = df[df['年月'].isin(sel_month)]
        
        # ==========================================
        # [ 3. 視覺化圖表區 ]
        # ==========================================
        tab1, tab2, tab3 = st.tabs(["🍩 績效概覽", "🚨 超耗分析", "📉 差異明細"])

        with tab1:
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                k1.metric("平均總績效", f"{filtered_df['合計績效%'].mean():.2f}%")
                k2.metric("總差異耗用", f"{filtered_df['Δ耗用 (Deviation)'].sum():,.0f}")
                k3.metric("分析塗料數", f"{len(filtered_df['塗料編號'].unique())} 支")
                
                fig_p = px.pie(filtered_df, names='績效等級', color='績效等級', 
                               color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'})
                st.plotly_chart(fig_p, use_container_width=True)

        with tab2:
            pareto_df = filtered_df[filtered_df['Δ耗用 (Deviation)'] > 0].sort_values(by='Δ耗用 (Deviation)', ascending=False).head(40)
            if not pareto_df.empty:
                fig_pa = px.bar(pareto_df, x='塗料編號', y='Δ耗用 (Deviation)', title="Top 40 異常超耗排行")
                fig_pa.update_layout(xaxis=dict(tickangle=-90, automargin=True, title=""), margin=dict(b=150))
                st.plotly_chart(fig_pa, use_container_width=True)

        with tab3:
            fig_dev = px.bar(filtered_df, x='塗料編號', y='Δ耗用 (Deviation)', color='績效等級', title="個案耗用差異明細")
            fig_dev.update_layout(xaxis=dict(tickangle=-90, automargin=True, title=""), margin=dict(b=150))
            st.plotly_chart(fig_dev, use_container_width=True)

        # ==========================================
        # [ 4. 報表匯出功能 ]
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("📥 [3] 匯出報表")
        report_month = st.sidebar.selectbox("請選擇報表月份", options=available_months)
        
        if st.sidebar.button("產生 正面漆 績效報表"):
            df_rep = df[(df['用途'] == '正面漆') & (df['年月'] == report_month)].copy()
            if df_rep.empty:
                st.sidebar.error(f"⚠️ {report_month} 無正面漆數據")
            else:
                # Cấu hình HTML để tránh lỗi "đen thui"
                html_code = f"""
                <html>
                <head>
                    <meta charset='utf-8'>
                    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                    <style>
                        body {{ font-family: sans-serif; background-color: #ffffff; padding: 40px; }}
                        .container {{ max-width: 1200px; margin: auto; }}
                        .chart-card {{ background: white; border: 1px solid #ddd; padding: 20px; margin-bottom: 50px; border-radius: 10px; }}
                        h1 {{ text-align: center; color: #333; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>📊 生產績效分析報表 - 正面漆 ({report_month})</h1>
                """
                
                for line in sorted(df_rep['線別'].unique()):
                    df_line = df_rep[df_rep['線別'] == line]
                    html_code += f"<h2>🏭 線別: {line}</h2>"
                    
                    # Chart: Deviation
                    fig = px.bar(df_line, x='塗料編號', y='Δ耗用 (Deviation)', color='績效等級',
                                 color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                                 title=f"線別 {line} - 耗用差異明細")
                    
                    # Tối ưu hiển thị để không đè chữ
                    fig.update_layout(
                        paper_bgcolor='white', 
                        plot_bgcolor='white',
                        xaxis=dict(tickangle=-90, automargin=True, title=""),
                        margin=dict(b=150, t=50, l=50, r=50)
                    )
                    
                    # Chuyển chart sang HTML (Sử dụng CDN để đảm bảo không bị đen)
                    chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
                    html_code += f"<div class='chart-card'>{chart_html}</div>"

                html_code += "</div></body></html>"
                
                st.sidebar.success(f"✅ {report_month} 報表已生成")
                st.sidebar.download_button("📥 下載報表 (HTML)", data=html_code, file_name=f"Report_{report_month}.html", mime="text/html")

    except Exception as e:
        st.error(f"錯誤: {e}")
else:
    st.info("👈 請先上傳檔案")
