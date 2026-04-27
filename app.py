import streamlit as st
import pandas as pd
import plotly.express as px

# 頁面設定
st.set_page_config(page_title="塗料績效儀表板", layout="wide")

# --- 側邊欄：上傳檔案 (Sidebar: File Upload) ---
st.sidebar.header("📂 資料匯入 (Data Import)")
uploaded_file = st.sidebar.file_uploader("請選擇塗料數據檔案 (Excel 或 CSV)", type=['xlsx', 'csv'])

# 檢查是否有檔案上傳
if uploaded_file is not None:
    try:
        # 根據副檔名讀取資料
        if uploaded_file.name.endswith('.csv'):
            # 考慮到可能使用分號 (;) 或逗號 (,) 分隔
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)

        # 檢查必備欄位 (合計績效%)，若無則自動計算
        # 根據您的需求：合計績效% = (合計理論耗用 / 合計實際耗用) * 100
        if '合計績效%' not in df.columns and '合計理論耗用' in df.columns and '合計實際耗用' in df.columns:
            df['合計績效%'] = (df['合計理論耗用'] / df['合計實際耗用']) * 100

        # --- 側邊欄：篩選器 (Sidebar Filters) ---
        st.sidebar.header("🔍 資料篩選 (Data Filters)")
        
        # 確保資料中有對應欄位才顯示篩選器
        lines = df['線別'].unique() if '線別' in df.columns else []
        months = sorted(df['年月'].unique()) if '年月' in df.columns else []
        usages = df['用途'].unique() if '用途' in df.columns else []

        selected_line = st.sidebar.multiselect("選擇線別 (Line)", options=lines, default=lines)
        selected_month = st.sidebar.multiselect("選擇年月 (Month)", options=months, default=months)
        selected_usage = st.sidebar.multiselect("選擇用途 (Usage)", options=usages, default=usages)

        # 執行篩選
        mask = df['線別'].isin(selected_line) & df['年月'].isin(selected_month) & df['用途'].isin(selected_usage)
        filtered_df = df[mask]

        # --- 主畫面 (Main Panel) ---
        st.title("📊 塗料績效管理儀表板")
        st.info(f"當前載入檔案: {uploaded_file.name}")

        # KPI 指標
        st.markdown("### 📌 關鍵績效指標 (KPI)")
        col1, col2, col3, col4 = st.columns(4)

        if not filtered_df.empty:
            avg_perf = filtered_df['合計績效%'].mean()
            best_paint = filtered_df.loc[filtered_df['合計績效%'].idxmax()]
            worst_paint = filtered_df.loc[filtered_df['合計績效%'].idxmin()]

            col1.metric("平均總績效 (Avg Perf)", f"{avg_perf:.2f}%", f"{avg_perf - 100:.2f}%")
            col2.metric("塗料編號數量", len(filtered_df))
            col3.metric("最高績效編號", best_paint['塗料編號'], f"{best_paint['合計績效%']:.2f}%")
            col4.metric("最低績效編號", worst_paint['塗料編號'], f"{worst_paint['合計績效%']:.2f}%")
            
            st.divider()

            # 圖表 1: 散佈圖 (處理 >100 個樣本的最佳方案)
            st.markdown("### 1. 各塗料編號績效散佈圖 (基準: 100%)")
            fig_scatter = px.scatter(
                filtered_df, 
                x='塗料編號', 
                y='合計績效%', 
                color='用途' if '用途' in df.columns else None,
                hover_data=['線別', '年月', '合計理論耗用', '合計實際耗用']
            )
            fig_scatter.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 (100%)")
            fig_scatter.update_layout(xaxis_title="塗料編號", yaxis_title="合計績效 (%)")
            st.plotly_chart(fig_scatter, use_container_width=True)

            # 圖表 2: 班別比較 (Box Plot 觀察穩定性)
            st.markdown("### 2. 各班別績效分佈比較 (A, B, C, D 班)")
            shift_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in filtered_df.columns]
            if shift_cols:
                melted_df = pd.melt(filtered_df, value_vars=shift_cols, var_name='班別', value_name='績效%')
                fig_box = px.box(melted_df, x='班別', y='績效%', color='班別')
                fig_box.add_hline(y=100, line_dash="dash", line_color="red")
                st.plotly_chart(fig_box, use_container_width=True)

            # 詳細資料表
            st.markdown("### 📋 詳細資料明細")
            st.dataframe(filtered_df)
        else:
            st.warning("篩選後無符合條件之數據。")

    except Exception as e:
        st.error(f"檔案格式錯誤或缺少必要欄位。錯誤訊息: {e}")

else:
    # 未上傳檔案時的提示畫面
    st.title("📊 塗料績效管理儀表板")
    st.warning("👈 請在左側欄位上傳數據檔案 (Excel 或 CSV) 以開始分析。")
    st.image("https://img.icons8.com/clouds/200/000000/data-configuration.png")
    st.markdown("""
    **檔案格式說明：**
    請確保檔案包含以下欄位（Traditional Chinese）：
    - `線別` (Line)
    - `塗料編號` (Paint Code)
    - `年月` (Month/Year)
    - `用途` (Application)
    - `合計理論耗用` (Theoretical Consumption)
    - `合計實際耗用` (Actual Consumption)
    - `A班績效%`, `B班績效%`, `C班績效%`, `D班績效%` (可選)
    """)
