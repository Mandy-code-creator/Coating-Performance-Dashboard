import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板 V4", layout="wide")

st.title("🚀 塗料績效精準分析系統 (UI & 顏色優化版)")

# ==========================================
# [ 1. DATA LOAD & CLEANING ]
# ==========================================
st.sidebar.header("📂 資料匯入")
uploaded_file = st.sidebar.file_uploader("上傳數據 (Excel/CSV)", type=['csv', 'xlsx'])

def filter_with_all(label, options):
    """Hàm bổ trợ để tạo bộ lọc có tùy chọn 'All'"""
    options = ["All"] + sorted([str(x) for x in options if pd.notnull(x)])
    selected = st.multiselect(label, options, default=["All"])
    if "All" in selected:
        return [str(x) for x in options if x != "All"]
    return selected

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, engine='python', sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # Xử lý dữ liệu thô (Tránh lỗi float)
        text_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # Chuyển đổi số và tính toán
        num_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for shift in ['A', 'B', 'C', 'D']:
            num_cols.append(f'{shift}班績效%')
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Xử lý Logic GE00/GE01 và Năm tháng
        if '年月' in df.columns:
            df['年月'] = df['年月'].str.replace(r'\.0$', '', regex=True)

        # ==========================================
        # [ 2. OPTIMIZED FILTERS (Hiển thị gọn gàng) ]
        # ==========================================
        st.sidebar.header("🔍 篩選控制台")
        
        with st.sidebar.expander("📅 時間與線別", expanded=True):
            sel_month = filter_with_all("年月", df['年月'].unique())
            sel_line = filter_with_all("線別", df['線別'].unique())

        with st.sidebar.expander("🎨 塗料屬性", expanded=True):
            sel_usage = filter_with_all("用途 (主要分類)", df['用途'].unique())
            sel_supplier = filter_with_all("油漆廠商", df['油漆廠商'].unique() if '油漆廠商' in df.columns else [])

        # Áp dụng bộ lọc
        mask = (df['年月'].isin(sel_month)) & (df['線別'].isin(sel_line)) & (df['用途'].isin(sel_usage))
        if '油漆廠商' in df.columns and sel_supplier:
            mask &= (df['油漆廠商'].isin(sel_supplier))
        
        f_df = df[mask].copy()

        # ==========================================
        # [ 3. HEATMAP WITH IMPROVED COLOR LOGIC ]
        # ==========================================
        st.subheader("⚠️ 異常績效深度監控 (Diverging Color Heatmap)")
        st.markdown("顏色說明：<span style='color:red'>紅色 (低於100%, 耗損)</span> | <span style='color:gray'>白色 (接近100%)</span> | <span style='color:green'>綠色 (高於100%, 節省)</span>", unsafe_allow_html=True)
        
        threshold = st.slider("設定顯示偏差範圍 (%)", 0, 30, 10)
        lower_b, upper_b = 100 - threshold, 100 + threshold

        # Lọc các mã nằm ngoài vùng an toàn
        problem_df = f_df[(f_df['合計績效%'] < lower_b) | (f_df['合計績效%'] > upper_b)]
        
        if not problem_df.empty:
            shift_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in problem_df.columns]
            df_heat = problem_df.melt(id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效')
            df_heat['班別'] = df_heat['班別'].str[0]
            
            # Sắp xếp theo hiệu suất tổng để dễ theo dõi
            sort_order = problem_df.sort_values('合計績效%')['塗料編號'].tolist()

            # Tạo biểu đồ Heatmap với logic màu phân kỳ chuyên nghiệp
            fig_heat = go.Figure(data=go.Heatmap(
                z=df_heat['績效'],
                x=df_heat['班別'],
                y=df_heat['塗料編號'],
                colorscale=[
                    [0, '#d73027'],      # Đỏ đậm (Rất thấp)
                    [0.45, '#fee08b'],   # Vàng nhạt (Dưới mục tiêu một chút)
                    [0.5, '#ffffff'],    # Trắng (Đúng 100%)
                    [0.55, '#d9ef8b'],   # Xanh nhạt (Trên mục tiêu một chút)
                    [1, '#1a9850']       # Xanh đậm (Rất cao)
                ],
                zmin=70, zmax=130, # Giới hạn dải màu để độ tương phản rõ rệt hơn quanh mốc 100
                zmid=100,
                text=df_heat['績效'].round(1),
                texttemplate="%{text}",
                showscale=True
            ))

            fig_heat.update_layout(
                title=f"班別績效熱力圖 (目標 100%) - 已過濾 {len(problem_df)} 支異常碼",
                xaxis_title="班別",
                yaxis_title="塗料編號",
                height=max(400, len(problem_df) * 25),
                yaxis={'categoryarray': sort_order}
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.success("✅ 目前所有塗料績效均穩定在設定範圍內。")

        # ==========================================
        # [ 4. USAGE ANALYSIS ]
        # ==========================================
        st.divider()
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("📂 用途分類績效")
            usage_avg = f_df.groupby('用途')['合計績效%'].mean().reset_index()
            fig_u = px.bar(usage_avg, x='用途', y='合計績效%', color='合計績效%',
                           color_continuous_scale='RdYlGn', color_continuous_midpoint=100,
                           text_auto='.1f')
            fig_u.add_hline(y=100, line_dash="dash", line_color="black")
            st.plotly_chart(fig_u, use_container_width=True)

        with col_right:
            st.subheader("📊 用途耗用比例 (理論值)")
            usage_sum = f_df.groupby('用途')['合計理論耗用'].sum().reset_index()
            fig_p = px.pie(usage_sum, values='合計理論耗用', names='用途', hole=0.4,
                           color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_p, use_container_width=True)

        st.subheader("📋 明細數據表")
        st.dataframe(f_df)

    except Exception as e:
        st.error(f"系統錯誤: {e}")
else:
    st.info("👋 請上傳資料檔案以開始分析。")
