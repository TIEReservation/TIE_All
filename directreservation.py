import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# Global CSS for form styling
st.markdown("""
    <style>
    .stForm { margin: 0; padding: 0; }
    .stForm > div > div { margin-bottom: 0.5rem; width: 100%; }
    .stForm hr { display: none; }
    .stTextInput > div > input, .stSelectbox > div > select, .stNumberInput > div > input { max-width: 100%; }
    </style>
""", unsafe_allow_html=True)

# Initialize Supabase client
try:
    supabase: Client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
except KeyError as e:
    st.error(f"Missing Supabase secret: {e}. Please check Streamlit Cloud secrets configuration.")
    st.stop()

def load_property_room_map():
    """
    Loads the property to room type to room numbers mapping based on provided data.
    Returns a nested dictionary: {"Property": {"Room Type": ["Room No", ...], ...}, ...}
    """
    return {
        "Le Poshe Beachview": {
            "Double Room": ["101", "102", "202", "203", "204"],
            "Standard Room": ["201"],
            "Deluex Double Room Seaview": ["301", "302", "303", "304"]
        },
        "La Millionare Resort": {
            "Double Room": ["101", "102", "103", "105"],
            "Deluex Double Room with Balcony": ["205", "304", "305"],
            "Deluex Triple Room with Balcony": ["201", "202", "203", "204", "301", "302", "303"],
            "Deluex Family Room with Balcony": ["206", "207", "208", "306", "307", "308"],
            "Deluex Triple Room": ["402"],
            "Deluex Family Room": ["401"]
        },
        "Le Poshe Luxury": {
            "2BHA Appartment": ["101&102", "101", "102"],
            "2BHA Appartment with Balcony": ["201&202", "201", "202", "301&302", "301", "302", "401&402", "401", "402"],
            "3BHA Appartment": ["203to205", "203", "204", "205", "303to305", "303", "304", "305", "403to405", "403", "404", "405"],
            "Double Room with Private Terrace": ["501"]
        },
        "Le Poshe Suite": {
            "2BHA Appartment": ["601&602", "601", "602", "603", "604", "703", "704"],
            "2BHA Appartment with Balcony": ["701&702", "701", "702"],
            "Double Room with Terrace": ["801"]
        },
        "La Paradise Residency": {
            "Double Room": ["101", "102", "103", "301", "304"],
            "Family Room": ["201", "203"],
            "Triple Room": ["202", "303"]
        },
        "La Paradise Luxury": {
            "3BHA Appartment": ["101to103", "101", "102", "103", "201to203", "201", "202", "203"]
        },
        "La Villa Heritage": {
            "Double Room": ["101", "102", "103"],
            "4BHA Appartment": ["201to203&301", "201", "202", "203", "301"]
        },
        "Le Pondy Beach Side": {
            "Villa": ["101to104", "101", "102", "103", "104"]
        },
        "Le Royce Villa": {
            "Villa": ["101to102&201to202", "101", "102", "202", "202"]
        },
        "La Tamara Luxury": {
            "3BHA": ["101to103", "101", "102", "103", "104to106", "104", "105", "106", "201to203", "201", "202", "203", "204to206", "204", "205", "206", "301to303", "301", "302", "303", "304to306", "304", "305", "306"],
            "4BHA": ["401to404", "401", "402", "403", "404"]
        },
        "La Antilia": {
            "Deluex Suite Room": ["101"],
            "Deluex Double Room": ["203", "204", "303", "304"],
            "Family Room": ["201", "202", "301", "302"],
            "Deluex suite Room with Tarrace": ["404"]
        },
        "La Tamara Suite": {
            "Two Bedroom apartment": ["101&102"],
            "Deluxe Apartment": ["103&104"],
            "Deluxe Double Room": ["203", "204", "205"],
            "Deluxe Triple Room": ["201", "202"],
            "Deluxe Family Room": ["206"]
        },
        "Le Park Resort": {
            "Villa with Swimming Pool View": ["555&666", "555", "666"],
            "Villa with Garden View": ["111&222", "111", "222"],
            "Family Retreate Villa": ["333&444", "333", "444"]
        },
        "Villa Shakti": {
            "2BHA Studio Room": ["101&102"],
            "2BHA with Balcony": ["202&203", "302&303"],
            "Family Suite": ["201"],
            "Family Room": ["301"],
            "Terrace Room": ["401"]
        },
        "Eden Beach Resort": {
            "Double Room": ["101", "102"],
            "Deluex Room": ["103", "202"],
            "Triple Room": ["201"]
        }
    }

def generate_booking_id():
    """Generate a unique booking ID by checking existing IDs in Supabase."""
    try:
        today = datetime.now().strftime('%Y%m%d')
        response = supabase.table("reservations").select("booking_id").like("booking_id", f"TIE{today}%").execute()
        existing_ids = [record["booking_id"] for record in response.data]
        sequence = 1
        while f"TIE{today}{sequence:03d}" in existing_ids:
            sequence += 1
        return f"TIE{today}{sequence:03d}"
    except Exception as e:
        st.error(f"Error generating booking ID: {e}")
        return None

