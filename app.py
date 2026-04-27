import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# 頁面設定
st.set_page_config(page_title="塗料生產績效看板 V3", layout="wide")

st.title("🚀 塗料績效精準分析系統")

# ==========================================
# [ 1. DATA LOAD & CLEANING (修復 Float 錯誤) ]
# ==========================================
st.sidebar.header("📂 資料匯入")
uploaded_file = st.sidebar.file_uploader("上傳數據 (Excel/CSV)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, engine='python', sep=None)
        else:
            df = pd.read_excel(uploaded_file)

        # ---------------------------------------------------------
        # ★ 關鍵修復：強制轉字串，防止 NaN (float) 造成的 iterable 錯誤
        # ---------------------------------------------------------
        text_columns = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in text_columns:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        # 數值轉換
        num_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            num_cols.append(f'{shift}班績效%')
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # 處理 GE00 與 GE01 的組合分類 (已確保 x 絕對是字串)
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE_Group' if any(g in x for g in ['GE00', 'GE01']) else x)

        # 去除 .0 尾數的年月格式 (例: 202603.0 -> 202603)
        if '年月' in df.columns:
            df['年月'] = df['年月'].str.replace(r'\.0$', '', regex=True)

        # ==========================================
        # [ 2. 側邊欄篩選 (精簡版) ]
        # ==========================================
        st.sidebar.header("🔍 篩選控制台")
        
        with st.sidebar.expander("📅 時間與線別", expanded=True):
            sel_month = st.multiselect("年月", options=sorted(df['年月'].unique()), default=df['年月'].unique())
            sel_line = st.multiselect("線別", options=sorted(df['線別'].unique()), default=df['線別'].unique())

        with st.sidebar.expander("🎨 塗料屬性", expanded=True):
            sel_usage = st.multiselect("用途 (主要分類)", options=sorted(df['用途'].unique()), default=df['用途'].unique())
            
            # 若有廠商欄位則加入篩選
            if '油漆廠商' in df.columns:
                sel_supplier = st.multiselect("油漆廠商", options=sorted(df['油漆廠商'].unique()))
            else:
                sel_supplier = []

        # 執行篩選
        mask = (df['年月'].isin(sel_month)) & (df['線別'].isin(sel_line)) & (df['用途'].isin(sel_usage))
        if sel_supplier:
            mask &= (df['油漆廠商'].isin(sel_supplier))
        
        f_df = df[mask].copy()

        # ==========================================
        # [ 3. 異常績效監控 (聚焦熱力圖) ]
        # ==========================================
        st.subheader("⚠️ 異常績效監控 (Heatmap Focus)")
        st.markdown("僅顯示偏離標準 (100%) 的異常塗料，避免畫面雜亂。")
        
        threshold = st.slider("設定異常偏差值 (%)", 0, 20, 5, help="例如設定 5%，則只顯示績效低於 95% 或高於 105% 的塗料")
        lower_bound, upper_bound = 100 - threshold, 100 + threshold

        problematic_df = f_df[(f_df['合計績效%'] < lower_bound) | (f_df['合計績效%'] > upper_bound)]
        
        if not problematic_df.empty:
            shift_perf_cols = [c for c in ['A班績效%', 'B班績效%', 'C班績效%', 'D班績效%'] if c in problematic_df.columns]
            df_heat = problematic_df.melt(id_vars=['塗料編號', '用途'], value_vars=shift_perf_cols, var_name='班別', value_name='績效')
            df_heat['班別'] = df_heat['班別'].str[0] 
            
            # 依據績效由低到高排序
            sort_order = problematic_df.sort_values('合計績效%')['塗料編號'].tolist()

            fig_heat = px.density_heatmap(
                df_heat, x='班別', y='塗料編號', z='績效',
                category_orders={'塗料編號': sort_order},
                color_continuous_scale='RdYlGn',
                text_auto='.1f',
                title=f"異常塗料班別績效對比 (共 {len(problematic_df)} 支異常)",
                height=max(400, len(problematic_df) * 30) # 動態調整高度避免擠壓
            )
            st.plotly_chart(fig_heat, use_container_width=True)
        else:
            st.success("🎉 目前篩選範圍內所有塗料績效均在正常範圍內。")

        # ==========================================
        # [ 4. 用途結構與耗用分析 (Treemap & Bar) ]
        # ==========================================
        st.divider()
        st.subheader("📂 用途分類與耗用結構分析")
        
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**各用途底下塗料耗用比例 (板塊越大=實際耗用越多，顏色越紅=績效越差)**")
            # 處理掉包含 NaN 的列，以確保 Treemap 繪製正常
            tree_df = f_df.dropna(subset=['合計實際耗用', '合計績效%'])
            if not tree_df.empty:
                fig_tree = px.treemap(
                    tree_df,
                    path=[px.Constant("所有用途"), '用途', '塗料編號'],
                    values='合計實際耗用',
                    color='合計績效%',
                    color_continuous_scale='RdYlGn',
                    color_continuous_midpoint=100
                )
                fig_tree.update_layout(margin=dict(t=30, l=10, r=10, b=10))
                st.plotly_chart(fig_tree, use_container_width=True)
            else:
                st.warning("無足夠數據繪製用途樹狀圖。")

        with col_b:
            st.markdown("**各用途耗用對比 (理論值 vs 實際)**")
            usage_sum = f_df.groupby('用途')[['合計理論耗用', '合計實際耗用']].sum().reset_index()
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(name='理論耗用 (理論值)', x=usage_sum['用途'], y=usage_sum['合計理論耗用'], marker_color='#34495e'))
            fig_comp.add_trace(go.Bar(name='實際耗用 (實際值)', x=usage_sum['用途'], y=usage_sum['合計實際耗用'], marker_color='#3498db'))
            fig_comp.update_layout(barmode='group')
            st.plotly_chart(fig_comp, use_container_width=True)

        # Data view
        with st.expander("🔍 檢視過濾後的明細資料"):
            st.dataframe(f_df)

    except Exception as e:
        st.error(f"資料處理發生未預期的錯誤：{e}")
else:
    st.info("💡 請從左側邊欄上傳資料檔案 (Data Source) 進行分析。")
