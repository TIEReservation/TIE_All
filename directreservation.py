# Module-level constant for Plan Status options (alphabetical order for consistency)
PLAN_STATUS_OPTIONS = ["All", "Cancelled", "Completed", "Confirmed", "Fully Paid", "No Show", "Pending"]
VALID_PLAN_STATUSES = PLAN_STATUS_OPTIONS[1:]  # Exclude "All" for validation

def load_reservations_from_supabase():
    """Load reservations from Supabase, handling potential None values."""
    try:
        response = supabase.table("reservations").select("*").execute()
        reservations = []
        for record in response.data:
            # Default to "Pending" for null/empty plan_status to indicate incomplete reservation
            plan_status = record["plan_status"] or "Pending"
            if plan_status not in VALID_PLAN_STATUSES and st.session_state.role == "Management":
                st.warning(f"Unexpected plan_status '{plan_status}' for booking ID {record['booking_id']}")
            reservation = {
                "Booking ID": record["booking_id"],
                "Property Name": record["property_name"] or "",
                "Room No": record["room_no"] or "",
                "Guest Name": record["guest_name"] or "",
                "Mobile No": record["mobile_no"] or "",
                "No of Adults": safe_int(record["no_of_adults"]),
                "No of Children": safe_int(record["no_of_children"]),
                "No of Infants": safe_int(record["no_of_infants"]),
                "Total Pax": safe_int(record["total_pax"]),
                "Check In": datetime.strptime(record["check_in"], "%Y-%m-%d").date() if record["check_in"] else None,
                "Check Out": datetime.strptime(record["check_out"], "%Y-%m-%d").date() if record["check_out"] else None,
                "No of Days": safe_int(record["no_of_days"]),
                "Tariff": safe_float(record["tariff"]),
                "Total Tariff": safe_float(record["total_tariff"]),
                "Advance Amount": safe_float(record["advance_amount"]),
                "Balance Amount": safe_float(record["balance_amount"]),
                "Advance MOP": record["advance_mop"] or "",
                "Balance MOP": record["balance_mop"] or "",
                "MOB": record["mob"] or "",
                "Online Source": record["online_source"] or "",
                "Invoice No": record["invoice_no"] or "",
                "Enquiry Date": datetime.strptime(record["enquiry_date"], "%Y-%m-%d").date() if record["enquiry_date"] else None,
                "Booking Date": datetime.strptime(record["booking_date"], "%Y-%m-%d").date() if record["booking_date"] else None,
                "Room Type": record["room_type"] or "",
                "Breakfast": record["breakfast"] or "",
                "Plan Status": plan_status,
                "Submitted By": record.get("submitted_by", ""),
                "Modified By": record.get("modified_by", ""),
                "Modified Comments": record.get("modified_comments", "")
            }
            reservations.append(reservation)
        return reservations
    except Exception as e:
        st.error(f"Error loading reservations: {e}")
        return []

def show_reservations():
    """Display all reservations with filtering options."""
    if not st.session_state.reservations:
        st.info("No reservations available.")
        return

    st.header("📋 View Reservations")
    df = pd.DataFrame(st.session_state.reservations)
    
    st.subheader("Filters")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        start_date = st.date_input("Start Date", value=None, key="view_filter_start_date", help="Filter by Check In date range (optional)")
    with col2:
        end_date = st.date_input("End Date", value=None, key="view_filter_end_date", help="Filter by Check In date range (optional)")
    with col3:
        # Plan Status options in alphabetical order for consistency
        filter_status = st.selectbox("Filter by Status", PLAN_STATUS_OPTIONS, key="view_filter_status")
    with col4:
        filter_check_in_date = st.date_input("Check-in Date", value=None, key="view_filter_check_in_date")
    with col5:
        filter_check_out_date = st.date_input("Check-out Date", value=None, key="view_filter_check_out_date")
    with col6:
        filter_property = st.selectbox("Filter by Property", ["All"] + sorted(df["Property Name"].unique()), key="view_filter_property")

    filtered_df = display_filtered_analysis(df, start_date, end_date, view_mode=True)
    
    if filter_status != "All":
        filtered_df = filtered_df[filtered_df["Plan Status"] == filter_status]
    if filter_check_in_date:
        filtered_df = filtered_df[filtered_df["Check In"] == filter_check_in_date]
    if filter_check_out_date:
        filtered_df = filtered_df[filtered_df["Check Out"] == filter_check_out_date]
    if filter_property != "All":
        filtered_df = filtered_df[filtered_df["Property Name"] == filter_property]

    if filtered_df.empty:
        st.warning("No reservations match the selected filters.")
        return

    st.dataframe(
        filtered_df[["Booking ID", "Guest Name", "Mobile No", "Enquiry Date", "Room No", "MOB", "Check In", "Check Out", "Plan Status"]],
        use_container_width=True
    )