def check_duplicate_guest(guest_name, mobile_no, room_no, exclude_booking_id=None, mob=None):
    """Check for duplicate guest based on name, mobile number, and room number."""
    try:
        response = supabase.table("reservations").select("*").execute()
        for reservation in response.data:
            if exclude_booking_id and reservation["booking_id"] == exclude_booking_id:
                continue
            if (reservation["guest_name"].lower() == guest_name.lower() and
                    reservation["mobile_no"] == mobile_no and
                    reservation["room_no"] == room_no):
                if mob == "Stay-back" and reservation["mob"] != "Stay-back":
                    continue
                return True, reservation["booking_id"]
        return False, None
    except Exception as e:
        st.error(f"Error checking duplicate guest: {e}")
        return False, None

def calculate_days(check_in, check_out):
    """Calculate the number of days between check-in and check-out dates."""
    if check_in and check_out and check_out >= check_in:
        delta = check_out - check_in
        return max(1, delta.days)
    return 0

def safe_int(value, default=0):
    """Safely convert value to int, return default if conversion fails."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """Safely convert value to float, return default if conversion fails."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def load_reservations_from_supabase():
    """Load reservations from Supabase, handling potential None values."""
    try:
        response = supabase.table("reservations").select("*").execute()
        reservations = []
        for record in response.data:
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
                "Plan Status": record["plan_status"] or "",
                "Submitted By": record.get("submitted_by", ""),
                "Modified By": record.get("modified_by", ""),
                "Modified Comments": record.get("modified_comments", ""),
                "Remarks": record.get("remarks", ""),
                "Payment Status": record.get("payment_status", "Not Paid")
            }
            reservations.append(reservation)
        return reservations
    except Exception as e:
        st.error(f"Error loading reservations: {e}")
        return []

def save_reservation_to_supabase(reservation):
    """Save a new reservation to Supabase."""
    try:
        supabase_reservation = {
            "booking_id": reservation["Booking ID"],
            "property_name": reservation["Property Name"],
            "room_no": reservation["Room No"],
            "guest_name": reservation["Guest Name"],
            "mobile_no": reservation["Mobile No"],
            "no_of_adults": reservation["No of Adults"],
            "no_of_children": reservation["No of Children"],
            "no_of_infants": reservation["No of Infants"],
            "total_pax": reservation["Total Pax"],
            "check_in": reservation["Check In"].strftime("%Y-%m-%d") if reservation["Check In"] else None,
            "check_out": reservation["Check Out"].strftime("%Y-%m-%d") if reservation["Check Out"] else None,
            "no_of_days": reservation["No of Days"],
            "tariff": reservation["Tariff"],
            "total_tariff": reservation["Total Tariff"],
            "advance_amount": reservation["Advance Amount"],
            "balance_amount": reservation["Balance Amount"],
            "advance_mop": reservation["Advance MOP"],
            "balance_mop": reservation["Balance MOP"],
            "mob": reservation["MOB"],
            "online_source": reservation["Online Source"],
            "invoice_no": reservation["Invoice No"],
            "enquiry_date": reservation["Enquiry Date"].strftime("%Y-%m-%d") if reservation["Enquiry Date"] else None,
            "booking_date": reservation["Booking Date"].strftime("%Y-%m-%d") if reservation["Booking Date"] else None,
            "room_type": reservation["Room Type"],
            "breakfast": reservation["Breakfast"],
            "plan_status": reservation["Plan Status"],
            "submitted_by": reservation["Submitted By"],
            "modified_by": reservation["Modified By"],
            "modified_comments": reservation["Modified Comments"],
            "remarks": reservation["Remarks"],
            "payment_status": reservation["Payment Status"]
        }
        response = supabase.table("reservations").insert(supabase_reservation).execute()
        if response.data:
            st.session_state.reservations = load_reservations_from_supabase()
            return True
        return False
    except Exception as e:
        st.error(f"Error saving reservation: {e}")
        return False

