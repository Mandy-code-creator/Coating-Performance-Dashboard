import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# 頁面設定 (Thiết lập trang)
st.set_page_config(page_title="塗料績效儀表板", layout="wide")

# 1. 載入資料 (Load Data - Thay bằng hàm đọc file thực tế)
@st.cache_data
def load_data():
    np.random.seed(42)
    n = 150 # 樣本數
    
    lines = ['Line 1', 'Line 2', 'Line 3']
    months = ['2026-02', '2026-03', '2026-04']
    usages = ['用途 A', '用途 B', '用途 C']
    
    data = {
        '線別': np.random.choice(lines, n),
        '塗料編號': [f'PT-{str(i).zfill(4)}' for i in range(1, n+1)],
        '設定績效%': [100] * n,
        'A班績效%': np.random.normal(95, 10, n),
        'B班績效%': np.random.normal(98, 12, n),
        'C班績效%': np.random.normal(102, 8, n),
        'D班績效%': np.random.normal(100, 5, n),
        '合計理論耗用': np.random.uniform(100, 500, n),
        '合計實際耗用': np.random.uniform(90, 550, n),
        '年月': np.random.choice(months, n),
        '用途': np.random.choice(usages, n),
    }
    df = pd.DataFrame(data)
    # 計算合計績效%
    df['合計績效%'] = (df['合計理論耗用'] / df['合計實際耗用']) * 100
    return df

df = load_data()

# 2. 側邊欄 - 篩選器 (Sidebar Filters)
st.sidebar.header("🔍 資料篩選 (Data Filters)")

selected_line = st.sidebar.multiselect("選擇線別 (Line)", options=df['線別'].unique(), default=df['線別'].unique())
selected_month = st.sidebar.multiselect("選擇年月 (Month)", options=sorted(df['年月'].unique()), default=sorted(df['年月'].unique()))
selected_usage = st.sidebar.multiselect("選擇用途 (Usage)", options=df['用途'].unique(), default=df['用途'].unique())

# 執行篩選
filtered_df = df[
    (df['線別'].isin(selected_line)) &
    (df['年月'].isin(selected_month)) &
    (df['用途'].isin(selected_usage))
]

# 3. 主畫面 (Main Panel)
st.title("📊 塗料績效管理儀表板")
st.markdown("追蹤塗料消耗績效 (基準：100%)")

# KPI 指標 (KPI Metrics)
st.markdown("### 📌 關鍵績效指標 (KPI)")
col1, col2, col3, col4 = st.columns(4)

if not filtered_df.empty:
    avg_perf = filtered_df['合計績效%'].mean()
    best_paint = filtered_df.loc[filtered_df['合計績效%'].idxmax()]
    worst_paint = filtered_df.loc[filtered_df['合計績效%'].idxmin()]

    col1.metric("平均總績效 (Avg Perf)", f"{avg_perf:.2f}%", f"{avg_perf - 100:.2f}% (vs 目標)")
    col2.metric("塗料編號數量 (Paint Count)", len(filtered_df))
    col3.metric("最高績效編號 (Best)", best_paint['塗料編號'], f"{best_paint['合計績效%']:.2f}%")
    col4.metric("最低績效編號 (Worst)", worst_paint['塗料編號'], f"{worst_paint['合計績效%']:.2f}%")
else:
    st.warning("無符合條件的資料 (No data matches the selected filters)")

st.divider()

# 圖表 1: 散佈圖 (Scatter Plot)
st.markdown("### 1. 各塗料編號績效散佈圖 (基準: 100%)")
if not filtered_df.empty:
    fig_scatter = px.scatter(
        filtered_df, 
        x='塗料編號', 
        y='合計績效%', 
        color='用途', 
        hover_data=['線別', '年月', '合計理論耗用', '合計實際耗用'],
    )
    # 加入 100% 基準線
    fig_scatter.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 (Target: 100%)")
    fig_scatter.update_layout(xaxis_title="塗料編號", yaxis_title="合計績效 (%)", hovermode="closest")
    st.plotly_chart(fig_scatter, use_container_width=True)

# 圖表 2 & 3: 最低績效前10名 與 各班別比較
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("### 2. 績效表現最差前 10 名 (需注意)")
    if not filtered_df.empty:
        bottom_10 = filtered_df.nsmallest(10, '合計績效%')
        fig_bar_bottom = px.bar(
            bottom_10, 
            x='塗料編號', 
            y='合計績效%', 
            color='合計績效%',
            color_continuous_scale='Reds_r',
            text_auto='.2f'
        )
        fig_bar_bottom.add_hline(y=100, line_dash="dash", line_color="black")
        fig_bar_bottom.update_layout(xaxis_title="塗料編號", yaxis_title="合計績效 (%)")
        st.plotly_chart(fig_bar_bottom, use_container_width=True)

with col_chart2:
    st.markdown("### 3. 各班別績效比較 (A, B, C, D班)")
    if not filtered_df.empty:
        melted_df = pd.melt(filtered_df, value_vars=['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'], 
                            var_name='班別', value_name='班別績效 (%)')
        fig_box = px.box(melted_df, x='班別', y='班別績效 (%)', color='班別')
        fig_box.add_hline(y=100, line_dash="dash", line_color="red")
        st.plotly_chart(fig_box, use_container_width=True)

# 資料表 (Data Table)
st.markdown("### 📋 詳細資料表")
st.dataframe(filtered_df)
