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
        # 1. 讀取資料
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)

        # ==========================================
        # 2. 資料清洗 (DATA CLEANING - SỬA LỖI Ở ĐÂY)
        # ==========================================
        
        # 2a. Xử lý cột 年月 (Ép toàn bộ về kiểu chuỗi/chữ để không bị lỗi khi sort)
        if '年月' in df.columns:
            df['年月'] = df['年月'].fillna('未定義').astype(str)

        # 2b. Xử lý các cột dạng Line, 用途 (Ép về chuỗi, loại bỏ ô trống)
        if '線別' in df.columns:
            df['線別'] = df['線別'].fillna('未知').astype(str)
        if '用途' in df.columns:
            df['用途'] = df['用途'].fillna('未知').astype(str)

        # 2c. Ép các cột số lượng, hiệu suất về định dạng SỐ (Numeric). 
        # Nếu có chữ lạ (như "-", "N/A", "#DIV/0!"), nó sẽ tự động biến thành rỗng (NaN)
        numeric_cols = [
            '合計理論耗用', '合計實際耗用', '設定績效%', 
            'A班理論耗用', 'A班實際耗用', 'A班績效%',
            'B班理論耗用', 'B班實際耗用', 'B班績效%',
            'C班理論耗用', 'C班實際耗用', 'C班績效%',
            'D班理論耗用', 'D班實際耗用', 'D班績效%',
            '合計績效%'
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 2d. Tính toán tổng hiệu suất (nếu file gốc chưa có)
        if '合計績效%' not in df.columns and '合計理論耗用' in df.columns and '合計實際耗用' in df.columns:
            # Tránh lỗi chia cho 0
            df['合計績效%'] = df.apply(
                lambda row: (row['合計理論耗用'] / row['合計實際耗用'] * 100) if pd.notnull(row['合計實際耗用']) and row['合計實際耗用'] != 0 else None, 
                axis=1
            )
        
        # Xóa các dòng không có dữ liệu Hiệu suất để vẽ biểu đồ không bị lỗi
        df_clean = df.dropna(subset=['合計績效%'])

        # ==========================================
        # 3. 側邊欄：篩選器 (Sidebar Filters)
        # ==========================================
        st.sidebar.header("🔍 資料篩選 (Data Filters)")
        
        lines = df_clean['線別'].unique() if '線別' in df_clean.columns else []
        months = sorted(df_clean['年月'].unique()) if '年月' in df_clean.columns else []
        usages = df_clean['用途'].unique() if '用途' in df_clean.columns else []

        selected_line = st.sidebar.multiselect("選擇線別 (Line)", options=lines, default=lines)
        selected_month = st.sidebar.multiselect("選擇年月 (Month)", options=months, default=months)
        selected_usage = st.sidebar.multiselect("選擇用途 (Usage)", options=usages, default=usages)

        # 執行篩選
        mask = df_clean['線別'].isin(selected_line) & df_clean['年月'].isin(selected_month) & df_clean['用途'].isin(selected_usage)
        filtered_df = df_clean[mask]

        # ==========================================
        # 4. 主畫面 (Main Panel)
        # ==========================================
        st.title("📊 塗料績效管理儀表板")
        st.info(f"當前載入檔案: {uploaded_file.name}")

        st.markdown("### 📌 關鍵績效指標 (KPI)")
        col1, col2, col3, col4 = st.columns(4)

        if not filtered_df.empty:
            avg_perf = filtered_df['合計績效%'].mean()
            best_paint = filtered_df.loc[filtered_df['合計績效%'].idxmax()]
            worst_paint = filtered_df.loc[filtered_df['合計績效%'].idxmin()]

            col1.metric("平均總績效", f"{avg_perf:.2f}%", f"{avg_perf - 100:.2f}%")
            col2.metric("塗料編號數量", len(filtered_df))
            col3.metric("最高績效編號", best_paint['塗料編號'], f"{best_paint['合計績效%']:.2f}%")
            col4.metric("最低績效編號", worst_paint['塗料編號'], f"{worst_paint['合計績效%']:.2f}%")
            
            st.divider()

            st.markdown("### 1. 各塗料編號績效散佈圖 (基準: 100%)")
            fig_scatter = px.scatter(
                filtered_df, 
                x='塗料編號', 
                y='合計績效%', 
                color='用途' if '用途' in filtered_df.columns else None,
                hover_data=['線別', '年月', '合計理論耗用', '合計實際耗用']
            )
            fig_scatter.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="目標 (100%)")
            fig_scatter.update_layout(xaxis_title="塗料編號", yaxis_title="合計績效 (%)")
            st.plotly_chart(fig_scatter, use_container_width=True)

            st.markdown("### 2. 各班別績效分佈比較 (A, B, C, D 班)")
            shift_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in filtered_df.columns]
            if shift_cols:
                melted_df = pd.melt(filtered_df, value_vars=shift_cols, var_name='班別', value_name='績效%')
                # Bỏ qua các giá trị rỗng khi vẽ Boxplot
                melted_df = melted_df.dropna(subset=['績效%']) 
                if not melted_df.empty:
                    fig_box = px.box(melted_df, x='班別', y='績效%', color='班別')
                    fig_box.add_hline(y=100, line_dash="dash", line_color="red")
                    st.plotly_chart(fig_box, use_container_width=True)
                else:
                    st.warning("無有效的班別績效數據可供繪圖。")

            st.markdown("### 📋 詳細資料明細")
            st.dataframe(filtered_df)
        else:
            st.warning("篩選後無符合條件之數據。")

    except Exception as e:
        st.error(f"檔案處理發生錯誤。請確認資料格式。錯誤細節: {e}")

else:
    st.title("📊 塗料績效管理儀表板")
    st.warning("👈 請在左側欄位上傳數據檔案 (Excel 或 CSV) 以開始分析。")