def update_reservation_in_supabase(booking_id, updated_reservation):
    """Update an existing reservation in Supabase."""
    try:
        supabase_reservation = {
            "booking_id": updated_reservation["Booking ID"],
            "property_name": updated_reservation["Property Name"],
            "room_no": updated_reservation["Room No"],
            "guest_name": updated_reservation["Guest Name"],
            "mobile_no": updated_reservation["Mobile No"],
            "no_of_adults": updated_reservation["No of Adults"],
            "no_of_children": updated_reservation["No of Children"],
            "no_of_infants": updated_reservation["No of Infants"],
            "total_pax": updated_reservation["Total Pax"],
            "check_in": updated_reservation["Check In"].strftime("%Y-%m-%d") if updated_reservation["Check In"] else None,
            "check_out": updated_reservation["Check Out"].strftime("%Y-%m-%d") if updated_reservation["Check Out"] else None,
            "no_of_days": updated_reservation["No of Days"],
            "tariff": updated_reservation["Tariff"],
            "total_tariff": updated_reservation["Total Tariff"],
            "advance_amount": updated_reservation["Advance Amount"],
            "balance_amount": updated_reservation["Balance Amount"],
            "advance_mop": updated_reservation["Advance MOP"],
            "balance_mop": updated_reservation["Balance MOP"],
            "mob": updated_reservation["MOB"],
            "online_source": updated_reservation["Online Source"],
            "invoice_no": updated_reservation["Invoice No"],
            "enquiry_date": updated_reservation["Enquiry Date"].strftime("%Y-%m-%d") if updated_reservation["Enquiry Date"] else None,
            "booking_date": updated_reservation["Booking Date"].strftime("%Y-%m-%d") if updated_reservation["Booking Date"] else None,
            "room_type": updated_reservation["Room Type"],
            "breakfast": updated_reservation["Breakfast"],
            "plan_status": updated_reservation["Plan Status"],
            "submitted_by": updated_reservation["Submitted By"],
            "modified_by": updated_reservation["Modified By"],
            "modified_comments": updated_reservation["Modified Comments"],
            "remarks": updated_reservation["Remarks"],
            "payment_status": updated_reservation["Payment Status"]
        }
        response = supabase.table("reservations").update(supabase_reservation).eq("booking_id", booking_id).execute()
        if response.data:
            return True
        return False
    except Exception as e:
        st.error(f"Error updating reservation: {e}")
        return False

def delete_reservation_in_supabase(booking_id):
    """Delete a reservation from Supabase."""
    try:
        response = supabase.table("reservations").delete().eq("booking_id", booking_id).execute()
        if response.data:
            return True
        return False
    except Exception as e:
        st.error(f"Error deleting reservation: {e}")
        return False

@st.dialog("Reservation Confirmation")
def show_confirmation_dialog(booking_id, is_update=False):
    """Show confirmation dialog for new or updated reservations."""
    message = "Reservation Updated!" if is_update else "Reservation Confirmed!"
    st.markdown(f"**{message}**\n\nBooking ID: {booking_id}")
    if st.button("✔️ Confirm", use_container_width=True):
        st.rerun()

def display_filtered_analysis(df, start_date=None, end_date=None, view_mode=False):
    """
    Filter reservations by date range and display results.
    Args:
        df (pd.DataFrame): Reservations DataFrame.
        start_date (date, optional): Start of the date range.
        end_date (date, optional): End of the date range.
        view_mode (bool): If True, return filtered DataFrame for table display; else, display metrics and property-wise details.
    Returns:
        pd.DataFrame: Filtered DataFrame.
    """
    filtered_df = df.copy()
    filtered_df = filtered_df[filtered_df["Check In"].notnull()]
    
    if start_date and end_date:
        if end_date < start_date:
            st.error("❌ End date must be on or after start date")
            return filtered_df
        filtered_df = filtered_df[(filtered_df["Check In"] >= start_date) & (filtered_df["Check In"] <= end_date)]
    
    if filtered_df.empty:
        st.warning("No reservations found for the selected filters.")
        return filtered_df
    
    if not view_mode:
        st.subheader("Overall Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Reservations", len(filtered_df))
        with col2:
            total_revenue = filtered_df["Total Tariff"].sum()
            st.metric("Total Revenue", f"₹{total_revenue:,.2f}")
        with col3:
            st.metric("Average Tariff", f"₹{filtered_df['Tariff'].mean():,.2f}" if not filtered_df.empty else "₹0.00")
        with col4:
            st.metric("Average Stay", f"{filtered_df['No of Days'].mean():.1f} days" if not filtered_df.empty else "0.0 days")
        col5, col6 = st.columns(2)
        with col5:
            total_collected = filtered_df["Advance Amount"].sum() + filtered_df[filtered_df["Plan Status"] == "Completed"]["Balance Amount"].sum()
            st.metric("Total Revenue Collected", f"₹{total_collected:,.2f}")
        with col6:
            balance_pending = filtered_df[filtered_df["Plan Status"] != "Completed"]["Balance Amount"].sum()
            st.metric("Balance Pending", f"₹{balance_pending:,.2f}")

        st.subheader("Property-wise Reservation Details")
        properties = sorted(filtered_df["Property Name"].unique())
        for property in properties:
            with st.expander(f"{property} Reservations"):
                property_df = filtered_df[filtered_df["Property Name"] == property]
                st.write(f"**Total Reservations**: {len(property_df)}")
                total_revenue = property_df["Total Tariff"].sum()
                st.write(f"**Total Revenue**: ₹{total_revenue:,.2f}")
                total_collected = property_df["Advance Amount"].sum() + property_df[property_df["Plan Status"] == "Completed"]["Balance Amount"].sum()
                st.write(f"**Total Revenue Collected**: ₹{total_collected:,.2f}")
                balance_pending = property_df[property_df["Plan Status"] != "Completed"]["Balance Amount"].sum()
                st.write(f"**Balance Pending**: ₹{balance_pending:,.2f}")
                st.write(f"**Average Tariff**: ₹{property_df['Tariff'].mean():,.2f}" if not property_df.empty else "₹0.00")
                st.write(f"**Average Stay**: {property_df['No of Days'].mean():.1f} days" if not property_df.empty else "0.0 days")
                st.dataframe(
                    property_df[["Booking ID", "Guest Name", "Room No", "Check In", "Check Out", "Total Tariff", "Plan Status", "MOB", "Payment Status", "Remarks"]],
                    use_container_width=True
                )
    
    return filtered_df