def show_edit_reservations():
    """Display reservations for editing with filtering options."""
    try:
        st.header("✏️ Edit Reservations")
        if not st.session_state.reservations:
            st.info("No reservations available to edit.")
            return

        df = pd.DataFrame(st.session_state.reservations)
        
        st.subheader("Filters")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            # Plan Status options in alphabetical order for consistency
            filter_status = st.selectbox("Filter by Status", PLAN_STATUS_OPTIONS, key="edit_filter_status")
        with col2:
            filter_check_in_date = st.date_input("Check-in Date", value=None, key="edit_filter_check_in_date")
        with col3:
            filter_check_out_date = st.date_input("Check-out Date", value=None, key="edit_filter_check_out_date")
        with col4:
            filter_enquiry_date = st.date_input("Enquiry Date", value=None, key="edit_filter_enquiry_date")
        with col5:
            filter_booking_date = st.date_input("Booking Date", value=None, key="edit_filter_booking_date")
        with col6:
            filter_property = st.selectbox("Filter by Property", ["All"] + sorted(df["Property Name"].unique()), key="edit_filter_property")

        filtered_df = df.copy()
        if filter_status != "All":
            filtered_df = filtered_df[filtered_df["Plan Status"] == filter_status]
        if filter_check_in_date:
            filtered_df = filtered_df[filtered_df["Check In"] == filter_check_in_date]
        if filter_check_out_date:
            filtered_df = filtered_df[filtered_df["Check Out"] == filter_check_out_date]
        if filter_enquiry_date:
            filtered_df = filtered_df[filtered_df["Enquiry Date"] == filter_enquiry_date]
        if filter_booking_date:
            filtered_df = filtered_df[filtered_df["Booking Date"] == filter_booking_date]
        if filter_property != "All":
            filtered_df = filtered_df[filtered_df["Property Name"] == filter_property]

        if filtered_df.empty:
            st.warning("No reservations match the selected filters.")
            return

        st.dataframe(
            filtered_df[["Booking ID", "Guest Name", "Mobile No", "Enquiry Date", "Room No", "MOB", "Check In", "Check Out", "Plan Status"]],
            use_container_width=True
        )

        booking_ids = filtered_df["Booking ID"].tolist()
        selected_booking_id = st.selectbox("Select Booking ID to Edit", ["None"] + booking_ids, key="edit_booking_id")

        if selected_booking_id != "None":
            edit_index = next(i for i, res in enumerate(st.session_state.reservations) if res["Booking ID"] == selected_booking_id)
            st.session_state.edit_mode = True
            st.session_state.edit_index = edit_index
            show_edit_form(edit_index)
    except Exception as e:
        st.error(f"Error rendering edit reservations: {e}")

def show_analytics():
    """Display analytics dashboard for Management users with month-wise and week-wise breakdowns."""
    if st.session_state.role != "Management":
        st.error("❌ Access Denied: Analytics is available only for Management users.")
        return

    st.header("📊 Analytics Dashboard")
    if not st.session_state.reservations:
        st.info("No reservations available for analysis.")
        return

    df = pd.DataFrame(st.session_state.reservations)
    
    st.subheader("Filters")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        start_date = st.date_input("Start Date", value=date(2025, 8, 1), key="analytics_filter_start_date", help="Filter by Check In date range (optional)")
    with col2:
        end_date = st.date_input("End Date", value=date(2025, 8, 31), key="analytics_filter_end_date", help="Filter by Check In date range (optional)")
    with col3:
        # Plan Status options in alphabetical order for consistency
        filter_status = st.selectbox("Filter by Status", PLAN_STATUS_OPTIONS, key="analytics_filter_status")
    with col4:
        filter_check_in_date = st.date_input("Check-in Date", value=None, key="analytics_filter_check_in_date")
    with col5:
        filter_check_out_date = st.date_input("Check-out Date", value=None, key="analytics_filter_check_out_date")
    with col6:
        filter_property = st.selectbox("Filter by Property", ["All"] + sorted(df["Property Name"].unique()), key="analytics_filter_property")

    filtered_df = display_filtered_analysis(df, start_date, end_date, view_mode=False)
    
    if filter_status != "All":
        filtered_df = filtered_df[filtered_df["Plan Status"] == filter_status]
    if filter_check_in_date:
        filtered_df = filtered_df[filtered_df["Check In"] == filter_check_in_date]
    if filter_check_out_date:
        filtered_df = filtered_df[filtered_df["Check Out"] == filter_check_out_date]
    if filter_property != "All":
        filtered_df = filtered_df[filtered_df["Property Name"] == filter_property]

    if filtered_df.empty:
        st.warning("No reservations match the selected filters.")
        return

    # Visualizations with unique keys
    st.subheader("Visualizations")
    col1, col2 = st.columns(2)
    with col1:
        property_counts = filtered_df["Property Name"].value_counts().reset_index()
        property_counts.columns = ["Property Name", "Reservation Count"]
        fig_pie = px.pie(
            property_counts,
            values="Reservation Count",
            names="Property Name",
            title="Reservation Distribution by Property",
            height=400,
            color_discrete_sequence=px.colors.qualitative.Plotly
        )
        st.plotly_chart(fig_pie, use_container_width=True, key="analytics_pie_chart_property_distribution")
    with col2:
        revenue_by_property = filtered_df.groupby("Property Name")["Total Tariff"].sum().reset_index()
        fig_bar = px.bar(
            revenue_by_property,
            x="Property Name",
            y="Total Tariff",
            title="Total Revenue by Property",
            height=400,
            labels={"Total Tariff": "Revenue (₹)"},
            color_discrete_sequence=["#636EFA"]
        )
        st.plotly_chart(fig_bar, use_container_width=True, key="analytics_bar_chart_revenue")

    # Month-wise Summary
    st.subheader("Monthly Summary")
    monthly_summary = filtered_df.groupby("Month").agg({
        "Property Name": "count",
        "Total Tariff": "sum"
    }).rename(columns={"Property Name": "Reservation Count", "Total Tariff": "Total Revenue"})
    st.dataframe(monthly_summary, use_container_width=True)

    # Week-wise Summary
    st.subheader("Weekly Summary")
    weekly_summary = filtered_df.groupby("Year-Week").agg({
        "Property Name": "count",
        "Total Tariff": "sum"
    }).rename(columns={"Property Name": "Reservation Count", "Total Tariff": "Total Revenue"})
    st.dataframe(weekly_summary, use_container_width=True)
