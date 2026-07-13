import io

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="AQ Foodhall Sales Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
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
        .small-note {
            color: #5f6b7a;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="main-header">AQ Foodhall Sales Analytics Dashboard</div>',
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Upload your Verifone CSV file",
    type=["csv"],
    help="Upload the transaction CSV downloaded from the Verifone portal.",
)


VENDOR_MAP = {
    "809-990-578": "Kacao",
    "809-990-535": "Frost & Froth",
    "809-990-722": "Fat Belly",
    "809-990-587": "Boba & Chai",
    "809-990-622": "Kohitayn",
    "809-907-812": "Salsa",
    "809-907-685": "Tarbushi",
}

# Only these statuses are counted as completed sales revenue.
INCLUDED_SALE_STATUSES = [
    "PARTIAL SALE SETTLED",
    "SALE SETTLED",
    "SALE SETTLEMENT_REQUESTED",
]

# These statuses need operational attention or monitoring.
CRITICAL_STATUSES = [
    "SALE FAILED",
    "SALE DECLINED",
    "REFUND FAILED",
    "CANCEL DECLINED",
]

PENDING_STATUSES = [
    "SALE AUTHORISED",
    "SALE SETTLEMENT_REQUESTED",
]

REQUIRED_COLUMNS = [
    "created_at_date",
    "created_at_time",
    "status",
    "Curr.amount",
    "device_serial_number",
]

OPTIONAL_EXPORT_COLUMNS = [
    "datetime",
    "date",
    "hour",
    "vendor_name",
    "device_serial_number",
    "terminal_id",
    "Reference",
    "merchant_reference",
    "payment_method",
    "processor_card_brand",
    "Curr.amount",
    "payment_processing_fee_amount",
    "net_amount",
    "fee_percentage",
    "status",
    "settlement_date",
    "batch_id",
    "authorisation_code",
    "acquirer_response_code",
    "acquirer_response_message",
    "card.last_four",
]


def safe_numeric(series):
    """Convert a pandas Series to numeric values, replacing invalid values with zero."""
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def validate_columns(dataframe):
    """Return a list of required columns that are missing from the uploaded CSV."""
    return [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]


def load_and_process_data(dataframe):
    """Prepare the complete transaction dataset without hiding failed or pending rows."""
    df = dataframe.copy()

    missing_columns = validate_columns(df)
    if missing_columns:
        st.error(
            "The uploaded CSV is missing these required columns: "
            + ", ".join(missing_columns)
        )
        return pd.DataFrame()

    df["status"] = df["status"].fillna("UNKNOWN").astype(str).str.strip()
    df["status_upper"] = df["status"].str.upper()

    df["Curr.amount"] = safe_numeric(df["Curr.amount"])

    if "payment_processing_fee_amount" in df.columns:
        df["payment_processing_fee_amount"] = safe_numeric(
            df["payment_processing_fee_amount"]
        )
    else:
        df["payment_processing_fee_amount"] = 0.0
        st.warning(
            "The column 'payment_processing_fee_amount' was not found. "
            "Fee totals will show as £0.00."
        )

    df["created_at_date"] = pd.to_datetime(
        df["created_at_date"], errors="coerce"
    )
    df["datetime"] = pd.to_datetime(
        df["created_at_date"].dt.strftime("%Y-%m-%d").fillna("")
        + " "
        + df["created_at_time"].fillna("").astype(str),
        errors="coerce",
    )

    df["date"] = df["datetime"].dt.date
    df["hour"] = df["datetime"].dt.hour

    df["device_serial_number"] = (
        df["device_serial_number"].fillna("UNKNOWN").astype(str).str.strip()
    )
    df["vendor_name"] = df["device_serial_number"].map(VENDOR_MAP)
    df["vendor_name"] = df["vendor_name"].fillna(
        "Unknown terminal (" + df["device_serial_number"] + ")"
    )

    df["net_amount"] = df["Curr.amount"] - df["payment_processing_fee_amount"]
    df["fee_percentage"] = 0.0
    positive_amount_mask = df["Curr.amount"] > 0
    df.loc[positive_amount_mask, "fee_percentage"] = (
        df.loc[positive_amount_mask, "payment_processing_fee_amount"]
        / df.loc[positive_amount_mask, "Curr.amount"]
        * 100
    )

    df = df.dropna(subset=["datetime"])
    return df


