import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效儀表板", layout="wide")

st.title("📊 塗料生產績效與耗用分析儀表板")
st.markdown("依據 MES/Excel 數據進行系統化分析 (單頁整合視圖)")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] 資料匯入 (Data Load)")
uploaded_file = st.sidebar.file_uploader("請上傳資料檔 (支援 CSV 或 Excel)", type=['csv', 'xlsx'])

def filter_with_all(label, options):
    valid_options = sorted([str(x) for x in options if pd.notnull(x) and str(x).strip() != ''])
    options_list = ["全部 (All)"] + valid_options
    selected = st.sidebar.multiselect(label, options_list, default=["全部 (All)"])
    if "全部 (All)" in selected or len(selected) == 0:
        return valid_options
    return selected

if uploaded_file is not None:
    try:
        # 讀取資料
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, engine='python', sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # ==========================================
        # [ 2. DATA CLEANING & MODELING ]
        # ==========================================
        df = df.dropna(subset=['塗料編號']).copy()
        
        if '年月' in df.columns:
            df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True)

        cat_cols = ['線別', '油漆廠商', '顏色', '樹脂', '用途']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 建立 Measure (計算指標)
        if '合計績效%' not in df.columns and '合計理論耗用' in df.columns and '合計實際耗用' in df.columns:
            df['合計績效%'] = np.where(df['合計實際耗用'] != 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
            
        if '合計實際耗用' in df.columns and '合計理論耗用' in df.columns:
            df['Δ耗用 (Deviation)'] = df['合計實際耗用'] - df['合計理論耗用']
            
        # [ LOGIC CHỈNH SỬA: Nhóm GE00/GE01 để sắp xếp trên biểu đồ ]
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # [ 3. CASCADING FILTERS ]
        # ==========================================
        st.sidebar.header("🔍 [2] 階層式篩選 (Cascading Filters)")
        
        st.sidebar.markdown("**Step 1: 選擇時間**")
        sel_month = filter_with_all("年月 (Month)", df['年月'].unique() if '年月' in df.columns else [])
        df_s1 = df[df['年月'].isin(sel_month)] if '年月' in df.columns else df

        st.sidebar.markdown("**Step 2: 選擇線別**")
        sel_line = filter_with_all("線別 (Line)", df_s1['線別'].unique() if '線別' in df_s1.columns else [])
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)] if '線別' in df_s1.columns else df_s1

        st.sidebar.markdown("**Step 3: 選擇用途**")
        sel_usage = filter_with_all("用途 (Usage)", df_s2['用途'].unique() if '用途' in df_s2.columns else [])
        filtered_df = df_s2[df_s2['用途'].isin(sel_usage)] if '用途' in df_s2.columns else df_s2

        # ==========================================
        # [ 4. DECISION MAKING (KPIs) ]
        # ==========================================
        st.markdown("### 🎯 決策指標 (Decision Making KPIs)")
        if not filtered_df.empty:
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            
            avg_perf = filtered_df['合計績效%'].mean()
            total_delta = filtered_df['Δ耗用 (Deviation)'].sum()
            worst_paint = filtered_df.loc[filtered_df['合計績效%'].idxmin()] if not filtered_df['合計績效%'].isna().all() else None
            
            kpi1.metric("整體平均績效", f"{avg_perf:.2f}%" if pd.notnull(avg_perf) else "N/A")
            kpi2.metric("總差異耗用 (實際 - 理論)", f"{total_delta:,.0f} 單位", "異常超耗" if total_delta > 0 else "耗用節省", delta_color="inverse")
            
            if worst_paint is not None:
                kpi3.metric("需改善塗料 (效能最低)", f"{worst_paint['塗料編號']}", f"{worst_paint['合計績效%']:.2f}%")
            else:
                kpi3.metric("需改善塗料", "無資料")
                
            kpi4.metric("篩選塗料總數", f"{len(filtered_df['塗料編號'].unique())} 支")
        else:
            st.warning("查無符合篩選條件的資料。")

        st.divider()

        # ==========================================
        # [ 5. VISUALIZATION (單頁網格佈局) ]
        # ==========================================
        st.markdown("### 📈 視覺化分析 (Visualization)")
        
        # 準備繪圖用的排序清單 (確保 GE00/GE01 排在一起)
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()

        col_chart1, col_chart2 = st.columns(2)

        # ------------------------------------------
        # 圖表 1: 耗用差異圖表 (Deviation Chart)
        # ------------------------------------------
        with col_chart1:
            st.markdown("#### 📉 耗用差異分析 (Deviation: 實際 - 理論)")
            df_dev = filtered_df.groupby('塗料編號')['Δ耗用 (Deviation)'].sum().reset_index()
            df_dev['顏色標示'] = np.where(df_dev['Δ耗用 (Deviation)'] > 0, '超耗 (Over)', '節省 (Under)')
            
            fig_dev = px.bar(
                df_dev, 
                x='塗料編號', 
                y='Δ耗用 (Deviation)', 
                color='顏色標示',
                color_discrete_map={'超耗 (Over)': '#d73027', '節省 (Under)': '#1a9850'}
            )
            fig_dev.add_hline(y=0, line_dash="solid", line_color="black")
            fig_dev.update_layout(xaxis_title="塗料編號", yaxis_title="差異量 (Δ耗用)", xaxis={'categoryorder':'array', 'categoryarray':sort_order})
            st.plotly_chart(fig_dev, use_container_width=True)

        # ------------------------------------------
        # 圖表 2: 理論與實際比較 (Bar Chart)
        # ------------------------------------------
        with col_chart2:
            st.markdown("#### 📊 耗用量對比 (理論值 vs 實際值)")
            df_bar = filtered_df.groupby('塗料編號')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計理論耗用'], name='理論耗用 (Theoretical)', marker_color='#34495e'))
            fig_bar.add_trace(go.Bar(x=df_bar['塗料編號'], y=df_bar['合計實際耗用'], name='實際耗用 (Actual)', marker_color='#3498db'))
            fig_bar.update_layout(barmode='group', xaxis_title="塗料編號", yaxis_title="耗用量", xaxis={'categoryorder':'array', 'categoryarray':sort_order})
            st.plotly_chart(fig_bar, use_container_width=True)

        # ------------------------------------------
        # 圖表 3: 績效趨勢 (Trend Chart)
        # ------------------------------------------
        st.markdown("#### 📈 隨時間變化的平均績效趨勢")
        if '年月' in filtered_df.columns:
            df_trend = filtered_df.groupby('年月')['合計績效%'].mean().reset_index()
            df_trend = df_trend.sort_values('年月')
            fig_trend = px.line(df_trend, x='年月', y='合計績效%', markers=True)
            fig_trend.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="基準目標 100%")
            fig_trend.update_layout(xaxis_title="年月", yaxis_title="平均績效 (%)")
            st.plotly_chart(fig_trend, use_container_width=True)

        # ------------------------------------------
        # 原始資料檢視
        # ------------------------------------------
        with st.expander("🔍 檢視轉換後的底層資料 (Data View)"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"資料處理時發生錯誤，請確認檔案格式是否符合。錯誤詳情：{e}")

else:
    st.info("👈 請於左側面板上傳您的資料集 (Data Source) 以驅動分析引擎。")
