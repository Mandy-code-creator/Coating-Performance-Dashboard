import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (精簡高效版)")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # --- 💡 NÂNG CẤP BỘ ĐỌC FILE TẠI ĐÂY ---
        if uploaded_file.name.endswith('.csv'):
            # Ép đọc chuẩn utf-8, tự động bỏ qua các dòng bị lỗi cấu trúc nặng thay vì sụp hệ thống
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', on_bad_lines='skip', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        # 1. Dọn dẹp tiêu đề cột (Xóa khoảng trắng bị dư lúc export)
        df.columns = df.columns.str.strip()

        # 🛠️ DEBUG TOOL: Hộp thoại xem dữ liệu thô
        with st.expander("🛠️ 檢查原始數據 (Kiểm tra dữ liệu gốc) - Bấm vào đây để xem file có đủ Line không"):
            st.markdown("👉 *Nếu bảng dưới đây chỉ có Line 41CP, nghĩa là file CSV từ hệ thống của bạn xuất ra đang bị thiếu. Bạn cần xuất lại file.*")
            st.dataframe(df.head(100))

        # ==========================================
        # [ 2. DATA CLEANING & MODELING ]
        # ==========================================
        # 2. Chuẩn hóa cột Line (線別) và Mã sơn (塗料編號) - Xóa mọi dấu cách thừa
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip().str.upper()
            df = df[~df['線別'].isin(['NAN', 'NONE', ''])] # Loại bỏ dòng trống

        if '塗料編號' in df.columns:
            df['塗料編號'] = df['塗料編號'].astype(str).str.strip()
            df = df[~df['塗料編號'].isin(['NAN', 'NONE', ''])]
            
        # Dọn dẹp cột thời gian
        if '年月' in df.columns:
            df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

        # Dọn dẹp các cột phân loại
        cat_cols = ['油漆廠商', '顏色', '樹脂', '用途']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # 3. Chuẩn hóa các cột Số lượng (Ép kiểu an toàn, xóa dấu phẩy ngàn nếu có)
        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            numeric_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
            
        for col in numeric_cols:
            if col in df.columns:
                # Xóa dấu phẩy của số hàng ngàn (vd: 2,042 -> 2042) để ép kiểu không bị lỗi
                df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 4. Tính toán Chỉ số (Sử dụng Khái niệm Lý thuyết / 理論值)
        if '合計績效%' not in df.columns and '合計理論耗用' in df.columns and '合計實際耗用' in df.columns:
            df['合計績效%'] = np.where(df['合計實際耗用'] != 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
            
        if '合計實際耗用' in df.columns and '合計理論耗用' in df.columns:
            df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']

        # GE00 與 GE01 群組化邏輯
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ 3. DASHBOARD FILTER (階層式連動篩選) ]
        # ==========================================
        st.sidebar.header("🔍 [2] 篩選控制台")
        
        # Step 1: 時間
        months = sorted(df['年月'].dropna().unique()) if '年月' in df.columns else []
        sel_month = st.sidebar.multiselect("1. 選擇年月", options=months, default=months)
        df_s1 = df[df['年月'].isin(sel_month)]
        
        # Step 2: 線別
        lines = sorted(df_s1['線別'].dropna().unique()) if '線別' in df_s1.columns else []
        sel_line = st.sidebar.multiselect("2. 選擇線別", options=lines, default=lines)
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        # Step 3: 用途
        usages = sorted(df_s2['用途'].dropna().unique()) if '用途' in df_s2.columns else []
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
            worst_paint = filtered_df.loc[filtered_df['合計績效%'].idxmin()] if not filtered_df['合計績效%'].isna().all() else None
            
            k1.metric("平均總績效 (理論值基準)", f"{avg_perf:.2f}%")
            k2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f}", delta=f"{total_delta:,.0f}", delta_color="inverse")
            if worst_paint is not None:
                k3.metric("優先改善對象", f"{worst_paint['塗料編號']}", f"{worst_paint['合計績效%']:.2f}%")
            k4.metric("分析塗料總數", f"{len(filtered_df['塗料編號'].unique())} 支")
        
        st.divider()

        # ==========================================
        # [ 5. VISUALIZATION LAYER ]
        # ==========================================
        st.markdown("### 📈 核心視覺化分析")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "🎯 績效燈號散佈圖 (Scatter)", 
            "📊 理論與實際比較 (Bar)", 
            "📉 耗用差異分析 (Deviation)", 
            "📈 趨勢與廠商分析 (Trend)"
        ])

        with tab1:
            st.subheader("1. 績效散佈趨勢圖 (各塗料編號)")
            st.markdown("""
            **💡 績效燈號規則：**
            🔴 < 85% (嚴重超耗) | 🟡 85-95% (注意) | 🔵 95-100% (接近理論值) | 🟢 ≥ 100% (達標/節省)
            *(圓圈越大代表「理論耗用量」越高，大紅圈為首要改善目標)*
            """)
            
            if not filtered_df.empty:
                plot_df = filtered_df.copy()
                conds = [
                    plot_df['合計績效%'] < 85,
                    (plot_df['合計績效%'] >= 85) & (plot_df['合計績效%'] < 95),
                    (plot_df['合計績效%'] >= 95) & (plot_df['合計績效%'] < 100),
                    plot_df['合計績效%'] >= 100
                ]
                labels = ['🔴 < 85%', '🟡 85% - 95%', '🔵 95% - 100%', '🟢 ≥ 100%']
                plot_df['績效等級'] = np.select(conds, labels, default='未知')
                
                c_map = {
                    '🔴 < 85%': '#d73027', 
                    '🟡 85% - 95%': '#fee08b', 
                    '🔵 95% - 100%': '#4575b4', 
                    '🟢 ≥ 100%': '#1a9850'
                }
                
                fig_scatter = px.scatter(
                    plot_df, x='塗料編號', y='合計績效%', color='績效等級',
                    color_discrete_map=c_map,
                    size='合計理論耗用',
                    hover_data=['用途', '線別', '合計理論耗用', '合計實際耗用'],
                    size_max=35,
                    category_orders={"績效等級": labels}
                )
                fig_scatter.add_hline(y=100, line_dash="dash", line_color="black")
                
                fig_scatter.update_layout(
                    xaxis=dict(
                        categoryorder='array', 
                        categoryarray=sort_order,
                        dtick=1,            
                        tickangle=-45       
                    ),
                    height=700              
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

        with tab2:
            st.subheader("2. 理論耗用 vs 實際耗用 (總量比較)")
            df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用', marker_color='#34495e'))
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用', marker_color='#3498db'))
            
            fig_bar.update_layout(
                barmode='group', 
                xaxis=dict(
                    categoryorder='array', 
                    categoryarray=sort_order,
                    dtick=1,            
                    tickangle=-45       
                ),
                height=650
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab3:
            st.subheader("3. 耗用差異 (Δ 實際 - 理論)")
            df_dev = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            df_dev['Color'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗 (Red)', '節省 (Green)')
            fig_dev = px.bar(df_dev, x='塗料編號', y='Δ耗用 (Deviation)', color='Color',
                             color_discrete_map={'超耗 (Red)': '#d73027', '節省 (Green)': '#1a9850'})
            fig_dev.add_hline(y=0, line_color="black")
            
            fig_dev.update_layout(
                xaxis=dict(
                    categoryorder='array', 
                    categoryarray=sort_order,
                    dtick=1,            
                    tickangle=-45       
                ),
                height=650
            )
            st.plotly_chart(fig_dev, use_container_width=True)

        with tab4:
            st.subheader("4. 趨勢與廠商分析")
            c1, c2 = st.columns(2)
            with c1:
                if '年月' in filtered_df.columns:
                    df_trend = filtered_df.groupby('年月')['合計績效%'].mean().reset_index().sort_values('年月')
                    st.plotly_chart(px.line(df_trend, x='年月', y='合計績效%', markers=True, title="月度績效趨勢"), use_container_width=True)
            with c2:
                if '油漆廠商' in filtered_df.columns:
                    df_sup = filtered_df.groupby('油漆廠商')['合計績效%'].mean().reset_index()
                    st.plotly_chart(px.bar(df_sup, x='油漆廠商', y='合計績效%', color='合計績效%', title="供應商平均績效"), use_container_width=True)

        with st.expander("🔍 數據明細檢視"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"分析失敗，請檢查資料格式：{e}")
else:
    st.info("👈 請於左側面板上傳 MES 數據檔案。")