def render_form_row(row_config, form_key, reservation=None):
    """Render a form row with dynamic inputs based on configuration."""
    fields = row_config["fields"]
    values = {}
    num_fields = len(fields)
    cols = st.columns(max(1, num_fields))
    for i, field in enumerate(fields):
        with cols[i]:
            if "key" not in field:
                st.error(f"Configuration error: Missing 'key' for field {field.get('name', 'unknown')}")
                continue
            key = f"{form_key}_{field['key']}"
            default = reservation.get(field["name"], field.get("default")) if reservation else field.get("default")
            
            if field["type"] == "text":
                values[field["name"]] = st.text_input(field["label"], value=default or "", placeholder=field.get("placeholder", ""), key=key)
            elif field["type"] == "number":
                values[field["name"]] = st.number_input(field["label"], min_value=field.get("min_value", 0), value=safe_float(default) if field["name"] in ["Tariff", "Advance Amount"] else safe_int(default) if default is not None else field.get("default", 0), step=field.get("step", 1), key=key)
            elif field["type"] == "date":
                values[field["name"]] = st.date_input(field["label"], value=default or date.today(), key=key)
            elif field["type"] == "selectbox":
                options = field["options"]
                index = options.index(default) if default in options else 0
                values[field["name"]] = st.selectbox(field["label"], options, index=index, key=key)
                if field["name"] == "MOB" and values[field["name"]] == "Others":
                    values["Custom MOB"] = st.text_input("Custom MOB", value=reservation.get("MOB", "") if reservation and default not in options else "", key=f"{key}_custom")
                elif field["name"] == "MOB" and values[field["name"]] == "Online":
                    online_options = ["Booking.com", "Agoda Prepaid", "Agoda Booking.com", "Expedia", "MMT", "Cleartrip", "Others"]
                    online_default = reservation.get("Online Source", "") if reservation else ""
                    online_index = online_options.index(online_default) if online_default in online_options else len(online_options) - 1
                    values["Online Source"] = st.selectbox("Online Source", online_options, index=online_index, key=f"{key}_online")
                    if values["Online Source"] == "Others":
                        values["Custom Online Source"] = st.text_input("Custom Online Source", value=reservation.get("Online Source", "") if reservation and online_default not in options else "", key=f"{key}_custom_online")
                    else:
                        values["Custom Online Source"] = None
                elif field["name"] in ["Advance MOP", "Balance MOP"] and values[field["name"]] == "Other":
                    custom_key = f"Custom {field['name']}"
                    values[custom_key] = st.text_input(f"Custom {field['label']}", value=reservation.get(field["name"], "") if reservation and default not in options else "", key=f"{key}_custom")
                else:
                    values[f"Custom {field['name']}"] = None
            elif field["type"] == "text_area":
                values[field["name"]] = st.text_area(field["label"], value=default or "", key=key)
            elif field["type"] == "disabled_text":
                value = f"₹{default:.2f}" if field["name"] in ["Total Tariff", "Balance Amount"] and default is not None else str(default) if default is not None else ""
                values[field["name"]] = st.text_input(field["label"], value=value, disabled=True, key=key)
            elif field["type"] == "dynamic_selectbox":
                if field["name"] == "Property Name":
                    options = sorted(load_property_room_map().keys())
                    if reservation and reservation.get("Property Name") == "Property 16":
                        options = sorted(options + ["Property 16"])
                    index = options.index(default) if default in options else 0
                    values[field["name"]] = st.selectbox(field["label"], options, index=index, key=key)
                elif field["name"] == "Room Type":
                    room_map = load_property_room_map()
                    available_room_types = sorted(room_map.get(values.get("Property Name", ""), {}).keys())
                    is_custom_type = default not in available_room_types or not default
                    room_type_options = available_room_types + ["Other"] if "Other" not in available_room_types else available_room_types
                    room_type_index = room_type_options.index("Other" if is_custom_type else default)
                    values[field["name"]] = st.selectbox(field["label"], room_type_options, index=room_type_index, key=key)
                    if values[field["name"]] == "Other":
                        values["Custom Room Type"] = st.text_input("Custom Room Type", value=default if is_custom_type else "", key=f"{key}_custom")
                    else:
                        values["Custom Room Type"] = None
                elif field["name"] == "Room No":
                    room_map = load_property_room_map()
                    room_type = values.get("Room Type", "")
                    available_rooms = sorted(room_map.get(values.get("Property Name", ""), {}).get(room_type, [])) if room_type != "Other" else []
                    existing_room_no = default or ""
                    if existing_room_no and existing_room_no not in available_rooms:
                        available_rooms = sorted(set(available_rooms + [existing_room_no]))
                    if available_rooms:
                        room_no_index = available_rooms.index(existing_room_no) if existing_room_no in available_rooms else 0
                        values[field["name"]] = st.selectbox(field["label"], available_rooms, index=room_no_index, key=key)
                    else:
                        st.warning("No rooms available for this room type. Enter manually.")
                        values[field["name"]] = st.text_input(field["label"], value=existing_room_no, placeholder="Enter room number", key=key)
    return values

