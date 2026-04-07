import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import io

st.set_page_config(
    page_title="Sales Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">Sales Analytics Dashboard</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload your Verifone CSV file", 
    type=['csv'],
    help="Upload the CSV file downloaded from Verifone portal"
)

VENDOR_MAP = {
    '809-990-578': 'Kacao',
    '809-990-535': 'Frost&Froth',
    '809-990-722': 'FatBelly',
    '809-990-587': 'Broth',
    '809-990-622': 'Kohitayn'
}

INCLUDED_STATUSES = [
    'PARTIAL SALE SETTLED',
    'SALE SETTLED',
    'SALE SETTLEMENT_REQUESTED'
]

def load_and_process_data(df):
    """Load and process the dataframe - ONLY INCLUDING SPECIFIED STATUSES"""
    
    st.write("### Debug: Statuses found in your CSV")
    unique_statuses = df['status'].unique()
    st.write(unique_statuses)
    
    df['status_upper'] = df['status'].str.upper()
    
    df_filtered = df[df['status_upper'].isin([s.upper() for s in INCLUDED_STATUSES])].copy()
    
    st.write(f"### Filter Results")
    st.write(f"Total rows in CSV: {len(df)}")
    st.write(f"Rows after filtering (only {', '.join(INCLUDED_STATUSES)}): {len(df_filtered)}")
    
    if df_filtered.empty:
        st.error(f"No transactions found with statuses: {', '.join(INCLUDED_STATUSES)}")
        return pd.DataFrame()
    
    df_filtered['created_at_date'] = pd.to_datetime(df_filtered['created_at_date'], format='%Y-%m-%d', errors='coerce')
    df_filtered['datetime'] = pd.to_datetime(
        df_filtered['created_at_date'].astype(str) + ' ' + df_filtered['created_at_time'], 
        format='%Y-%m-%d %H:%M:%S',
        errors='coerce'
    )
    
    df_filtered['hour'] = df_filtered['datetime'].dt.hour
    df_filtered['date'] = df_filtered['datetime'].dt.date
    
    if 'device_serial_number' in df_filtered.columns:
        df_filtered['vendor_name'] = df_filtered['device_serial_number'].map(VENDOR_MAP)
    else:
        st.error("Column 'device_serial_number' not found in your CSV")
        return pd.DataFrame()
    
    df_filtered = df_filtered.dropna(subset=['datetime', 'Curr.amount'])
    
    st.write("### Status Breakdown (After Filtering)")
    status_counts = df_filtered['status'].value_counts()
    st.dataframe(status_counts)
    
    return df_filtered