def get_sales_data(all_transactions):
    """Return only completed/settlement-stage sale transactions."""
    included = {status.upper() for status in INCLUDED_SALE_STATUSES}
    return all_transactions[
        all_transactions["status_upper"].isin(included)
    ].copy()


def calculate_metrics(sales_df):
    """Calculate sales and fee KPIs using completed sale transactions only."""
    total_sales = sales_df["Curr.amount"].sum()
    total_fees = sales_df["payment_processing_fee_amount"].sum()
    net_sales = total_sales - total_fees
    total_transactions = len(sales_df)

    avg_transaction = (
        total_sales / total_transactions if total_transactions > 0 else 0.0
    )
    avg_fee = total_fees / total_transactions if total_transactions > 0 else 0.0
    effective_fee_rate = (
        total_fees / total_sales * 100 if total_sales > 0 else 0.0
    )
    unique_days = sales_df["date"].nunique()

    hourly_sales = sales_df.groupby("hour")["Curr.amount"].sum().sort_index()
    daily_sales = sales_df.groupby("date")["Curr.amount"].sum().sort_index()
    hourly_by_day = (
        sales_df.groupby(["date", "hour"])["Curr.amount"]
        .sum()
        .unstack(fill_value=0)
    )

    busiest_hour = hourly_sales.idxmax() if not hourly_sales.empty else 0
    busiest_hour_amount = hourly_sales.max() if not hourly_sales.empty else 0.0
    best_day = daily_sales.idxmax() if not daily_sales.empty else None
    best_day_amount = daily_sales.max() if not daily_sales.empty else 0.0

    after_6pm = sales_df[sales_df["hour"] >= 18]["Curr.amount"].sum()
    after_6pm_pct = after_6pm / total_sales * 100 if total_sales > 0 else 0.0

    return {
        "total_sales": total_sales,
        "total_fees": total_fees,
        "net_sales": net_sales,
        "total_transactions": total_transactions,
        "avg_transaction": avg_transaction,
        "avg_fee": avg_fee,
        "effective_fee_rate": effective_fee_rate,
        "unique_days": unique_days,
        "hourly_sales": hourly_sales,
        "daily_sales": daily_sales,
        "hourly_by_day": hourly_by_day,
        "busiest_hour": busiest_hour,
        "busiest_hour_amount": busiest_hour_amount,
        "best_day": best_day,
        "best_day_amount": best_day_amount,
        "after_6pm": after_6pm,
        "after_6pm_pct": after_6pm_pct,
    }


def build_vendor_summary(sales_df):
    """Build vendor-level gross sales, fees and net settlement figures."""
    if sales_df.empty:
        return pd.DataFrame()

    summary = (
        sales_df.groupby("vendor_name", dropna=False)
        .agg(
            Transactions=("Curr.amount", "size"),
            **{
                "Gross Sales (£)": ("Curr.amount", "sum"),
                "Processing Fees (£)": (
                    "payment_processing_fee_amount",
                    "sum",
                ),
            },
        )
        .reset_index()
        .rename(columns={"vendor_name": "Vendor"})
    )

    summary["Net Sales (£)"] = (
        summary["Gross Sales (£)"] - summary["Processing Fees (£)"]
    )
    summary["Average Transaction (£)"] = (
        summary["Gross Sales (£)"] / summary["Transactions"]
    )
    summary["Effective Fee Rate (%)"] = 0.0
    positive_mask = summary["Gross Sales (£)"] > 0
    summary.loc[positive_mask, "Effective Fee Rate (%)"] = (
        summary.loc[positive_mask, "Processing Fees (£)"]
        / summary.loc[positive_mask, "Gross Sales (£)"]
        * 100
    )

    total_sales = summary["Gross Sales (£)"].sum()
    summary["Share of Sales (%)"] = (
        summary["Gross Sales (£)"] / total_sales * 100 if total_sales > 0 else 0.0
    )

    return summary.sort_values("Gross Sales (£)", ascending=False).reset_index(drop=True)


