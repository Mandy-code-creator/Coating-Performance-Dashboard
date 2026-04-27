import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板 V2", layout="wide")

# 自定義 CSS 優化介面
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 塗料績效精準分析系統 (聚焦異常管理)")

# ==========================================
# [ DATA LOAD & CLEANING ]
# ==========================================
uploaded_file = st.sidebar.file_uploader("📂 載入數據 (Excel/CSV)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, engine='python', sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # 資料清洗與標準化
        df['塗料編號'] = df['塗料編號'].astype(str).str.strip()
        df['用途'] = df['用途'].fillna('未定義').astype(str)
        df['年月'] = df['年月'].astype(str).str.replace(r'\.0$', '', regex=True)
        
        # 數值轉換
        num_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for shift in ['A', 'B', 'C', 'D']:
            num_cols.append(f'{shift}班績效%')
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # [ LOGIC CHỈNH SỬA: Nhóm GE00/GE01 theo yêu cầu ]
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE_Group' if any(g in x for g in ['GE00', 'GE01']) else x)

        # ==========================================
        # [ SIDEBAR OPTIMIZATION: Gọn hóa bộ lọc ]
        # ==========================================
        st.sidebar.header("🔍 篩選控制台")
        
        with st.sidebar.expander("📅 時間與線別選擇", expanded=True):
            sel_month = st.multiselect("年月", options=sorted(df['年月'].unique()), default=df['年月'].unique()[:2])
            sel_line = st.multiselect("線別", options=sorted(df['線別'].unique()), default=df['線別'].unique())

        with st.sidebar.expander("🎨 塗料屬性選擇", expanded=True):
            sel_usage = st.multiselect("用途 (主要分類)", options=sorted(df['用途'].unique()), default=df['用途'].unique())
            sel_supplier = st.multiselect("油漆廠商", options=sorted(df['油漆廠商'].unique()))

        # 應用篩選
        mask = (df['年月'].isin(sel_month)) & (df['線別'].isin(sel_line)) & (df['用途'].isin(sel_usage))
        if sel_supplier:
            mask &= (df['油漆廠商'].isin(sel_supplier))
        
        f_df = df[mask].copy()

        # ==========================================
        # [ ANALYSIS LAYER: Heatmap Cải tiến ]
        # ==========================================
        st.subheader("⚠️ 異常績效監控 (Heatmap Focus)")
        
        col_ctrl1, col_ctrl2 = st.columns([2, 1])
        with col_ctrl1:
            threshold = st.slider("設定異常偏差值 (%)", 0, 20, 5, help="顯示偏離目標 100% 超過此範圍的編號")
        
        lower_bound = 100 - threshold
        upper_bound = 100 + threshold

        # Filter ra các mã có vấn đề
        problematic_df = f_df[(f_df['合計績效%'] < lower_bound) | (f_df['合計績效%'] > upper_bound)]
        
        if not problematic_df.empty:
            # Unpivot để vẽ Heatmap cho các ca
            shift_perf_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in problematic_df.columns]
            df_heat = problematic_df.melt(id_vars=['塗料編號', '用途'], value_vars=shift_perf_cols, var_name='班別', value_name='績效')
            df_heat['班別'] = df_heat['班別'].str[0] # Lấy A, B, C, D
            
            # Sắp xếp mã sơn có hiệu suất thấp nhất lên trên cùng
            sort_order = problematic_df.sort_values('合計績效%')['塗料編號'].tolist()

            fig_heat = px.density_heatmap(
                df_heat, x='班別', y='塗料編號', z='績效',
                category_orders={'塗料編號': sort_order},
                color_continuous_scale='RdYlGn',
                text_auto='.1f',
                title=f"異常塗料班別績效對比 (目前顯示 {len(problematic_df)} 支異常碼)",
                aspect="auto"
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.success("🎉 目前篩選範圍內所有塗料績效均在正常範圍內。")

        # ==========================================
        # [ ANALYSIS LAYER: Phân tích theo 用途 ]
        # ==========================================
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("📂 用途分類績效分析")
            usage_analysis = f_df.groupby('用途')['合計績效%'].agg(['mean', 'count']).reset_index()
            fig_usage = px.bar(
                usage_analysis, x='用途', y='mean', color='mean',
                text_auto='.1f',
                labels={'mean': '平均績效 (%)', 'count': '樣品數'},
                title="各用途平均績效 (基準線: 100%)",
                color_continuous_scale='Viridis'
            )
            fig_usage.add_hline(y=100, line_dash="dash", line_color="red")
            st.plotly_chart(fig_usage, use_container_width=True)

        with col_b:
            st.subheader("🏗️ 耗用結構比對 (理論值 vs 實際)")
            usage_sum = f_df.groupby('用途')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(name='理論耗用 (理論值)', x=usage_sum['用途'], y=usage_sum['合計理論耗用'], marker_color='#34495e'))
            fig_comp.add_trace(go.Bar(name='實際耗用 (實際值)', x=usage_sum['用途'], y=usage_sum['合計實際耗用'], marker_color='#3498db'))
            fig_comp.update_layout(barmode='group', title="各用途總耗用量對比")
            st.plotly_chart(fig_comp, use_container_width=True)

        # Data view
        with st.expander("🔍 檢視過濾後的明細資料"):
            st.dataframe(f_df[['線別', '塗料編號', '用途', '合計理論耗用', '合計實際耗用', '合計績效%']])

    except Exception as e:
        st.error(f"資料格式錯誤：{e}")
else:
    st.info("💡 請從側邊欄上傳資料開始分析。")