def show_new_reservation_form():
    """Display form for creating a new reservation with specified row layout."""
    try:
        st.header("📝 Direct Reservations")
        form_key = "new_reservation"
        row_configs = [
            {
                "fields": [
                    {"name": "Property Name", "type": "dynamic_selectbox", "label": "Property Name", "key": "property"},
                    {"name": "Guest Name", "type": "text", "label": "Guest Name", "placeholder": "Enter guest name", "key": "guest"},
                    {"name": "Mobile No", "type": "text", "label": "Mobile No", "placeholder": "Enter mobile number", "key": "mobile"},
                    {"name": "MOB", "type": "selectbox", "label": "MOB (Mode of Booking)", "options": ["Direct", "Online", "Agent", "Walk-in", "Phone", "Website", "Booking-Drt", "Social Media", "Stay-back", "TIE-Group", "Others"], "key": "mob"}
                ]
            },
            {
                "fields": [
                    {"name": "Enquiry Date", "type": "date", "label": "Enquiry Date", "default": date.today(), "key": "enquiry"},
                    {"name": "Check In", "type": "date", "label": "Check In", "default": date.today(), "key": "checkin"},
                    {"name": "Check Out", "type": "date", "label": "Check Out", "default": date.today() + timedelta(days=1), "key": "checkout"},
                    {"name": "No of Days", "type": "disabled_text", "label": "No of Days", "key": "days"}
                ]
            },
            {
                "fields": [
                    {"name": "No of Adults", "type": "number", "label": "No of Adults", "default": 1, "min_value": 0, "key": "adults"},
                    {"name": "No of Children", "type": "number", "label": "No of Children", "default": 0, "min_value": 0, "key": "children"},
                    {"name": "No of Infants", "type": "number", "label": "No of Infants", "default": 0, "min_value": 0, "key": "infants"},
                    {"name": "Breakfast", "type": "selectbox", "label": "Breakfast", "options": ["CP", "EP"], "key": "breakfast"}
                ]
            },
            {
                "fields": [
                    {"name": "Total Pax", "type": "disabled_text", "label": "Total Pax", "key": "pax"},
                    {"name": "No of Days", "type": "disabled_text", "label": "No of Days", "key": "days2"},
                    {"name": "Room Type", "type": "dynamic_selectbox", "label": "Room Type", "key": "roomtype"},
                    {"name": "Room No", "type": "dynamic_selectbox", "label": "Room No", "key": "room"}
                ]
            },
            {
                "fields": [
                    {"name": "Tariff", "type": "number", "label": "Tariff (per day)", "default": 0.0, "min_value": 0.0, "step": 100.0, "key": "tariff"},
                    {"name": "Advance Amount", "type": "number", "label": "Advance Amount", "default": 0.0, "min_value": 0.0, "step": 100.0, "key": "advance"},
                    {"name": "Advance MOP", "type": "selectbox", "label": "Advance MOP", "options": ["Cash", "Card", "UPI", "Bank Transfer", "ClearTrip", "TIE Management", "Booking.com", "Pending", "Other"], "key": "advmop"}
                ]
            },
            {
                "fields": [
                    {"name": "Total Tariff", "type": "disabled_text", "label": "Total Tariff", "key": "total_tariff"},
                    {"name": "Balance Amount", "type": "disabled_text", "label": "Balance Amount", "key": "balance"},
                    {"name": "Balance MOP", "type": "selectbox", "label": "Balance MOP", "options": ["Cash", "Card", "UPI", "Bank Transfer", "Pending", "Other"], "key": "balmop"}
                ]
            },
            {
                "fields": [
                    {"name": "Booking Date", "type": "date", "label": "Booking Date", "default": date.today(), "key": "booking"},
                    {"name": "Invoice No", "type": "text", "label": "Invoice No", "placeholder": "Enter invoice number", "key": "invoice"},
                    {"name": "Plan Status", "type": "selectbox", "label": "Plan Status", "options": ["Confirmed", "Pending", "Cancelled", "Completed", "No Show"], "key": "status"}
                ]
            },
            {
                "fields": [
                    {"name": "Remarks", "type": "text_area", "label": "Remarks", "default": "", "key": "remarks"}
                ]
            },
            {
                "fields": [
                    {"name": "Payment Status", "type": "selectbox", "label": "Payment Status", "options": ["Fully Paid", "Partially Paid", "Not Paid"], "default": "Not Paid", "key": "payment_status"},
                    {"name": "Submitted By", "type": "text", "label": "Submitted By", "placeholder": "Enter submitter name", "key": "submitted_by"}
                ]
            }
        ]

        with st.form(key=form_key):
            form_values = {}
            for row_config in row_configs:
                row_values = render_form_row(row_config, form_key)
                form_values.update(row_values)

            check_in = form_values.get("Check In")
            check_out = form_values.get("Check Out")
            no_of_days = calculate_days(check_in, check_out) if check_in and check_out else 0
            adults = safe_int(form_values.get("No of Adults", 0))
            children = safe_int(form_values.get("No of Children", 0))
            infants = safe_int(form_values.get("No of Infants", 0))
            total_pax = adults + children + infants
            tariff = safe_float(form_values.get("Tariff", 0.0))
            total_tariff = tariff * max(0, no_of_days)
            advance_amount = safe_float(form_values.get("Advance Amount", 0.0))
            balance_amount = max(0, total_tariff - advance_amount)

            form_values["No of Days"] = no_of_days
            form_values["Total Pax"] = total_pax
            form_values["Total Tariff"] = total_tariff
            form_values["Balance Amount"] = balance_amount

            if st.form_submit_button("💾 Save Reservation", use_container_width=True):
                required_fields = ["Property Name", "Room No", "Guest Name", "Mobile No"]
                if not all(form_values.get(field) for field in required_fields):
                    st.error("❌ Please fill in all required fields")
                elif check_out and check_in and check_out < check_in:
                    st.error("❌ Check-out date must be on or after check-in")
                elif no_of_days < 0:
                    st.error("❌ Number of days cannot be negative")
                else:
                    mob_value = form_values.get("Custom MOB") if form_values.get("MOB") == "Others" else form_values.get("MOB")
                    is_duplicate, existing_booking_id = check_duplicate_guest(form_values["Guest Name"], form_values["Mobile No"], form_values["Room No"], mob=mob_value)
                    if is_duplicate:
                        st.error(f"❌ Guest already exists! Booking ID: {existing_booking_id}")
                    else:
                        booking_id = generate_booking_id()
                        if not booking_id:
                            st.error("❌ Failed to generate a unique booking ID")
                            return
                        reservation = {
                            "Property Name": form_values["Property Name"],
                            "Room No": form_values["Room No"],
                            "Guest Name": form_values["Guest Name"],
                            "Mobile No": form_values["Mobile No"],
                            "No of Adults": adults,
                            "No of Children": children,
                            "No of Infants": infants,
                            "Total Pax": total_pax,
                            "Check In": check_in,
                            "Check Out": check_out,
                            "No of Days": no_of_days,
                            "Tariff": tariff,
                            "Total Tariff": total_tariff,
                            "Advance Amount": advance_amount,
                            "Balance Amount": balance_amount,
                            "Advance MOP": form_values.get("Custom Advance MOP") if form_values.get("Advance MOP") == "Other" else form_values.get("Advance MOP"),
                            "Balance MOP": form_values.get("Custom Balance MOP") if form_values.get("Balance MOP") == "Other" else form_values.get("Balance MOP"),
                            "MOB": mob_value,
                            "Online Source": form_values.get("Custom Online Source") if form_values.get("Online Source") == "Others" else form_values.get("Online Source"),
                            "Invoice No": form_values.get("Invoice No"),
                            "Enquiry Date": form_values.get("Enquiry Date"),
                            "Booking Date": form_values.get("Booking Date"),
                            "Booking ID": booking_id,
                            "Room Type": form_values.get("Custom Room Type") if form_values.get("Room Type") == "Other" else form_values.get("Room Type"),
                            "Breakfast": form_values.get("Breakfast"),
                            "Plan Status": form_values.get("Plan Status"),
                            "Submitted By": form_values.get("Submitted By"),
                            "Modified By": "",
                            "Modified Comments": "",
                            "Remarks": form_values.get("Remarks"),
                            "Payment Status": form_values.get("Payment Status")
                        }
                        if save_reservation_to_supabase(reservation):
                            st.success(f"✅ Reservation {booking_id} created successfully!")
                            show_confirmation_dialog(booking_id)
                        else:
                            st.error("❌ Failed to save reservation")
    except Exception as e:
        st.error(f"Error rendering new reservation form: {e}")

