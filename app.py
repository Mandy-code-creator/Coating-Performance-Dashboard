import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (分段圖表版 - 每頁 40 支)")

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

        # 1. 清理數據
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # 2. 數值轉換 (Xử lý dấu phẩy)
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 3. 計算差異
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ 2. DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        
        months = sorted(df['年月'].unique())
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=months, default=months)
        df_s1 = df[df['年月'].isin(sel_month)]
        
        lines = sorted(df_s1['線別'].unique())
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=lines, default=lines)
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        usages = sorted(df_s2['用途'].unique())
        sel_usage = st.sidebar.multiselect("3. 選擇用途", options=usages, default=usages)
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 3. PAGINATION LOGIC (每 40 支分一組) ]
        # ==========================================
        # Lấy danh sách mã sơn đã sắp xếp theo nhóm GE00/01
        all_paints = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(all_paints)
        
        items_per_page = 40
        num_pages = int(np.ceil(total_paints / items_per_page))

        if total_paints > 0:
            st.sidebar.divider()
            st.sidebar.header("📦 [3] 圖表分段顯示")
            page = st.sidebar.number_input(f"選擇頁數 (共 {num_pages} 頁)", min_value=1, max_value=max(1, num_pages), step=1)
            
            # Cắt danh sách mã sơn cho trang hiện tại
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            current_paints = all_paints[start_idx:end_idx]
            
            # Lọc dataframe chỉ lấy các mã sơn trong trang hiện tại
            page_df = filtered_df[filtered_df['塗料編號'].isin(current_paints)]
            
            st.info(f"💡 Đang hiển thị mã sơn từ thứ {start_idx+1} đến {min(end_idx, total_paints)} (Tổng cộng {total_paints} mã sơn)")

            # ==========================================
            # [ 4. VISUALIZATION ]
            # ==========================================
            tab1, tab2, tab3 = st.tabs(["🎯 績效燈號 (Scatter)", "📊 耗用量對比 (Bar)", "📉 差異分析 (Deviation)"])

            with tab1:
                plot_df = page_df.dropna(subset=['合計理論耗用', '合計績效%']).copy()
                plot_df = plot_df[plot_df['合計理論耗用'] > 0] 

                if not plot_df.empty:
                    conds = [plot_df['合計績效%'] < 85, (plot_df['合計績效%'] < 95), (plot_df['合計績效%'] < 100), plot_df['合計績效%'] >= 100]
                    labels = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
                    plot_df['績效等級'] = np.select(conds, labels, default='未知')
                    
                    fig_scatter = px.scatter(
                        plot_df, x='塗料編號', y='合計績效%', color='績效等級',
                        color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                        size='合計理論耗用', hover_data=['線別', '合計理論耗用'], size_max=30,
                        category_orders={"績效等級": labels}
                    )
                    fig_scatter.add_hline(y=100, line_dash="dash")
                    fig_scatter.update_layout(xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=current_paints), height=600)
                    st.plotly_chart(fig_scatter, use_container_width=True)

            with tab2:
                df_bar = page_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用', marker_color='#34495e'))
                fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用', marker_color='#3498db'))
                fig_bar.update_layout(barmode='group', xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=current_paints), height=600)
                st.plotly_chart(fig_bar, use_container_width=True)

            with tab3:
                df_dev = page_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
                df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
                fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
                fig_dev.update_layout(xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=current_paints), height=600)
                st.plotly_chart(fig_dev, use_container_width=True)

        else:
            st.warning("請先選擇篩選條件。")

    except Exception as e:
        st.error(f"錯誤：{e}")
else:
    st.info("👈 請上傳資料檔。")