def calculate_metrics(df):
    """Calculate all metrics"""
    
    total_sales = df['Curr.amount'].sum()
    
    total_transactions = len(df)
    
    avg_transaction = total_sales / total_transactions if total_transactions > 0 else 0
    
    unique_days = df['date'].nunique()
    
    vendor_sales = df.groupby('vendor_name')['Curr.amount'].sum().sort_values(ascending=False)
    vendor_transactions = df.groupby('vendor_name').size()
    vendor_avg = vendor_sales / vendor_transactions
    
    hourly_sales = df.groupby('hour')['Curr.amount'].sum()
    
    daily_sales = df.groupby('date')['Curr.amount'].sum().sort_index()
    
    hourly_by_day = df.groupby(['date', 'hour'])['Curr.amount'].sum().unstack(fill_value=0)
    
    busiest_hour = hourly_sales.idxmax() if not hourly_sales.empty else 0
    busiest_hour_amount = hourly_sales.max() if not hourly_sales.empty else 0
    
    best_day = daily_sales.idxmax() if not daily_sales.empty else None
    best_day_amount = daily_sales.max() if not daily_sales.empty else 0
    
    after_6pm = df[df['hour'] >= 18]['Curr.amount'].sum()
    after_6pm_pct = (after_6pm / total_sales * 100) if total_sales > 0 else 0
    
    return {
        'total_sales': total_sales,
        'total_transactions': total_transactions,
        'avg_transaction': avg_transaction,
        'unique_days': unique_days,
        'vendor_sales': vendor_sales,
        'vendor_transactions': vendor_transactions,
        'vendor_avg': vendor_avg,
        'hourly_sales': hourly_sales,
        'daily_sales': daily_sales,
        'hourly_by_day': hourly_by_day,
        'busiest_hour': busiest_hour,
        'busiest_hour_amount': busiest_hour_amount,
        'best_day': best_day,
        'best_day_amount': best_day_amount,
        'after_6pm': after_6pm,
        'after_6pm_pct': after_6pm_pct
    }

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.success(f"File loaded successfully! Found {len(df)} rows.")
        
        df = load_and_process_data(df)
        
        if df.empty:
            st.stop()
        
        metrics = calculate_metrics(df)
        
        st.markdown("---")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "Total Sales", 
                f"£{metrics['total_sales']:,.2f}",
                help=f"From statuses: {', '.join(INCLUDED_STATUSES)}"
            )
        
        with col2:
            st.metric(
                "Total Transactions", 
                f"{metrics['total_transactions']:,}",
                help=f"From statuses: {', '.join(INCLUDED_STATUSES)}"
            )
        
        with col3:
            st.metric(
                "Avg Transaction", 
                f"£{metrics['avg_transaction']:.2f}",
                help="Average transaction value"
            )
        
        with col4:
            st.metric(
                "Days Analyzed", 
                f"{metrics['unique_days']}",
                help="Number of unique days in data"
            )
        
        with col5:
            st.metric(
                "After 6PM Sales", 
                f"£{metrics['after_6pm']:,.2f} ({metrics['after_6pm_pct']:.1f}%)",
                help="Sales after 6PM"
            )
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="sub-header">Daily Sales Trend</div>', unsafe_allow_html=True)
            if not metrics['daily_sales'].empty:
                fig_daily = px.line(
                    x=metrics['daily_sales'].index, 
                    y=metrics['daily_sales'].values,
                    title="Sales by Day",
                    labels={'x': 'Date', 'y': 'Sales (£)'},
                    markers=True
                )
                fig_daily.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                st.info("No daily sales data available")
        
        with col2:
            st.markdown('<div class="sub-header">Sales by Vendor</div>', unsafe_allow_html=True)
            if not metrics['vendor_sales'].empty:
                fig_vendor = px.pie(
                    values=metrics['vendor_sales'].values,
                    names=metrics['vendor_sales'].index,
                    title="Revenue Distribution by Vendor",
                    hole=0.3,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_vendor.update_layout(height=400)
                st.plotly_chart(fig_vendor, use_container_width=True)
            else:
                st.info("No vendor sales data available")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="sub-header">Hourly Sales Analysis</div>', unsafe_allow_html=True)
            if not metrics['hourly_sales'].empty:
                fig_hourly = px.bar(
                    x=metrics['hourly_sales'].index,
                    y=metrics['hourly_sales'].values,
                    title="Total Sales by Hour of Day",
                    labels={'x': 'Hour (24h)', 'y': 'Sales (£)'},
                    color=metrics['hourly_sales'].values,
                    color_continuous_scale='Viridis'
                )
                fig_hourly.update_layout(height=400)
                st.plotly_chart(fig_hourly, use_container_width=True)
                
                # Add peak hour insight
                st.info(f"**Peak Hour:** {metrics['busiest_hour']}:00 - {metrics['busiest_hour']+1}:00 with £{metrics['busiest_hour_amount']:,.2f}")
            else:
                st.info("No hourly sales data available")
        
        with col2:
            st.markdown('<div class="sub-header">Vendor Performance Details</div>', unsafe_allow_html=True)
            if not metrics['vendor_sales'].empty:
                vendor_df = pd.DataFrame({
                    'Vendor': metrics['vendor_sales'].index,
                    'Total Sales (£)': metrics['vendor_sales'].values,
                    'Transactions': metrics['vendor_transactions'].values,
                    'Avg Transaction (£)': metrics['vendor_avg'].values
                })
                vendor_df['% of Total'] = (vendor_df['Total Sales (£)'] / metrics['total_sales'] * 100).round(1)
                
                st.dataframe(
                    vendor_df.style.format({
                        'Total Sales (£)': '£{:,.2f}',
                        'Avg Transaction (£)': '£{:.2f}',
                        '% of Total': '{:.1f}%'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No vendor data available")
        
        st.markdown('<div class="sub-header">Hourly Sales Heatmap (By Day)</div>', unsafe_allow_html=True)
        if not metrics['hourly_by_day'].empty:
            fig_heatmap = px.imshow(
                metrics['hourly_by_day'].T,
                title="Sales Heatmap - Hour vs Day",
                labels={'x': 'Date', 'y': 'Hour', 'color': 'Sales (£)'},
                color_continuous_scale='RdYlGn',
                aspect='auto'
            )
            fig_heatmap.update_layout(height=500)
            st.plotly_chart(fig_heatmap, use_container_width=True)
        else:
            st.info("Not enough data for heatmap")
        
        st.markdown('<div class="sub-header">Detailed Reports</div>', unsafe_allow_html=True)
        
        tab1, tab2, tab3, tab4 = st.tabs(["Daily Breakdown", "Hourly by Day", "Vendor Daily", "Raw Data"])
        
        with tab1:
            if not metrics['daily_sales'].empty:
                daily_df = pd.DataFrame({
                    'Date': metrics['daily_sales'].index,
                    'Total Sales (£)': metrics['daily_sales'].values,
                    'Transactions': df.groupby('date').size().values,
                    'Avg Transaction (£)': (metrics['daily_sales'].values / df.groupby('date').size().values).round(2)
                })
                st.dataframe(
                    daily_df.style.format({
                        'Total Sales (£)': '£{:,.2f}',
                        'Avg Transaction (£)': '£{:.2f}'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        
        with tab2:
            if not metrics['hourly_by_day'].empty:
                hourly_display = metrics['hourly_by_day'].round(2)
                hourly_display.columns = [str(col) for col in hourly_display.columns]
                st.dataframe(hourly_display, use_container_width=True)
        
        with tab3:
            vendor_daily = df.groupby(['date', 'vendor_name'])['Curr.amount'].sum().unstack(fill_value=0).round(2)
            st.dataframe(vendor_daily, use_container_width=True)
        
        with tab4:
            st.dataframe(df[['datetime', 'vendor_name', 'Curr.amount', 'status', 'device_serial_number']], use_container_width=True)
        
        st.markdown('<div class="sub-header">Key Insights</div>', unsafe_allow_html=True)
        
        insight_col1, insight_col2, insight_col3 = st.columns(3)
        
        with insight_col1:
            st.info(f"**Best Day:** {metrics['best_day']} with £{metrics['best_day_amount']:,.2f}" if metrics['best_day'] else "No data")
        
        with insight_col2:
            st.info(f"**Busiest Hour:** {metrics['busiest_hour']}:00-{metrics['busiest_hour']+1}:00 with £{metrics['busiest_hour_amount']:,.2f}")
        
        with insight_col3:
            top_vendor = metrics['vendor_sales'].index[0] if not metrics['vendor_sales'].empty else "N/A"
            top_vendor_pct = (metrics['vendor_sales'].iloc[0] / metrics['total_sales'] * 100) if not metrics['vendor_sales'].empty else 0
            st.info(f"**Top Vendor:** {top_vendor} ({top_vendor_pct:.1f}% of total)")
        
        st.markdown("---")
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Processed Data (CSV)",
            data=csv_buffer.getvalue(),
            file_name="processed_sales_data.csv",
            mime="text/csv"
        )
        
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        st.info("Please make sure the CSV has the expected columns")

else:
    st.info("Please upload a Verifone CSV file to begin analysis")