import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import math

# ==========================================
# [ 0. PAGE CONFIG & CSS ]
# ==========================================
st.set_page_config(page_title="Paint Performance Dashboard", layout="wide")

st.markdown("""
<style>
.stPlotlyChart { border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); background-color: white; }
[data-testid="stKPIs"] div { border: 1px solid #e6e6e6; border-radius: 8px; padding: 10px; background-color: #f9fbfd; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Paint Production Performance Dashboard")

# ==========================================
# [ 1. DATA SOURCE & DATA LOAD ]
# ==========================================
st.sidebar.header("📂 [1] Data Load")
uploaded_file = st.sidebar.file_uploader("Upload MES/Excel File", type=['csv', 'xlsx'])

if uploaded_file is not None:
    try:
        # Load Data
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig', dtype=str)
        else:
            df = pd.read_excel(uploaded_file, dtype=str)

        # Basic Cleaning
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        
        # Numeric Conversion
        num_cols = ['合計理論耗用', '合計實際耗用', '合計績效%']
        for shift in ['A', 'B', 'C', 'D']:
            num_cols.extend([f'{shift}班理論耗用', f'{shift}班實際耗用', f'{shift}班績效%'])
                
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # Core Calculations
        df['Deviation'] = df['合計實際耗用'] - df['合計理論耗用']
        if '合計績效%' not in df.columns or df['合計績效%'].sum() == 0:
            df['合計績效%'] = np.where(df['合計實際耗用'] > 0, (df['合計理論耗用'] / df['合計實際耗用']) * 100, 0)

        # ==========================================
        # 🔥 [NEW] VIEW SELECTOR (Mandy's Requirement)
        # ==========================================
        st.sidebar.markdown("---")
        st.sidebar.header("🎯 [2] Analysis View")
        view_mode = st.sidebar.radio(
            "Select Analysis Range:",
            ["View 1: Full Analysis (All Items)", 
             "View 2: Critical Deviation (≥ 500kg)"]
        )

        # Apply View Logic
        if "View 2" in view_mode:
            df_working = df[df['Deviation'] >= 500].copy()
            st.sidebar.warning(f"Focusing on {len(df_working)} critical items.")
        else:
            df_working = df.copy()
            st.sidebar.success(f"Displaying all {len(df_working)} items.")

        if df_working.empty:
            st.warning("No data matches the selected criteria.")
            st.stop()

        # Grouping & Legend Logic
        labels_global = ['🔴 < 80%', '🟠 80% - 90%', '🟢 90% - 100%', '🌱 100% - 110%', '🔵 > 110%']
        perf_color_map = {
            '🔴 < 80%': '#990000', '🟠 80% - 90%': '#FF8C00', '🟢 90% - 100%': '#008000',
            '🌱 100% - 110%': '#ADFF2F', '🔵 > 110%': '#00008B'
        }
        df_working['Perf_Grade'] = pd.cut(df_working['合計績效%'], 
                                        bins=[-np.inf, 80, 90, 100, 110, np.inf], 
                                        labels=labels_global)

        # Additional Filters
        st.sidebar.header("🔍 [3] Fine Filters")
        sel_line = st.sidebar.multiselect("Line Selection", options=sorted(df_working['線別'].unique()), default=df_working['線別'].unique())
        filtered_df = df_working[df_working['線別'].isin(sel_line)]

        # ==========================================
        # [ 3. VISUALIZATION ]
        # ==========================================
        # Common Layout Dictionary (Safe - No xaxis key here)
        common_layout = dict(
            plot_bgcolor='white',
            font=dict(color='black', family='Arial', size=12, weight='bold'),
            yaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True, gridcolor='#e6e6e6'),
            xaxis=dict(showline=True, linewidth=2, linecolor='black', mirror=True)
        )

        tab_summary, tab_pareto, tab_detail = st.tabs(["📊 Executive Summary", "🚨 Pareto Analysis", "📈 Consumption Details"])

        with tab_summary:
            k1, k2, k3 = st.columns(3)
            k1.metric("Avg Performance", f"{filtered_df['合計績效%'].mean():.2f}%")
            k2.metric("Total Deviation (kg)", f"{filtered_df['Deviation'].sum():,.0f}", delta_color="inverse")
            k3.metric("Items Count", f"{len(filtered_df)}")
            
            fig_pie = px.pie(filtered_df, names='Perf_Grade', color='Perf_Grade', color_discrete_map=perf_color_map, hole=0.4)
            fig_pie.update_layout(title="<b>Performance Grade Distribution</b>")
            st.plotly_chart(fig_pie, use_container_width=True)

        with tab_pareto:
            pareto_data = filtered_df.sort_values(by='Deviation', ascending=False).head(40)
            fig_p = go.Figure()
            fig_p.add_trace(go.Bar(x=pareto_data['塗料編號'], y=pareto_data['Deviation'], name='Deviation (kg)', marker_color='#990000'))
            fig_p.update_layout(**common_layout)
            fig_p.update_layout(title="<b>Top 40 Material Loss (Pareto)</b>", height=600)
            # FIX: Use update_xaxes to avoid "multiple values" error
            fig_p.update_xaxes(tickangle=-90)
            st.plotly_chart(fig_p, use_container_width=True)

        with tab_detail:
            # Multi-chart logic for many items
            items_per_page = 40
            all_codes = sorted(filtered_df['塗料編號'].unique())
            num_batches = math.ceil(len(all_codes) / items_per_page)
            
            for i in range(num_batches):
                batch_codes = all_codes[i*items_per_page : (i+1)*items_per_page]
                batch_df = filtered_df[filtered_df['塗料編號'].isin(batch_codes)]
                
                fig_b = go.Figure()
                fig_b.add_trace(go.Bar(x=batch_df['塗料編號'], y=batch_df['合計理論耗用'], name='Theoretical', marker_color='#34495e'))
                fig_b.add_trace(go.Bar(x=batch_df['塗料編號'], y=batch_df['合計實際耗用'], name='Actual', marker_color='#3498db'))
                
                fig_b.update_layout(**common_layout)
                fig_b.update_layout(barmode='group', height=500, title=f"<b>Consumption Comparison - Group {i+1}</b>")
                # FIX: Use update_xaxes to avoid "multiple values" error
                fig_b.update_xaxes(tickangle=-90)
                st.plotly_chart(fig_b, use_container_width=True)

        with st.expander("🔍 View Raw Data Table"):
            st.dataframe(filtered_df)

    except Exception as e:
        st.error(f"System Error: {e}")
else:
    st.info("👈 Please upload the MES data file to begin.")