def build_daily_summary(sales_df):
    """Build daily sales, fees, net revenue and transaction counts."""
    if sales_df.empty:
        return pd.DataFrame()

    daily = (
        sales_df.groupby("date")
        .agg(
            Transactions=("Curr.amount", "size"),
            **{
                "Gross Sales (£)": ("Curr.amount", "sum"),
                "Processing Fees (£)": (
                    "payment_processing_fee_amount",
                    "sum",
                ),
            },
        )
        .reset_index()
        .rename(columns={"date": "Date"})
    )

    daily["Net Sales (£)"] = daily["Gross Sales (£)"] - daily["Processing Fees (£)"]
    daily["Average Transaction (£)"] = daily["Gross Sales (£)"] / daily["Transactions"]
    daily["Effective Fee Rate (%)"] = 0.0
    positive_mask = daily["Gross Sales (£)"] > 0
    daily.loc[positive_mask, "Effective Fee Rate (%)"] = (
        daily.loc[positive_mask, "Processing Fees (£)"]
        / daily.loc[positive_mask, "Gross Sales (£)"]
        * 100
    )

    return daily.sort_values("Date").reset_index(drop=True)


def build_status_summary(all_transactions):
    """Summarise every status found in the uploaded CSV."""
    status_summary = (
        all_transactions.groupby("status", dropna=False)
        .agg(
            Transactions=("status", "size"),
            **{
                "Transaction Value (£)": ("Curr.amount", "sum"),
                "Recorded Fees (£)": (
                    "payment_processing_fee_amount",
                    "sum",
                ),
            },
        )
        .reset_index()
        .rename(columns={"status": "Status"})
    )

    critical_upper = {status.upper() for status in CRITICAL_STATUSES}
    pending_upper = {status.upper() for status in PENDING_STATUSES}
    settled_upper = {status.upper() for status in INCLUDED_SALE_STATUSES}

    def classify_status(status):
        upper_status = str(status).upper()
        if upper_status in critical_upper:
            return "Critical / investigate"
        if upper_status in pending_upper:
            return "Pending / monitor"
        if upper_status in settled_upper:
            return "Successful sale"
        if upper_status == "REFUND SETTLED":
            return "Completed refund"
        if upper_status == "CANCEL AUTHORISED":
            return "Cancelled"
        return "Review"

    status_summary["Operational Meaning"] = status_summary["Status"].apply(
        classify_status
    )
    return status_summary.sort_values("Transactions", ascending=False).reset_index(drop=True)


def build_vendor_daily_summary(sales_df):
    """Build one row per date and vendor for Excel-friendly analysis."""
    if sales_df.empty:
        return pd.DataFrame()

    vendor_daily = (
        sales_df.groupby(["date", "vendor_name"])
        .agg(
            Transactions=("Curr.amount", "size"),
            **{
                "Gross Sales (£)": ("Curr.amount", "sum"),
                "Processing Fees (£)": (
                    "payment_processing_fee_amount",
                    "sum",
                ),
            },
        )
        .reset_index()
        .rename(columns={"date": "Date", "vendor_name": "Vendor"})
    )
    vendor_daily["Net Sales (£)"] = (
        vendor_daily["Gross Sales (£)"]
        - vendor_daily["Processing Fees (£)"]
    )
    return vendor_daily.sort_values(["Date", "Vendor"]).reset_index(drop=True)


def format_display_table(dataframe):
    """Round values while keeping the table as a normal, copyable DataFrame."""
    display_df = dataframe.copy()
    for column in display_df.columns:
        if "(£)" in str(column) or "(%)" in str(column):
            display_df[column] = pd.to_numeric(
                display_df[column], errors="coerce"
            ).round(2)
    return display_df


def dataframe_to_csv_bytes(dataframe):
    """Create a UTF-8 CSV that opens cleanly in Microsoft Excel."""
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def dataframe_to_tsv_bytes(dataframe):
    """Create tab-separated data for easy copy/paste into Excel."""
    return dataframe.to_csv(index=False, sep="\t").encode("utf-8-sig")


