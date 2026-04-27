import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板 V5", layout="wide")
st.title("🚀 塗料績效精準分析系統 (階層式篩選版)")

# ==========================================
# [ 1. DATA LOAD & CLEANING ]
# ==========================================
st.sidebar.header("📂 資料匯入")
uploaded_file = st.sidebar.file_uploader("上傳數據 (Excel/CSV)", type=['csv', 'xlsx'])

# Hàm hỗ trợ bộ lọc có tùy chọn "All"
def filter_with_all(label, options):
    valid_options = sorted([str(x) for x in options if pd.notnull(x) and str(x).strip() != ''])
    options_list = ["全部 (All)"] + valid_options
    selected = st.multiselect(label, options_list, default=["全部 (All)"])
    
    # Nếu người dùng chọn All hoặc xóa trắng, tự động hiểu là lấy tất cả
    if "全部 (All)" in selected or len(selected) == 0:
        return valid_options
    return selected

if uploaded_file is not None:
    try:
        # Đọc dữ liệu
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, engine='python', sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # Xử lý dữ liệu thô
        text_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        if '年月' in df.columns:
            df['年月'] = df['年月'].str.replace(r'\.0$', '', regex=True)

        num_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            num_cols.append(f'{shift}班績效%')
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # ==========================================
        # [ 2. STEP-BY-STEP CASCADING FILTERS ]
        # ==========================================
        st.sidebar.header("🔍 篩選步驟 (Step-by-Step)")
        
        # Step 1: Chọn thời gian
        st.sidebar.markdown("### Step 1: 選擇時間")
        sel_month = filter_with_all("1. 年月 (Month)", df['年月'].unique())
        df_step1 = df[df['年月'].isin(sel_month)]

        # Step 2: Chọn Line (Danh sách tự động cập nhật theo thời gian)
        st.sidebar.markdown("### Step 2: 選擇線別")
        sel_line = filter_with_all("2. 線別 (Line)", df_step1['線別'].unique())
        df_step2 = df_step1[df_step1['線別'].isin(sel_line)]

        # Step 3: Chọn Ứng dụng (Danh sách tự động cập nhật theo Line)
        st.sidebar.markdown("### Step 3: 選擇用途")
        sel_usage = filter_with_all("3. 用途 (Usage)", df_step2['用途'].unique())
        f_df = df_step2[df_step2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 3. HEATMAP WITH DIVERGING COLOR ]
        # ==========================================
        st.subheader("⚠️ 異常績效深度監控 (Diverging Color Heatmap)")
        st.markdown("顏色說明：<span style='color:#d73027; font-weight:bold'>紅色 (低於100%, 耗損)</span> | <span style='color:gray; font-weight:bold'>白色 (接近100%)</span> | <span style='color:#1a9850; font-weight:bold'>綠色 (高於100%, 節省)</span>", unsafe_allow_html=True)
        
        # Thanh trượt cho phép sếp điều chỉnh mức độ sai lệch muốn xem
        threshold = st.slider("設定顯示偏差範圍 (%)", 0, 30, 5)
        lower_b, upper_b = 100 - threshold, 100 + threshold

        # Lọc dữ liệu bất thường
        problem_df = f_df[(f_df['合計績效%'] < lower_b) | (f_df['合計績效%'] > upper_b)]
        
        if not problem_df.empty:
            shift_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in problem_df.columns]
            df_heat = problem_df.melt(id_vars=['塗料編號'], value_vars=shift_cols, var_name='班別', value_name='績效')
            df_heat['班別'] = df_heat['班別'].str[0]
            
            # Gom GE00 và GE01 lại với nhau trong lúc sort (Logic gom nhóm đặc thù)
            problem_df['Sort_Group'] = problem_df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in x for g in ['GE00', 'GE01']) else x)
            sort_order = problem_df.sort_values(by=['Sort_Group', '合計績效%'])['塗料編號'].tolist()

            fig_heat = go.Figure(data=go.Heatmap(
                z=df_heat['績效'],
                x=df_heat['班別'],
                y=df_heat['塗料編號'],
                colorscale=[
                    [0, '#d73027'],      # Đỏ đậm (Hiệu suất thấp)
                    [0.45, '#fee08b'],   # Vàng (Hơi thấp)
                    [0.5, '#ffffff'],    # Trắng (Chính xác 100%)
                    [0.55, '#d9ef8b'],   # Xanh nhạt (Hơi cao)
                    [1, '#1a9850']       # Xanh đậm (Hiệu suất cao)
                ],
                zmin=70, zmax=130, # Cố định dải màu để 100 luôn luôn nằm ở mức Trắng
                zmid=100,
                text=df_heat['績效'].round(1),
                texttemplate="%{text}",
                showscale=True
            ))

            fig_heat.update_layout(
                title=f"班別績效熱力圖 (目標 100%) - 顯示 {len(problem_df)} 支異常碼",
                xaxis_title="班別",
                yaxis_title="塗料編號",
                height=max(400, len(problem_df) * 30),
                yaxis={'categoryarray': sort_order}
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.success("✅ 目前所有塗料績效均穩定在設定範圍內 (100%)。")

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
            st.subheader("📊 用途耗用比例 (理論值 vs 實際值)")
            usage_sum = f_df.groupby('用途')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(name='理論值 (Theoretical)', x=usage_sum['用途'], y=usage_sum['合計理論耗用'], marker_color='#34495e'))
            fig_comp.add_trace(go.Bar(name='實際值 (Actual)', x=usage_sum['用途'], y=usage_sum['合計實際耗用'], marker_color='#3498db'))
            fig_comp.update_layout(barmode='group')
            st.plotly_chart(fig_comp, use_container_width=True)

        st.subheader("📋 明細數據表")
        st.dataframe(f_df)

    except Exception as e:
        st.error(f"系統錯誤: {e}")
else:
    st.info("👋 請上傳資料檔案 (Data Load) 以開始分析。")
