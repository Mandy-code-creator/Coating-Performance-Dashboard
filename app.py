import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import random
import math

# 頁面設定 (Thiết lập trang)
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

# CSS để bọc viền trắng bao quanh biểu đồ như hình
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
""", unsafe_allow_escaping=True)

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (進階根因分析版)")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ] (Giả lập)
# ==========================================
# ... (Phần tạo dữ liệu giả như cũ, đảm bảo đa dạng mã sơn, line, tháng...)
def generate_paint_data():
    paint_codes = [f"PA{random.randint(1,9)}P{random.randint(300,399)}{chr(random.randint(88,90))}" for _ in range(129)] + \
                  [f"PJ{random.randint(1,9)}P{random.randint(300,399)}{chr(random.randint(88,90))}" for _ in range(129)]
    lines = [f"Line {random.randint(1,5)}CP" for _ in range(len(paint_codes))]
    total_paint_codes = list(set(paint_codes))
    data = []
    months = [f"2023.{m:02d}" for m in range(1, 13)]
    suppliers = ['AkzoNobel 蘇貝貝爾', 'Taiwan West 台灣威士伯', 'AkzoNobel 阿克蘇諾貝爾', 'Kansai', 'Nippon Nippon paint']
    usages = ['Usage A', 'Usage B', 'Usage C']
    for _ in range(400):
        data.append({
            '年月': random.choice(months),
            '線別': f"Line {random.randint(1,5)}CP",
            '塗料編號': random.choice(total_paint_codes),
            '合計理論耗用': random.randint(100, 5000),
            '合計實際耗用': random.randint(100, 5000) * (random.randint(75, 130) / 100),
            '油漆廠商': random.choice(suppliers),
            '用途': random.choice(usages)
        })
    df = pd.DataFrame(data)
    df['合計績效%'] = (df['合計理論耗用'] / df['合計實際耗用'] * 100).round(2)
    for shift in ['A', 'B', 'C', 'D']:
        df[f'Shift_{shift}_Perf%'] = df['合計績效%'] + np.random.normal(0, 10, len(df))
    return df
df_full = generate_paint_data()

# ==========================================
# [ 2. DASHBOARD FILTER ]
# ==========================================
# ... (Thanh bên liên động như cũ)
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔", type=['csv', 'xlsx'])
months = sorted(df_full['年月'].unique())
sel_month = st.sidebar.multiselect("2. 年月 (Month)", options=months, default=months[-1])
df_s1 = df_full[df_full['年月'].isin(sel_month)]
lines = sorted(df_s1['線別'].unique())
sel_line = st.sidebar.multiselect("3. 線別 (Line)", options=lines, default=lines[0])
filtered_df = df_s1[df_s1['線別'].isin(sel_line)]

# ==========================================
# [ 3. DECISION MAKING KPIs ]
# ==========================================
st.markdown("### 🎯 決策指標 (Decision Making KPIs)")
col1, col2, col3, col4 = st.columns(4)
col1.metric("整體平均績效", f"{filtered_df['合計績效%'].mean():.2f}%")
col2.metric("分析塗料總數", f"{len(filtered_df['塗料編號'].unique())} 支")
col3.metric("需改善塗料數 (<95%)", f"{len(filtered_df[filtered_df['合計績效%'] < 95]['塗料編號'].unique())} 支", delta_color="inverse")
col4.metric("設定績效", "95.00%", help="Theo目標為 100%, QC目標為 95%")
st.divider()

# ==========================================
# [ 4. VISUALIZATION - TASK 1 ]
# ==========================================
st.markdown("### 📊 核心視覺化分析")
sort_order = filtered_df.sort_values(by='合計績效%')['塗料編號'].tolist()
viz_tab1, viz_tab2, viz_tab3, viz_tab4 = st.tabs(["🎯 績效燈號 (Scatter)", "📊 耗用對比 (Bar)", "📈 趨勢分析", "📦 供應商穩定度 (Pareto)"])

# 💡 **Đề xuất: Thêm chú thích cho "Đại hồng quyển"**
st.info("💡 **讀圖提示** : \n - 圓圈大小代表 **'theo使用量'**. Theo量越大,圓圈越大。\n - **🎯 Mục tiêu ưu tiên** : Đi tìm các 'đại hồng quyển' (vòng tròn đỏ lớn) để xử lý hao hụt lớn nhất.")

with viz_tab1:
    st.markdown('<div style="border: 2px solid white; border-radius: 8px; background-color: white; padding: 10px;">', unsafe_allow_escaping=True)
    st.markdown("## 第 1 組塗料績效 (1 - 40)")
    
    fig = px.scatter(
        filtered_df, x='塗料編號', y='合計績效%', 
        color='合計績效%', size='合計理論耗用',
        color_continuous_scale=[(0, '#d73027'), (0.85, '#d73027'), (0.95, '#fee08b'), (1.0, '#1a9850'), (1.3, '#1a9850')],
        color_continuous_midpoint=100,
        hover_name='塗料編號', hover_data=['線別', '年月'],
        category_orders={"塗料編號": sort_order},
        size_max=35,
        title='<b>合計績效散佈趨勢圖</b>'
    )

    # Thêm đường ngang 100%
    fig.add_hline(y=100, line_dash="dash", line_color="black", line_width=2)
    
    # --- 💡 GIẢI QUYẾT LỖI: DỜI LABEL RA NGOÀI BÊN PHẢI ---
    # fig.add_annotation(x='PJ2G128HS', y=100, text="<b>🎯 目標 100%</b>", showarrow=False, ay=-20, font=dict(color="red", size=12)) # Bỏ code này
    
    # Sử dụng `add_annotation` để dời ra lề phải và xoay dọc
    fig.add_annotation(
        x=1.02, # Tọa độ paper (0-1) dời ra ngoài mép phải khung hình (1.02)
        y=100, 
        xref="paper", yref="y",
        text="<b>🎯 目標 100%</b>", 
        showarrow=False,
        xanchor="left", yanchor="middle",
        font=dict(color="red", size=14),
        bordercolor="black",
        bgcolor="white",
        borderwidth=1,
        textangle=-90, # Xoay dọc 90 độ để tiết kiệm diện tích và tạo điểm nhấn
        name='target_label'
    )
    
    # Làm cho các điểm có viền sắc nét như hình image_9
    fig.update_traces(marker=dict(line=dict(width=1.5, color='black')), selector=dict(mode='markers'))

    # Tùy chỉnh trục và bố cục
    fig.update_layout(
        plot_bgcolor='white', font=dict(color='black'),
        margin=dict(r=100), # Mở rộng biên phải 100px để không bị mất chữ xoay dọc
        xaxis=dict(dtick=1, tickangle=45, showgrid=True, gridcolor='#e5e5e5', title='<b>塗料編號</b>'),
        yaxis=dict(showgrid=True, gridcolor='#e5e5e5', title='<b>合計績效%</b>'),
        coloraxis_colorbar=dict(title="績效等級", thickness=15, len=0.8)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_escaping=True)

with viz_tab2:
    # Biểu đồ thanh Theo vs Actual
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=filtered_df['塗料編號'], y=filtered_df['合計理論耗用'], name='Theo', marker_color='#34495e'))
    fig_bar.add_trace(go.Bar(x=filtered_df['塗料編號'], y=filtered_df['合計實際耗用'], name='Actual', marker_color='#e74c3c'))
    fig_bar.update_layout(
        plot_bgcolor='white', font=dict(color='black'), barmode='group',
        xaxis=dict(dtick=1, tickangle=45, showgrid=True, gridcolor='#e5e5e5'),
        yaxis=dict(showgrid=True, gridcolor='#e5e5e5'),
        title='<b>Theoretical vs Actual Usage by Paint Code</b>'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with viz_tab3:
    st.info("Dòng này dành cho các đề xuất cải tiến phân tích trend line SPC...")

# ==========================================
# [ 5. 🌟 TÍNH NĂNG MỚI: PARETO VÀ VARIATION ] (Dữ liệu image_9)
# ==========================================
with viz_tab4:
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("5. 安定度分析 ( बॉक्स प्लॉट)")
        st.info("💡 **讀圖提示** : 供應商盒子越長,代表其品質穩定度越差。")
        # --- 💡 CẢI TIẾN MỚI: 供應商 QC Box Plot ---
        # image_9 bên trái
        fig_box1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all")
        fig_box1.add_hline(y=100, line_dash="dash", line_color="red")
        fig_box1.update_layout(
            plot_bgcolor='white', font=dict(color='black'),
            xaxis=dict(title='<b>油漆廠商</b>', showgrid=False),
            yaxis=dict(title='<b>合計績效%</b>', showgrid=True, gridcolor='#e5e5e5'),
            title='<b>Suppliers Performance Variation (image_9 Left)</b>'
        )
        st.plotly_chart(fig_box1, use_container_width=True)

    with col2:
        st.subheader("6. 班別差異分析")
        # --- 💡 CẢI TIẾN MỚI: Ca làm việc (image_9 phải) ---
        shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=['Shift_A_Perf%', 'Shift_B_Perf%', 'Shift_C_Perf%', 'Shift_D_Perf%'], var_name='Shift', value_name='Perf%')
        shift_df['Shift'] = shift_df['Shift'].str.replace('_Perf%', '').str.replace('Shift_', 'Ca ')
        
        fig_box2 = px.box(shift_df, x='Shift', y='Perf%', color='Shift', points="all")
        fig_box2.add_hline(y=100, line_dash="dash", line_color="red")
        fig_box2.update_layout(
            plot_bgcolor='white', font=dict(color='black'),
            xaxis=dict(title='<b>班別</b>', showgrid=False),
            yaxis=dict(title='<b>績效%</b>', showgrid=True, gridcolor='#e5e5e5'),
            title='<b>Shift-to-Shift Performance Variation (image_9 Right)</b>'
        )
        st.plotly_chart(fig_box2, use_container_width=True)

with st.expander("🔍 原始數據檢視 (Original Data View)"):
    st.dataframe(filtered_df)
