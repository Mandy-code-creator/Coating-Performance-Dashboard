import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (多圖表捲動模式 - 每組 40 支)")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # 讀取資料
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

        # 2. 數值轉換
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 3. 建立排序群組
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
        # [ 3. 視覺化分析 - 自動分段顯示 ]
        # ==========================================
        all_paints = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(all_paints)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart)

        st.subheader(f"📈 績效燈號散佈圖 (共 {total_paints} 支塗料，分 {num_charts} 組顯示)")

        if total_paints > 0:
            # 💡 Vòng lặp tự động tạo biểu đồ
            for i in range(num_charts):
                start_idx = i * items_per_chart
                end_idx = min(start_idx + items_per_chart, total_paints)
                current_batch = all_paints[start_idx:end_idx]
                
                # Lọc dữ liệu cho cụm hiện tại
                batch_df = filtered_df[filtered_df['塗料編號'].isin(current_batch)].copy()
                
                # Thiết lập màu sắc
                conds = [batch_df['合計績效%'] < 85, (batch_df['合計績效%'] < 95), (batch_df['合計績效%'] < 100), batch_df['合計績效%'] >= 100]
                labels = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
                batch_df['績效等級'] = np.select(conds, labels, default='未知')

                with st.expander(f"📊 第 {i+1} 組塗料績效 ({start_idx+1} - {end_idx})", expanded=True):
                    fig = px.scatter(
                        batch_df, x='塗料編號', y='合計績效%', color='績效等級',
                        color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                        size='合計理論耗用', size_max=30,
                        category_orders={"績效等級": labels},
                        hover_data=['合計理論耗用', '合計實際耗用']
                    )
                    fig.add_hline(y=100, line_dash="dash", line_color="black")
                    fig.update_layout(
                        xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=current_batch),
                        height=500,
                        margin=dict(t=20, b=20)
                    )
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("查無資料，請調整篩選條件。")

    except Exception as e:
        st.error(f"系統錯誤：{e}")
else:
    st.info("👈 請上傳數據檔案以開始分析。")
