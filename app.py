import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (多線別與數據清洗加強版)")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # 讀取資料 (dtype=str để tránh lỗi định dạng ban đầu)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        # --- 💡 BƯỚC LÀM SẠCH DỮ LIỆU QUAN TRỌNG ---
        # 1. Dọn dẹp tiêu đề cột
        df.columns = df.columns.str.strip()
        
        # 2. Loại bỏ các dòng hoàn toàn trống (do file CSV dư dấu phẩy)
        df = df.dropna(how='all')
        
        # 3. Loại bỏ các dòng mà giá trị '線別' bị trùng với tên tiêu đề (Lỗi lặp tiêu đề trong file gốc)
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[df['線別'] != '線別']
            df = df[df['線別'] != 'nan']
            df = df[df['線別'] != '']

        # 4. Ép kiểu dữ liệu chữ
        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # 5. Ép kiểu dữ liệu số (Xử lý dấu phẩy ngàn)
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            numeric_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
            
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 6. Tính toán các chỉ số bổ sung
        if '合計績效%' not in df.columns or df['合計績效%'].isnull().all():
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ 3. DASHBOARD FILTER (階層式連動篩選) ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        
        # Step 1: 年月
        months = sorted(df['年月'].unique())
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=months, default=months)
        df_s1 = df[df['年月'].isin(sel_month)]
        
        # Step 2: 線別 (Lúc này sẽ hiện đầy đủ 41CP, 42CP, 43CP nếu có trong file)
        lines = sorted(df_s1['線別'].unique())
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=lines, default=lines)
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        # Step 3: 用途
        usages = sorted(df_s2['用途'].unique())
        sel_usage = st.sidebar.multiselect("3. 選擇用途", options=usages, default=usages)
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)]

        # ==========================================
        # [ 4. DECISION MAKING KPIs ]
        # ==========================================
        st.markdown("### 🎯 決策指標 (Decision Making KPIs)")
        if not filtered_df.empty:
            k1, k2, k3, k4 = st.columns(4)
            avg_perf = filtered_df['合計績效%'].mean()
            total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
            
            k1.metric("平均總績效", f"{avg_perf:.2f}%")
            k2.metric("總差異耗用", f"{total_delta:,.0f}", delta_color="inverse")
            
            valid_perf = filtered_df.dropna(subset=['合計績效%'])
            if not valid_perf.empty:
                worst_row = valid_perf.loc[valid_perf['合計績效%'].idxmin()]
                k3.metric("優先改善對象", f"{worst_row['塗料編號']}", f"{worst_row['合計績效%']:.2f}%")
            
            k4.metric("分析塗料總數", f"{len(filtered_df['塗料編號'].unique())} 支")
        else:
            st.warning("查無符合篩選條件的資料。")

        st.divider()

        # ==========================================
        # [ 5. VISUALIZATION LAYER ]
        # ==========================================
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        
        tab1, tab2, tab3, tab4 = st.tabs(["🎯 績效燈號散佈圖", "📊 耗用量對比", "📉 差異分析", "📈 趨勢分析"])

        with tab1:
            st.subheader("1. 績效散佈趨勢圖 (Scatter)")
            # Loại bỏ giá trị lỗi để tránh crash biểu đồ
            plot_df = filtered_df.dropna(subset=['合計理論耗用', '合計績效%']).copy()
            plot_df = plot_df[plot_df['合計理論耗用'] > 0] 

            if not plot_df.empty:
                # Quy tắc màu sắc theo yêu cầu
                conds = [
                    plot_df['合計績效%'] < 85,
                    (plot_df['合計績效%'] >= 85) & (plot_df['合計績效%'] < 95),
                    (plot_df['合計績效%'] >= 95) & (plot_df['合計績效%'] < 100),
                    plot_df['合計績效%'] >= 100
                ]
                labels = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
                plot_df['績效等級'] = np.select(conds, labels, default='未知')
                
                fig_scatter = px.scatter(
                    plot_df, x='塗料編號', y='合計績效%', color='績效等級',
                    color_discrete_map={'🔴 < 85%': '#d73027', '🟡 85% - 95%': '#fee08b', '🔵 95% - 100%': '#4575b4', '🟢 ≥ 100%': '#1a9850'},
                    size='合計理論耗用',
                    hover_data=['用途', '線別', '合計理論耗用', '合計實際耗用'],
                    size_max=35,
                    category_orders={"績效等級": labels}
                )
                fig_scatter.add_hline(y=100, line_dash="dash", line_color="black")
                fig_scatter.update_layout(
                    xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=sort_order),
                    height=700
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
            else:
                st.warning("⚠️ 無法繪製散佈圖：數據不足或理論值為 0。")

        with tab2:
            df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用 (理論值)', marker_color='#34495e'))
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用 (實際值)', marker_color='#3498db'))
            fig_bar.update_layout(barmode='group', xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=sort_order), height=650)
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            df_dev = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗', '節省')
            fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color', color_discrete_map={'超耗': '#d73027', '節省': '#1a9850'})
            fig_dev.update_layout(xaxis=dict(dtick=1, tickangle=-45, categoryorder='array', categoryarray=sort_order), height=650)
            st.plotly_chart(fig_dev, use_container_width=True)

        with tab4:
            c1, c2 = st.columns(2)
            with c1:
                df_trend = filtered_df.groupby('年月')['合計績效%'].mean().reset_index().sort_values('年月')
                st.plotly_chart(px.line(df_trend, x='年月', y='合計績效%', markers=True, title="月度績效趨勢"), use_container_width=True)
            with c2:
                if '油漆廠商' in filtered_df.columns:
                    df_sup = filtered_df.groupby('油漆廠商')['合計績效%'].mean().reset_index()
                    st.plotly_chart(px.bar(df_sup, x='油漆廠商', y='合計績效%', title="供應商績效比對"), use_container_width=True)

        with st.expander("🔍 數據明細"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"系統發生錯誤：{e}")
else:
    st.info("👈 請上傳 MES 數據檔案 (CSV/Excel) 以驅動分析。")