def build_excel_workbook(sheets):
    """Create one Excel workbook containing all dashboard reports."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, dataframe in sheets.items():
            safe_sheet_name = sheet_name[:31]
            dataframe.to_excel(writer, sheet_name=safe_sheet_name, index=False)

            worksheet = writer.sheets[safe_sheet_name]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions

            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter
                for cell in column_cells:
                    cell_value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(cell_value))
                worksheet.column_dimensions[column_letter].width = min(
                    max(max_length + 2, 12), 40
                )

    output.seek(0)
    return output.getvalue()


def show_table_with_downloads(dataframe, table_name, file_prefix, key_prefix):
    """Show a copyable table plus CSV and TSV download options."""
    display_df = format_display_table(dataframe)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    button_col1, button_col2 = st.columns(2)
    with button_col1:
        st.download_button(
            label=f"Download {table_name} CSV",
            data=dataframe_to_csv_bytes(dataframe),
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            use_container_width=True,
        )
    with button_col2:
        st.download_button(
            label=f"Download {table_name} for Copy/Paste",
            data=dataframe_to_tsv_bytes(dataframe),
            file_name=f"{file_prefix}.tsv",
            mime="text/tab-separated-values",
            key=f"{key_prefix}_tsv",
            use_container_width=True,
            help="Open this file in Excel or copy its tab-separated rows directly into an existing worksheet.",
        )


if uploaded_file is not None:
    try:
        raw_df = pd.read_csv(uploaded_file, low_memory=False)
        all_transactions = load_and_process_data(raw_df)

        if all_transactions.empty:
            st.stop()

        sales_df = get_sales_data(all_transactions)
        if sales_df.empty:
            st.error(
                "No completed sales were found using these statuses: "
                + ", ".join(INCLUDED_SALE_STATUSES)
            )
            st.stop()

        metrics = calculate_metrics(sales_df)
        vendor_summary = build_vendor_summary(sales_df)
        daily_summary = build_daily_summary(sales_df)
        status_summary = build_status_summary(all_transactions)
        vendor_daily_summary = build_vendor_daily_summary(sales_df)

        critical_upper = {status.upper() for status in CRITICAL_STATUSES}
        pending_upper = {status.upper() for status in PENDING_STATUSES}

        critical_transactions = all_transactions[
            all_transactions["status_upper"].isin(critical_upper)
        ].copy()
        pending_transactions = all_transactions[
            all_transactions["status_upper"].isin(pending_upper)
        ].copy()

        export_columns = [
            column for column in OPTIONAL_EXPORT_COLUMNS if column in all_transactions.columns
        ]
        processed_export = all_transactions[export_columns].copy()
        completed_sales_export = sales_df[export_columns].copy()

        st.success(
            f"File loaded successfully: {len(all_transactions):,} total transactions, "
            f"including {len(sales_df):,} completed/settlement-stage sales."
        )

        st.markdown("---")
        st.markdown(
            '<div class="sub-header">Financial Summary</div>',
            unsafe_allow_html=True,
        )

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        with metric_col1:
            st.metric("Gross Sales", f"£{metrics['total_sales']:,.2f}")
        with metric_col2:
            st.metric(
                "Processing Fees Paid",
                f"£{metrics['total_fees']:,.2f}",
                help="Sum of payment_processing_fee_amount for included sale statuses.",
            )
        with metric_col3:
            st.metric("Net Sales After Fees", f"£{metrics['net_sales']:,.2f}")
        with metric_col4:
            st.metric(
                "Effective Fee Rate",
                f"{metrics['effective_fee_rate']:.2f}%",
                help="Total processing fees divided by gross completed sales.",
            )

        metric_col5, metric_col6, metric_col7, metric_col8 = st.columns(4)
        with metric_col5:
            st.metric("Completed Transactions", f"{metrics['total_transactions']:,}")
        with metric_col6:
            st.metric("Average Transaction", f"£{metrics['avg_transaction']:,.2f}")
        with metric_col7:
            st.metric("Average Fee per Sale", f"£{metrics['avg_fee']:,.2f}")
        with metric_col8:
            st.metric(
                "After 6PM Sales",
                f"£{metrics['after_6pm']:,.2f} ({metrics['after_6pm_pct']:.1f}%)",
            )

        st.caption(
            "Gross sales and fee KPIs use only completed or settlement-stage sale statuses: "
            + ", ".join(INCLUDED_SALE_STATUSES)
            + ". Failed, declined, cancelled and refund transactions are monitored separately."
        )

        st.markdown("---")
        st.markdown(
            '<div class="sub-header">Operational Status Monitor</div>',
            unsafe_allow_html=True,
        )

        failed_count = len(critical_transactions)
        pending_count = len(pending_transactions)
        refund_failed_count = int(
            (all_transactions["status_upper"] == "REFUND FAILED").sum()
        )
        declined_count = int(
            (all_transactions["status_upper"] == "SALE DECLINED").sum()
        )

        status_col1, status_col2, status_col3, status_col4 = st.columns(4)
        with status_col1:
            st.metric("Critical Transactions", f"{failed_count:,}")
        with status_col2:
            st.metric("Pending / Authorised", f"{pending_count:,}")
        with status_col3:
            st.metric("Sale Declines", f"{declined_count:,}")
        with status_col4:
            st.metric("Failed Refunds", f"{refund_failed_count:,}")

        with st.expander("Status guidance — what requires attention", expanded=True):
            st.markdown(
                """
                **Critical / investigate:** `SALE FAILED`, `REFUND FAILED`, and `CANCEL DECLINED`.  
                **Monitor:** `SALE AUTHORISED` and `SALE SETTLEMENT_REQUESTED` because they have not yet reached final settlement.  
                **Usually customer-bank related:** `SALE DECLINED`, although a sudden increase can indicate a terminal, connection or processor issue.  
                **Successful:** `SALE SETTLED` and other included settled-sale statuses.  
                **Completed reversal:** `REFUND SETTLED` or `CANCEL AUTHORISED`.
                """
            )

        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown(
                '<div class="sub-header">Daily Gross Sales and Fees</div>',
                unsafe_allow_html=True,
            )
            daily_chart = daily_summary.melt(
                id_vars=["Date"],
                value_vars=["Gross Sales (£)", "Processing Fees (£)"],
                var_name="Measure",
                value_name="Amount (£)",
            )
            fig_daily = px.line(
                daily_chart,
                x="Date",
                y="Amount (£)",
                color="Measure",
                markers=True,
                title="Daily Sales and Processing Fees",
            )
            fig_daily.update_layout(height=420)
            st.plotly_chart(fig_daily, use_container_width=True)

        with chart_col2:
            st.markdown(
                '<div class="sub-header">Sales by Vendor</div>',
                unsafe_allow_html=True,
            )
            fig_vendor = px.pie(
                vendor_summary,
                values="Gross Sales (£)",
                names="Vendor",
                title="Revenue Distribution by Vendor",
                hole=0.3,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_vendor.update_layout(height=420)
            st.plotly_chart(fig_vendor, use_container_width=True)

        chart_col3, chart_col4 = st.columns(2)
        with chart_col3:
            st.markdown(
                '<div class="sub-header">Hourly Sales Analysis</div>',
                unsafe_allow_html=True,
            )
            hourly_df = metrics["hourly_sales"].reset_index()
            hourly_df.columns = ["Hour", "Gross Sales (£)"]
            fig_hourly = px.bar(
                hourly_df,
                x="Hour",
                y="Gross Sales (£)",
                title="Total Sales by Hour of Day",
                labels={"Hour": "Hour (24h)"},
                color="Gross Sales (£)",
                color_continuous_scale="Viridis",
            )
            fig_hourly.update_layout(height=420)
            st.plotly_chart(fig_hourly, use_container_width=True)
            st.info(
                f"**Peak Hour:** {metrics['busiest_hour']}:00–"
                f"{metrics['busiest_hour'] + 1}:00 with "
                f"£{metrics['busiest_hour_amount']:,.2f} in sales."
            )

        with chart_col4:
            st.markdown(
                '<div class="sub-header">Fees by Vendor</div>',
                unsafe_allow_html=True,
            )
            fig_fees = px.bar(
                vendor_summary,
                x="Vendor",
                y="Processing Fees (£)",
                title="Processing Fees Paid by Vendor",
                text_auto=".2f",
            )
            fig_fees.update_layout(height=420)
            st.plotly_chart(fig_fees, use_container_width=True)

        st.markdown("---")
        st.markdown(
            '<div class="sub-header">Detailed Reports and Excel Exports</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "All tables below are plain DataFrames, so you can select cells and copy them. "
            "For reliable transfer into Excel, use the CSV, TSV or complete Excel workbook downloads."
        )

        tabs = st.tabs(
            [
                "Vendor Performance",
                "Daily Breakdown",
                "Vendor Daily",
                "Status Summary",
                "Critical Transactions",
                "Pending Transactions",
                "Raw Data",
            ]
        )

        with tabs[0]:
            show_table_with_downloads(
                vendor_summary,
                "Vendor Performance",
                "vendor_performance",
                "vendor_performance",
            )

        with tabs[1]:
            show_table_with_downloads(
                daily_summary,
                "Daily Breakdown",
                "daily_sales_fees",
                "daily_breakdown",
            )

        with tabs[2]:
            show_table_with_downloads(
                vendor_daily_summary,
                "Vendor Daily",
                "vendor_daily_sales_fees",
                "vendor_daily",
            )

        with tabs[3]:
            show_table_with_downloads(
                status_summary,
                "Status Summary",
                "transaction_status_summary",
                "status_summary",
            )

        with tabs[4]:
            if critical_transactions.empty:
                st.success("No critical transactions were found in this file.")
            else:
                critical_export_columns = [
                    column
                    for column in export_columns
                    if column in critical_transactions.columns
                ]
                show_table_with_downloads(
                    critical_transactions[critical_export_columns],
                    "Critical Transactions",
                    "critical_transactions",
                    "critical_transactions",
                )

        with tabs[5]:
            if pending_transactions.empty:
                st.success("No pending or authorised transactions were found.")
            else:
                pending_export_columns = [
                    column
                    for column in export_columns
                    if column in pending_transactions.columns
                ]
                show_table_with_downloads(
                    pending_transactions[pending_export_columns],
                    "Pending Transactions",
                    "pending_transactions",
                    "pending_transactions",
                )

        with tabs[6]:
            show_table_with_downloads(
                processed_export,
                "Processed Raw Data",
                "processed_transaction_data",
                "processed_raw_data",
            )

        st.markdown("---")
        st.markdown(
            '<div class="sub-header">Complete Excel Workbook</div>',
            unsafe_allow_html=True,
        )

        workbook_sheets = {
            "Financial Summary": pd.DataFrame(
                {
                    "Metric": [
                        "Gross Sales",
                        "Processing Fees Paid",
                        "Net Sales After Fees",
                        "Effective Fee Rate",
                        "Completed Transactions",
                        "Average Transaction",
                        "Average Fee per Sale",
                    ],
                    "Value": [
                        metrics["total_sales"],
                        metrics["total_fees"],
                        metrics["net_sales"],
                        metrics["effective_fee_rate"],
                        metrics["total_transactions"],
                        metrics["avg_transaction"],
                        metrics["avg_fee"],
                    ],
                }
            ),
            "Vendor Performance": vendor_summary,
            "Daily Breakdown": daily_summary,
            "Vendor Daily": vendor_daily_summary,
            "Status Summary": status_summary,
            "Critical Transactions": critical_transactions[
                [column for column in export_columns if column in critical_transactions.columns]
            ],
            "Pending Transactions": pending_transactions[
                [column for column in export_columns if column in pending_transactions.columns]
            ],
            "Completed Sales": completed_sales_export,
            "All Processed Data": processed_export,
        }

        try:
            excel_data = build_excel_workbook(workbook_sheets)
            st.download_button(
                label="Download Complete Excel Workbook",
                data=excel_data,
                file_name="aq_foodhall_sales_analysis.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ImportError:
            st.error(
                "Excel export requires openpyxl. Add 'openpyxl' to your requirements.txt file."
            )

        st.markdown(
            '<div class="sub-header">Key Insights</div>',
            unsafe_allow_html=True,
        )

        insight_col1, insight_col2, insight_col3 = st.columns(3)
        with insight_col1:
            if metrics["best_day"] is not None:
                st.info(
                    f"**Best Day:** {metrics['best_day']} with "
                    f"£{metrics['best_day_amount']:,.2f}."
                )
            else:
                st.info("No best-day data is available.")

        with insight_col2:
            st.info(
                f"**Busiest Hour:** {metrics['busiest_hour']}:00–"
                f"{metrics['busiest_hour'] + 1}:00 with "
                f"£{metrics['busiest_hour_amount']:,.2f}."
            )

        with insight_col3:
            if not vendor_summary.empty:
                top_vendor = vendor_summary.iloc[0]
                st.info(
                    f"**Top Vendor:** {top_vendor['Vendor']} "
                    f"({top_vendor['Share of Sales (%)']:.1f}% of sales)."
                )
            else:
                st.info("No vendor data is available.")

    except Exception as error:
        st.error(f"Error processing file: {error}")
        st.info(
            "Please confirm that the file is a valid Verifone CSV and contains the expected columns."
        )
else:
    st.info("Please upload a Verifone CSV file to begin analysis.")
