import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# [ 0. PAGE CONFIG & CSS ]
# ==========================================
st.set_page_config(page_title="塗料生產績效看板", layout="wide")

st.markdown("""
<style>
.stPlotlyChart {
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    background-color: white;
    overflow: hidden;
}
[data-testid="stKPIs"] div{
    border: 1px solid #e6e6e6;
    border-radius: 8px;
    padding: 10px;
    background-color: #f9fbfd;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 Paint Production Performance & Consumption Analysis")
st.markdown("<b>MES/Excel Data Systematic Analysis</b>", unsafe_allow_html=True)

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] Data Load")
uploaded_file = st.sidebar.file_uploader("Upload MES File (CSV/XLSX)", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        if '線別' in df.columns:
            df['線別'] = df['線別'].astype(str).str.strip()
            df = df[(df['線別'] != '線別') & (df['線別'] != 'nan') & (df['線別'] != '')]

        cat_cols = ['線別', '塗料編號', '用途', '年月', '油漆廠商', '顏色', '樹脂']
        for col in cat_cols:
            if col in df.columns:
                df[col] = df[col].fillna('未定義').astype(str).str.strip()

        numeric_cols = ['合計理論耗用', '合計實際耗用', '合計績效%', '設定績效%']
        for shift in ['A', 'B', 'C', 'D']:
            cols = [f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%']
            numeric_cols.extend(cols)
                
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # Tính toán Deviation (Lượng hao hụt)
        df['Deviation'] = df['合計實際耗用'] - df['合計理論耗用']
        
        if '合計績效%' not in df.columns or df['合計績效%'].sum() == 0:
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, np.nan)
        
        df['Sort_Group'] = df['塗料編號'].apply(lambda x: 'GE00_01_Group' if any(g in str(x) for g in ['GE00', 'GE01']) else str(x))

        # ==========================================
        # 🔥 [NEW] VIEW SELECTOR (2 CHẾ ĐỘ XEM)
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [2] Analysis View")
        view_mode = st.sidebar.radio(
            "Select View Mode:",
            ["View 1: All Items (Toàn bộ)", 
             "View 2: Deviation ≥ 500 (Hao hụt ≥ 500)"]
        )

        # Áp dụng bộ lọc View
        if "View 2" in view_mode:
            df_active = df[df['Deviation'] >= 500].copy()
            st.sidebar.warning(f"Analysis focused on {len(df_active)} critical items.")
        else:
            df_active = df.copy()
            st.sidebar.success(f"Analyzing total {len(df_active)} items.")

        # Phân cấp màu sắc
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {
            '🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000',
            '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'
        }
        df_active['績效等級'] = pd.cut(df_active['合計績效%'], bins=[-np.inf, 80, 90, 100, 110, np.inf], labels=labels_global)

        # ==========================================
        # [ 2. DASHBOARD FILTER ]
        # ==========================================
        st.sidebar.header("🔍 [3] Filters")
        available_months = sorted(df_active['年月'].unique(), reverse=True)
        sel_month = st.sidebar.multiselect("Select Year-Month", options=available_months, default=available_months[:1])
        df_s1 = df_active[df_active['年月'].isin(sel_month)]
        
        sel_line = st.sidebar.multiselect("Select Line", options=sorted(df_s1['線別'].unique()), default=df_s1['線別'].unique())
        df_s2 = df_s1[df_s1['線別'].isin(sel_line)]
        
        filtered_df = df_s2.copy()

        # ==========================================
        # [ 3. VISUALIZATION ]
        # ==========================================
        st.markdown(f"### 📈 Analysis Results ({view_mode})")
        
        sort_order = filtered_df.sort_values(by=['Sort_Group', '塗料編號'])['塗料編號'].unique().tolist()
        total_paints = len(sort_order)
        items_per_chart = 40
        num_charts = math.ceil(total_paints / items_per_chart) if items_per_chart else 0

        tab_overview, tab_pareto, tab_rootcause, tab_scatter, tab_bar, tab_dev = st.tabs([
            "🍩 [Summary]", "🚨 [Pareto]", "📦 [Stability]", "🎯 [Scatter Map]", "📊 [Comparison]", "📉 [Deviation]"
        ])

        # Common Layout (Tránh lỗi xaxis bằng cách không khai báo xaxis trực tiếp trong dict này)
        common_layout = dict(
            plot_bgcolor='white',
            font=dict(color='black', family='Arial', size=13, weight='bold'),
            yaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True, gridcolor='#e6e6e6')
        )

        with tab_overview:
            if not filtered_df.empty:
                k1, k2, k3 = st.columns(3)
                k1.metric("Avg Perf (%)", f"{filtered_df['合計績效%'].mean():.2f}%")
                k2.metric("Total Deviation (kg)", f"{filtered_df['Deviation'].sum():,.0f}", delta_color="inverse")
                k3.metric("Filtered Items", f"{len(filtered_df)}")
            
            st.divider()
            col_pie, col_table = st.columns([4, 6])
            with col_pie:
                pie_data = filtered_df['績效等級'].value_counts().reset_index()
                fig_pie = px.pie(pie_data, values='count', names='績效等級', color='績效等級', color_discrete_map=perf_color_map, hole=0.4)
                fig_pie.update_layout(title="<b>Performance Grade Distribution</b>")
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_table:
                st.markdown("##### 🚨 Top 10 Over-consumption")
                top10 = filtered_df.sort_values(by='Deviation', ascending=False).head(10)
                st.dataframe(top10[['塗料編號', '線別', '合計績效%', 'Deviation']].style.format({'合計績效%': '{:.2f}%', 'Deviation': '{:,.0f}'}), hide_index=True)

        with tab_pareto:
            pareto_df = filtered_df[filtered_df['Deviation'] > 0].sort_values(by='Deviation', ascending=False).head(40)
            if not pareto_df.empty:
                fig_p = go.Figure()
                fig_p.add_trace(go.Bar(x=pareto_df['塗料編號'], y=pareto_df['Deviation'], marker_color='#990000', name="Over-used"))
                fig_p.update_layout(**common_layout)
                fig_p.update_layout(title="<b>Pareto Analysis (Top 40 Material Loss)</b>")
                fig_p.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_p, use_container_width=True)

        with tab_rootcause:
            col1, col2 = st.columns(2)
            with col1:
                fig_b1 = px.box(filtered_df, x='油漆廠商', y='合計績效%', color='油漆廠商', points="all")
                fig_b1.update_layout(**common_layout, title="<b>Supplier Stability</b>")
                st.plotly_chart(fig_b1, use_container_width=True)
            with col2:
                shift_cols = [c for c in filtered_df.columns if '班績效%' in c]
                if shift_cols:
                    shift_df = pd.melt(filtered_df, id_vars=['塗料編號'], value_vars=shift_cols, var_name='Shift', value_name='Perf%')
                    fig_b2 = px.box(shift_df, x='Shift', y='Perf%', color='Shift', points="all")
                    fig_b2.update_layout(**common_layout, title="<b>Shift Stability</b>")
                    st.plotly_chart(fig_b2, use_container_width=True)

        with tab_scatter:
            fig_sc = px.scatter(filtered_df, x='塗料編號', y='合計績效%', color='績效等級', color_discrete_map=perf_color_map, size='合計理論耗用')
            fig_sc.add_hline(y=100, line_dash="dash", line_color="red")
            fig_sc.update_layout(**common_layout, height=600, title="<b>Overall Performance Map</b>")
            fig_sc.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
            st.plotly_chart(fig_sc, use_container_width=True)

        with tab_bar:
            for i in range(num_charts):
                batch = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch)]
                fig_bar = go.Figure()
                fig_bar.add_trace(go.Bar(x=batch_df['塗料編號'], y=batch_df['合計理論耗用'], name='Theoretical', marker_color='#34495e'))
                fig_bar.add_trace(go.Bar(x=batch_df['塗料編號'], y=batch_df['合計實際耗用'], name='Actual', marker_color='#3498db'))
                fig_bar.update_layout(**common_layout, barmode='group', title=f"Group {i+1} Comparison")
                fig_bar.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab_dev:
            for i in range(num_charts):
                batch = sort_order[i*40 : (i+1)*40]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch)].copy()
                batch_df['Type'] = np.where(batch_df['Deviation'] > 0, 'Over', 'Save')
                fig_d = px.bar(batch_df, x='塗料編號', y='Deviation', color='Type', color_discrete_map={'Over': '#990000', 'Save': '#008000'})
                fig_d.update_layout(**common_layout, title=f"Group {i+1} Deviation")
                fig_d.update_xaxes(tickangle=-90, showline=True, linewidth=2, linecolor='black')
                st.plotly_chart(fig_d, use_container_width=True)

        with st.expander("🔍 Raw Data View"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Please upload MES data to start.")