def show_edit_reservations(edit_index):
    """Display form for editing an existing reservation with specified row layout."""
    try:
        reservation = st.session_state.reservations[edit_index]
        st.subheader(f"✏️ Editing Reservation: {reservation['Booking ID']}")
        form_key = f"edit_reservation_{edit_index}"
        row_configs = [
            {
                "fields": [
                    {"name": "Property Name", "type": "dynamic_selectbox", "label": "Property Name", "key": "property"},
                    {"name": "Guest Name", "type": "text", "label": "Guest Name", "placeholder": "Enter guest name", "key": "guest"},
                    {"name": "Mobile No", "type": "text", "label": "Mobile No", "placeholder": "Enter mobile number", "key": "mobile"},
                    {"name": "MOB", "type": "selectbox", "label": "MOB (Mode of Booking)", "options": ["Direct", "Online", "Agent", "Walk-in", "Phone", "Website", "Booking-Drt", "Social Media", "Stay-back", "TIE-Group", "Others"], "key": "mob"}
                ]
            },
            {
                "fields": [
                    {"name": "Enquiry Date", "type": "date", "label": "Enquiry Date", "key": "enquiry"},
                    {"name": "Check In", "type": "date", "label": "Check In", "key": "checkin"},
                    {"name": "Check Out", "type": "date", "label": "Check Out", "key": "checkout"},
                    {"name": "No of Days", "type": "disabled_text", "label": "No of Days", "key": "days"}
                ]
            },
            {
                "fields": [
                    {"name": "No of Adults", "type": "number", "label": "No of Adults", "min_value": 0, "key": "adults"},
                    {"name": "No of Children", "type": "number", "label": "No of Children", "min_value": 0, "key": "children"},
                    {"name": "No of Infants", "type": "number", "label": "No of Infants", "min_value": 0, "key": "infants"},
                    {"name": "Breakfast", "type": "selectbox", "label": "Breakfast", "options": ["CP", "EP"], "key": "breakfast"}
                ]
            },
            {
                "fields": [
                    {"name": "Total Pax", "type": "disabled_text", "label": "Total Pax", "key": "pax"},
                    {"name": "No of Days", "type": "disabled_text", "label": "No of Days", "key": "days2"},
                    {"name": "Room Type", "type": "dynamic_selectbox", "label": "Room Type", "key": "roomtype"},
                    {"name": "Room No", "type": "dynamic_selectbox", "label": "Room No", "key": "room"}
                ]
            },
            {
                "fields": [
                    {"name": "Tariff", "type": "number", "label": "Tariff (per day)", "min_value": 0.0, "step": 100.0, "key": "tariff"},
                    {"name": "Advance Amount", "type": "number", "label": "Advance Amount", "min_value": 0.0, "step": 100.0, "key": "advance"},
                    {"name": "Advance MOP", "type": "selectbox", "label": "Advance MOP", "options": ["Cash", "Card", "UPI", "Bank Transfer", "ClearTrip", "TIE Management", "Booking.com", "Pending", "Other"], "key": "advmop"}
                ]
            },
            {
                "fields": [
                    {"name": "Total Tariff", "type": "disabled_text", "label": "Total Tariff", "key": "total_tariff"},
                    {"name": "Balance Amount", "type": "disabled_text", "label": "Balance Amount", "key": "balance"},
                    {"name": "Balance MOP", "type": "selectbox", "label": "Balance MOP", "options": ["Cash", "Card", "UPI", "Bank Transfer", "Pending", "Other"], "key": "balmop"}
                ]
            },
            {
                "fields": [
                    {"name": "Booking Date", "type": "date", "label": "Booking Date", "key": "booking"},
                    {"name": "Invoice No", "type": "text", "label": "Invoice No", "placeholder": "Enter invoice number", "key": "invoice"},
                    {"name": "Plan Status", "type": "selectbox", "label": "Plan Status", "options": ["Confirmed", "Pending", "Cancelled", "Completed", "No Show"], "key": "status"}
                ]
            },
            {
                "fields": [
                    {"name": "Remarks", "type": "text_area", "label": "Remarks", "key": "remarks"}
                ]
            },
            {
                "fields": [
                    {"name": "Payment Status", "type": "selectbox", "label": "Payment Status", "options": ["Fully Paid", "Partially Paid", "Not Paid"], "key": "payment_status"},
                    {"name": "Submitted By", "type": "text", "label": "Submitted By", "placeholder": "Enter submitter name", "key": "submitted_by"}
                ]
            },
            {
                "fields": [
                    {"name": "Modified By", "type": "text", "label": "Modified By", "placeholder": "Enter modifier name", "key": "modified_by"},
                    {"name": "Modified Comments", "type": "text_area", "label": "Modified Comments", "key": "modified_comments"}
                ]
            }
        ]

        with st.form(key=form_key):
            form_values = {}
            for row_config in row_configs:
                row_values = render_form_row(row_config, form_key, reservation)
                form_values.update(row_values)

            check_in = form_values.get("Check In")
            check_out = form_values.get("Check Out")
            no_of_days = calculate_days(check_in, check_out) if check_in and check_out else 0
            adults = safe_int(form_values.get("No of Adults", 0))
            children = safe_int(form_values.get("No of Children", 0))
            infants = safe_int(form_values.get("No of Infants", 0))
            total_pax = adults + children + infants
            tariff = safe_float(form_values.get("Tariff", 0.0))
            total_tariff = tariff * max(0, no_of_days)
            advance_amount = safe_float(form_values.get("Advance Amount", 0.0))
            balance_amount = max(0, total_tariff - advance_amount)

            form_values["No of Days"] = no_of_days
            form_values["Total Pax"] = total_pax
            form_values["Total Tariff"] = total_tariff
            form_values["Balance Amount"] = balance_amount

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.form_submit_button("💾 Save Reservation", use_container_width=True):
                    required_fields = ["Property Name", "Room No", "Guest Name", "Mobile No"]
                    if not all(form_values.get(field) for field in required_fields):
                        st.error("❌ Please fill in all required fields")
                    elif check_out and check_in and check_out < check_in:
                        st.error("❌ Check-out date must be on or after check-in")
                    elif no_of_days < 0:
                        st.error("❌ Number of days cannot be negative")
                    else:
                        mob_value = form_values.get("Custom MOB") if form_values.get("MOB") == "Others" else form_values.get("MOB")
                        is_duplicate, existing_booking_id = check_duplicate_guest(form_values["Guest Name"], form_values["Mobile No"], form_values["Room No"], exclude_booking_id=reservation["Booking ID"], mob=mob_value)
                        if is_duplicate:
                            st.error(f"❌ Guest already exists! Booking ID: {existing_booking_id}")
                        else:
                            updated_reservation = {
                                "Property Name": form_values["Property Name"],
                                "Room No": form_values["Room No"],
                                "Guest Name": form_values["Guest Name"],
                                "Mobile No": form_values["Mobile No"],
                                "No of Adults": adults,
                                "No of Children": children,
                                "No of Infants": infants,
                                "Total Pax": total_pax,
                                "Check In": check_in,
                                "Check Out": check_out,
                                "No of Days": no_of_days,
                                "Tariff": tariff,
                                "Total Tariff": total_tariff,
                                "Advance Amount": advance_amount,
                                "Balance Amount": balance_amount,
                                "Advance MOP": form_values.get("Custom Advance MOP") if form_values.get("Advance MOP") == "Other" else form_values.get("Advance MOP"),
                                "Balance MOP": form_values.get("Custom Balance MOP") if form_values.get("Balance MOP") == "Other" else form_values.get("Balance MOP"),
                                "MOB": mob_value,
                                "Online Source": form_values.get("Custom Online Source") if form_values.get("Online Source") == "Others" else form_values.get("Online Source"),
                                "Invoice No": form_values.get("Invoice No"),
                                "Enquiry Date": form_values.get("Enquiry Date"),
                                "Booking Date": form_values.get("Booking Date"),
                                "Booking ID": reservation["Booking ID"],
                                "Room Type": form_values.get("Custom Room Type") if form_values.get("Room Type") == "Other" else form_values.get("Room Type"),
                                "Breakfast": form_values.get("Breakfast"),
                                "Plan Status": form_values.get("Plan Status"),
                                "Submitted By": form_values.get("Submitted By"),
                                "Modified By": form_values.get("Modified By"),
                                "Modified Comments": form_values.get("Modified Comments"),
                                "Remarks": form_values.get("Remarks"),
                                "Payment Status": form_values.get("Payment Status")
                            }
                            if update_reservation_in_supabase(reservation["Booking ID"], updated_reservation):
                                st.session_state.reservations[edit_index] = updated_reservation
                                st.session_state.edit_mode = False
                                st.session_state.edit_index = None
                                st.success(f"✅ Reservation {reservation['Booking ID']} updated successfully!")
                                show_confirmation_dialog(reservation["Booking ID"], is_update=True)
                            else:
                                st.error("❌ Failed to update reservation")
            with col_btn2:
                if st.session_state.role == "Management":
                    if st.form_submit_button("🗑️ Delete Reservation", use_container_width=True):
                        if delete_reservation_in_supabase(reservation["Booking ID"]):
                            st.session_state.reservations.pop(edit_index)
                            st.session_state.edit_mode = False
                            st.session_state.edit_index = None
                            st.success(f"🗑️ Reservation {reservation['Booking ID']} deleted successfully!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete reservation")
    except Exception as e:
        st.error(f"Error rendering edit form: {e}")

def show_reservations():
    """Display a list of reservations with an option to select one for editing."""
    try:
        st.header("📋 View Reservations")
        if not st.session_state.reservations:
            st.warning("No reservations available to view.")
            return
        booking_ids = [res["Booking ID"] for res in st.session_state.reservations]
        selected_booking = st.selectbox("Select Booking ID", booking_ids)
        if selected_booking:
            edit_index = booking_ids.index(selected_booking)
            st.session_state.edit_mode = True
            st.session_state.edit_index = edit_index
            show_edit_reservations(edit_index)
    except Exception as e:
        st.error(f"Error rendering reservations list: {e}")

def show_analytics():
    """Display reservation analysis with date range filtering."""
    try:
        st.header("📊 Reservation Analysis")
        df = pd.DataFrame(st.session_state.reservations)
        if df.empty:
            st.warning("No reservations available for analysis.")
            return
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", value=date.today() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", value=date.today())
        display_filtered_analysis(df, start_date, end_date, view_mode=False)
    except Exception as e:
        st.error(f"Error rendering analytics: {e}")
