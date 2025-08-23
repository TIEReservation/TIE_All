import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# Initialize Supabase client
try:
    supabase: Client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
except KeyError as e:
    st.error(f"Missing Supabase secret: {e}. Please check Streamlit Cloud secrets configuration.")
    st.stop()

def load_property_room_map():
    """
    Loads the property to room type to room numbers mapping based on provided data.
    Keys and values are kept as-is from the user's input, including typos and combined rooms.
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
            "Villa": ["101to102&201to202", "101", "102", "202", "202"]  # Note: duplicate "202" as per data
        },
        "La Tamara Luxury": {
            "3BHA": ["101to103", "101", "102", "103", "104to106", "104", "105", "106", "201to203", "201", "202", "203", "204to206", "204", "205", "206", "301to303", "301", "302", "303", "304to306", "304", "305", "306"],
            "4BHA": ["401to404", "401", "402", "403", "404"]  # Note: duplicate "404" as per data
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
        # Note: "Property 16" not in data, so omitted to prevent empty dropdowns
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
    """Check for duplicate guest based on name, mobile number, and room number, allowing 'Stay-back' if MOB differs."""
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
                "Room No": record["room_no"] or "",  # Handle None
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
                "Room Type": record["room_type"] or "",  # Handle None
                "Breakfast": record["breakfast"] or "",
                "Plan Status": record["plan_status"] or "",
                "Submitted By": record.get("submitted_by", ""),
                "Modified By": record.get("modified_by", ""),
                "Modified Comments": record.get("modified_comments", "")
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
            "modified_comments": reservation["Modified Comments"]
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
            "modified_comments": updated_reservation["Modified Comments"]
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

def show_new_reservation_form():
    """Display form for creating a new reservation with dynamic room assignments."""
    try:
        st.header("📝 Direct Reservations")
        form_key = "new_reservation"

        col1, col2, col3 = st.columns(3)
        with col1:
            # Use properties from load_property_room_map
            property_options = sorted(load_property_room_map().keys())
            property_name = st.selectbox("Property Name", property_options, key=f"{form_key}_property")
            
            # Dynamic room types based on property
            room_map = load_property_room_map()
            available_room_types = sorted(room_map.get(property_name, {}).keys())
            room_type_options = available_room_types + ["Dayuse"] if "Dayuse" not in available_room_types else available_room_types
            if not available_room_types:
                st.warning("No room types available for this property. Use 'Dayuse'.")
            room_type = st.selectbox("Room Type", room_type_options, key=f"{form_key}_roomtype")
            if room_type == "Dayuse":
                custom_room_type = st.text_input("Custom Room Type", key=f"{form_key}_custom_roomtype")
            else:
                custom_room_type = None
            
            # Dynamic room numbers based on property and room type
            available_rooms = sorted(room_map.get(property_name, {}).get(room_type, [])) if room_type != "Dayuse" else []
            if available_rooms:
                room_no = st.selectbox("Room No", available_rooms, key=f"{form_key}_room")
            else:
                st.warning("No rooms available for this room type. Enter manually.")
                room_no = st.text_input("Room No", placeholder="Enter room number", key=f"{form_key}_room")
            
            guest_name = st.text_input("Guest Name", placeholder="Enter guest name", key=f"{form_key}_guest")
            mobile_no = st.text_input("Mobile No", placeholder="Enter mobile number", key=f"{form_key}_mobile")
        with col2:
            adults = st.number_input("No of Adults", min_value=0, value=1, key=f"{form_key}_adults")
            children = st.number_input("No of Children", min_value=0, value=0, key=f"{form_key}_children")
            infants = st.number_input("No of Infants", min_value=0, value=0, key=f"{form_key}_infants")
            total_pax = safe_int(adults) + safe_int(children) + safe_int(infants)
            st.text_input("Total Pax", value=str(total_pax), disabled=True, help="Adults + Children + Infants")
        with col3:
            check_in = st.date_input("Check In", value=date.today(), key=f"{form_key}_checkin")
            check_out = st.date_input("Check Out", value=date.today() + timedelta(days=1), key=f"{form_key}_checkout")
            no_of_days = calculate_days(check_in, check_out)
            st.text_input("No of Days", value=str(no_of_days), disabled=True, help="Check-out - Check-in")

        col4, col5 = st.columns(2)
        with col4:
            tariff = st.number_input("Tariff (per day)", min_value=0.0, value=0.0, step=100.0, key=f"{form_key}_tariff")
            total_tariff = safe_float(tariff) * max(0, no_of_days)
            st.text_input("Total Tariff", value=f"₹{total_tariff:.2f}", disabled=True, help="Tariff × No of Days")
            advance_mop = st.selectbox("Advance MOP",
                                       ["Cash", "Card", "UPI", "Bank Transfer", "ClearTrip", "TIE Management", "Booking.com", "Pending", "Other"],
                                       key=f"{form_key}_advmop")
            if advance_mop == "Other":
                custom_advance_mop = st.text_input("Custom Advance MOP", key=f"{form_key}_custom_advmop")
            else:
                custom_advance_mop = None
            balance_mop = st.selectbox("Balance MOP",
                                       ["Cash", "Card", "UPI", "Bank Transfer", "Pending", "Other"],
                                       key=f"{form_key}_balmop")
            if balance_mop == "Other":
                custom_balance_mop = st.text_input("Custom Balance MOP", key=f"{form_key}_custom_balmop")
            else:
                custom_balance_mop = None
        with col5:
            advance_amount = st.number_input("Advance Amount", min_value=0.0, value=0.0, step=100.0, key=f"{form_key}_advance")
            balance_amount = max(0, total_tariff - safe_float(advance_amount))
            st.text_input("Balance Amount", value=f"₹{balance_amount:.2f}", disabled=True, help="Total Tariff - Advance Amount")
            mob = st.selectbox("MOB (Mode of Booking)",
                               ["Direct", "Online", "Agent", "Walk-in", "Phone", "Website", "Booking-Drt", "Social Media", "Stay-back", "TIE-Group", "Others"],
                               key=f"{form_key}_mob")
            if mob == "Others":
                custom_mob = st.text_input("Custom MOB", key=f"{form_key}_custom_mob")
            else:
                custom_mob = None
            if mob == "Online":
                online_source = st.selectbox("Online Source",
                                             ["Booking.com", "Agoda Prepaid", "Agoda Booking.com", "Expedia", "MMT", "Cleartrip", "Others"],
                                             key=f"{form_key}_online_source")
                if online_source == "Others":
                    custom_online_source = st.text_input("Custom Online Source", key=f"{form_key}_custom_online_source")
                else:
                    custom_online_source = None
            else:
                online_source = None
                custom_online_source = None
            invoice_no = st.text_input("Invoice No", placeholder="Enter invoice number", key=f"{form_key}_invoice")

        col6, col7 = st.columns(2)
        with col6:
            enquiry_date = st.date_input("Enquiry Date", value=date.today(), key=f"{form_key}_enquiry")
            booking_date = st.date_input("Booking Date", value=date.today(), key=f"{form_key}_booking")
        with col7:
            breakfast = st.selectbox("Breakfast", ["CP", "EP"], key=f"{form_key}_breakfast")
            plan_status = st.selectbox("Plan Status", ["Confirmed", "Pending", "Cancelled", "Completed", "No Show"], key=f"{form_key}_status")
            submitted_by = st.text_input("Submitted By", placeholder="Enter submitter name", key=f"{form_key}_submitted_by")

        if st.button("💾 Save Reservation", use_container_width=True):
            if not all([property_name, room_no, guest_name, mobile_no]):
                st.error("❌ Please fill in all required fields")
            elif check_out < check_in:
                st.error("❌ Check-out date must be on or after check-in")
            elif no_of_days < 0:
                st.error("❌ Number of days cannot be negative")
            else:
                mob_value = custom_mob if mob == "Others" else mob
                is_duplicate, existing_booking_id = check_duplicate_guest(guest_name, mobile_no, room_no, mob=mob_value)
                if is_duplicate:
                    st.error(f"❌ Guest already exists! Booking ID: {existing_booking_id}")
                else:
                    booking_id = generate_booking_id()
                    if not booking_id:
                        st.error("❌ Failed to generate a unique booking ID")
                        return
                    reservation = {
                        "Property Name": property_name,
                        "Room No": room_no,
                        "Guest Name": guest_name,
                        "Mobile No": mobile_no,
                        "No of Adults": safe_int(adults),
                        "No of Children": safe_int(children),
                        "No of Infants": safe_int(infants),
                        "Total Pax": total_pax,
                        "Check In": check_in,
                        "Check Out": check_out,
                        "No of Days": no_of_days,
                        "Tariff": safe_float(tariff),
                        "Total Tariff": total_tariff,
                        "Advance Amount": safe_float(advance_amount),
                        "Balance Amount": balance_amount,
                        "Advance MOP": custom_advance_mop if advance_mop == "Other" else advance_mop,
                        "Balance MOP": custom_balance_mop if balance_mop == "Other" else balance_mop,
                        "MOB": mob_value,
                        "Online Source": custom_online_source if online_source == "Others" else online_source,
                        "Invoice No": invoice_no,
                        "Enquiry Date": enquiry_date,
                        "Booking Date": booking_date,
                        "Booking ID": booking_id,
                        "Room Type": custom_room_type if room_type == "Other" else room_type,
                        "Breakfast": breakfast,
                        "Plan Status": plan_status,
                        "Submitted By": submitted_by,
                        "Modified By": "",
                        "Modified Comments": ""
                    }
                    if save_reservation_to_supabase(reservation):
                        st.success(f"✅ Reservation {booking_id} created successfully!")
                        show_confirmation_dialog(booking_id)
                    else:
                        st.error("❌ Failed to save reservation")
    except Exception as e:
        st.error(f"Error rendering new reservation form: {e}")

def show_reservations():
    """Display all reservations with filtering options."""
    if not st.session_state.reservations:
        st.info("No reservations available.")
        return

    st.header("📋 View Reservations")
    df = pd.DataFrame(st.session_state.reservations)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        filter_status = st.selectbox("Filter by Status", ["All", "Confirmed", "Pending", "Cancelled", "Completed", "No Show"], key="view_filter_status")
    with col2:
        filter_check_in_date = st.date_input("Check-in Date", value=None, key="view_filter_check_in_date")
    with col3:
        filter_check_out_date = st.date_input("Check-out Date", value=None, key="view_filter_check_out_date")
    with col4:
        filter_enquiry_date = st.date_input("Enquiry Date", value=None, key="view_filter_enquiry_date")
    with col5:
        filter_booking_date = st.date_input("Booking Date", value=None, key="view_filter_booking_date")
    with col6:
        filter_property = st.selectbox("Filter by Property", ["All"] + sorted(df["Property Name"].unique()), key="view_filter_property")

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

def show_edit_reservations():
    """Display reservations for editing with filtering options."""
    try:
        st.header("✏️ Edit Reservations")
        if not st.session_state.reservations:
            st.info("No reservations available to edit.")
            return

        df = pd.DataFrame(st.session_state.reservations)
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        with col1:
            filter_status = st.selectbox("Filter by Status", ["All", "Confirmed", "Pending", "Cancelled", "Completed", "No Show"], key="edit_filter_status")
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

def show_edit_form(edit_index):
    """Display form for editing an existing reservation with dynamic room assignments."""
    try:
        st.subheader(f"✏️ Editing Reservation: {st.session_state.reservations[edit_index]['Booking ID']}")
        reservation = st.session_state.reservations[edit_index]
        form_key = f"edit_reservation_{edit_index}"

        col1, col2, col3 = st.columns(3)
        with col1:
            # Use properties from load_property_room_map, add Property 16 if in reservation
            property_options = sorted(load_property_room_map().keys())
            if reservation["Property Name"] == "Property 16":
                property_options = sorted(property_options + ["Property 16"])
            property_index = property_options.index(reservation["Property Name"]) if reservation["Property Name"] in property_options else 0
            property_name = st.selectbox("Property Name", property_options, index=property_index, key=f"{form_key}_property")
            
            # Dynamic room types, handle existing if not in list by setting to "Other"
            room_map = load_property_room_map()
            available_room_types = sorted(room_map.get(property_name, {}).keys())
            is_custom_type = reservation["Room Type"] not in available_room_types or not reservation["Room Type"]
            room_type_options = available_room_types + ["Other"] if "Other" not in available_room_types else available_room_types
            room_type_index = room_type_options.index("Other" if is_custom_type else reservation["Room Type"])
            room_type = st.selectbox("Room Type", room_type_options, index=room_type_index, key=f"{form_key}_roomtype")
            if room_type == "Other":
                custom_room_type = st.text_input("Custom Room Type", value=reservation["Room Type"] if is_custom_type else "", key=f"{form_key}_custom_roomtype")
            else:
                custom_room_type = None
            
            # Dynamic room numbers, augment with existing if not in list and not None
            available_rooms = sorted(room_map.get(property_name, {}).get(room_type, [])) if room_type != "Other" else []
            existing_room_no = reservation["Room No"] or ""
            if existing_room_no and existing_room_no not in available_rooms:
                available_rooms = sorted(set(available_rooms + [existing_room_no]))
            if available_rooms:
                room_no_index = available_rooms.index(existing_room_no) if existing_room_no in available_rooms else 0
                room_no = st.selectbox("Room No", available_rooms, index=room_no_index, key=f"{form_key}_room")
            else:
                st.warning("No rooms available for this room type. Enter manually.")
                room_no = st.text_input("Room No", value=existing_room_no, key=f"{form_key}_room")
            
            guest_name = st.text_input("Guest Name", value=reservation["Guest Name"], key=f"{form_key}_guest")
            mobile_no = st.text_input("Mobile No", value=reservation["Mobile No"], key=f"{form_key}_mobile")
        with col2:
            adults = st.number_input("No of Adults", min_value=0, value=reservation["No of Adults"], key=f"{form_key}_adults")
            children = st.number_input("No of Children", min_value=0, value=reservation["No of Children"], key=f"{form_key}_children")
            infants = st.number_input("No of Infants", min_value=0, value=reservation["No of Infants"], key=f"{form_key}_infants")
            total_pax = safe_int(adults) + safe_int(children) + safe_int(infants)
            st.text_input("Total Pax", value=str(total_pax), disabled=True, help="Adults + Children + Infants")
        with col3:
            check_in = st.date_input("Check In", value=reservation["Check In"], key=f"{form_key}_checkin")
            check_out = st.date_input("Check Out", value=reservation["Check Out"], key=f"{form_key}_checkout")
            no_of_days = calculate_days(check_in, check_out)
            st.text_input("No of Days", value=str(no_of_days), disabled=True, help="Check-out - Check-in")

        col4, col5 = st.columns(2)
        with col4:
            tariff = st.number_input("Tariff (per day)", min_value=0.0, value=reservation["Tariff"], step=100.0, key=f"{form_key}_tariff")
            total_tariff = safe_float(tariff) * max(0, no_of_days)
            st.text_input("Total Tariff", value=f"₹{total_tariff:.2f}", disabled=True, help="Tariff × No of Days")
            advance_mop_options = ["Cash", "Card", "UPI", "Bank Transfer", "ClearTrip", "TIE Management", "Booking.com", "Pending", "Other"]
            advance_mop_index = advance_mop_options.index(reservation["Advance MOP"]) if reservation["Advance MOP"] in advance_mop_options else len(advance_mop_options) - 1
            advance_mop = st.selectbox("Advance MOP", advance_mop_options, index=advance_mop_index, key=f"{form_key}_advmop")
            if advance_mop == "Other":
                custom_advance_mop = st.text_input("Custom Advance MOP", value=reservation["Advance MOP"] if advance_mop_index == len(advance_mop_options) - 1 else "", key=f"{form_key}_custom_advmop")
            else:
                custom_advance_mop = None
            balance_mop_options = ["Cash", "Card", "UPI", "Bank Transfer", "Pending", "Other"]
            balance_mop_index = balance_mop_options.index(reservation["Balance MOP"]) if reservation["Balance MOP"] in balance_mop_options else len(balance_mop_options) - 1
            balance_mop = st.selectbox("Balance MOP", balance_mop_options, index=balance_mop_index, key=f"{form_key}_balmop")
            if balance_mop == "Other":
                custom_balance_mop = st.text_input("Custom Balance MOP", value=reservation["Balance MOP"] if balance_mop_index == len(balance_mop_options) - 1 else "", key=f"{form_key}_custom_balmop")
            else:
                custom_balance_mop = None
        with col5:
            advance_amount = st.number_input("Advance Amount", min_value=0.0, value=reservation["Advance Amount"], step=100.0, key=f"{form_key}_advance")
            balance_amount = max(0, total_tariff - safe_float(advance_amount))
            st.text_input("Balance Amount", value=f"₹{balance_amount:.2f}", disabled=True, help="Total Tariff - Advance Amount")
            mob_options = ["Direct", "Online", "Agent", "Walk-in", "Phone", "Website", "Booking-Drt", "Social Media", "Stay-back", "TIE-Group", "Others"]
            mob_index = mob_options.index(reservation["MOB"]) if reservation["MOB"] in mob_options else len(mob_options) - 1
            mob = st.selectbox("MOB (Mode of Booking)", mob_options, index=mob_index, key=f"{form_key}_mob")
            if mob == "Others":
                custom_mob = st.text_input("Custom MOB", value=reservation["MOB"] if mob_index == len(mob_options) - 1 else "", key=f"{form_key}_custom_mob")
            else:
                custom_mob = None
            if mob == "Online":
                online_source_options = ["Booking.com", "Agoda Prepaid", "Agoda Booking.com", "Expedia", "MMT", "Cleartrip", "Others"]
                online_source_index = online_source_options.index(reservation["Online Source"]) if reservation["Online Source"] in online_source_options else len(online_source_options) - 1
                online_source = st.selectbox("Online Source", online_source_options, index=online_source_index, key=f"{form_key}_online_source")
                if online_source == "Others":
                    custom_online_source = st.text_input("Custom Online Source", value=reservation["Online Source"] if online_source_index == len(online_source_options) - 1 else "", key=f"{form_key}_custom_online_source")
                else:
                    custom_online_source = None
            else:
                online_source = None
                custom_online_source = None
            invoice_no = st.text_input("Invoice No", value=reservation["Invoice No"], key=f"{form_key}_invoice")

        col6, col7 = st.columns(2)
        with col6:
            enquiry_date = st.date_input("Enquiry Date", value=reservation["Enquiry Date"], key=f"{form_key}_enquiry")
            booking_date = st.date_input("Booking Date", value=reservation["Booking Date"], key=f"{form_key}_booking")
            submitted_by = st.text_input("Submitted By", value=reservation["Submitted By"], key=f"{form_key}_submitted_by")
        with col7:
            breakfast = st.selectbox("Breakfast", ["CP", "EP"], index=["CP", "EP"].index(reservation["Breakfast"]), key=f"{form_key}_breakfast")
            plan_status = st.selectbox("Plan Status", ["Confirmed", "Pending", "Cancelled", "Completed", "No Show"], index=["Confirmed", "Pending", "Cancelled", "Completed", "No Show"].index(reservation["Plan Status"]), key=f"{form_key}_status")
            modified_by = st.text_input("Modified By", value=reservation["Modified By"], key=f"{form_key}_modified_by")
            modified_comments = st.text_area("Modified Comments", value=reservation["Modified Comments"], key=f"{form_key}_modified_comments")

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("💾 Save Reservation", key=f"{form_key}_update", use_container_width=True):
                if not all([property_name, room_no, guest_name, mobile_no]):
                    st.error("❌ Please fill in all required fields")
                elif check_out < check_in:
                    st.error("❌ Check-out date must be on or after check-in")
                elif no_of_days < 0:
                    st.error("❌ Number of days cannot be negative")
                else:
                    mob_value = custom_mob if mob == "Others" else mob
                    is_duplicate, existing_booking_id = check_duplicate_guest(guest_name, mobile_no, room_no, exclude_booking_id=reservation["Booking ID"], mob=mob_value)
                    if is_duplicate:
                        st.error(f"❌ Guest already exists! Booking ID: {existing_booking_id}")
                    else:
                        updated_reservation = {
                            "Property Name": property_name,
                            "Room No": room_no,
                            "Guest Name": guest_name,
                            "Mobile No": mobile_no,
                            "No of Adults": safe_int(adults),
                            "No of Children": safe_int(children),
                            "No of Infants": safe_int(infants),
                            "Total Pax": total_pax,
                            "Check In": check_in,
                            "Check Out": check_out,
                            "No of Days": no_of_days,
                            "Tariff": safe_float(tariff),
                            "Total Tariff": total_tariff,
                            "Advance Amount": safe_float(advance_amount),
                            "Balance Amount": balance_amount,
                            "Advance MOP": custom_advance_mop if advance_mop == "Other" else advance_mop,
                            "Balance MOP": custom_balance_mop if balance_mop == "Other" else balance_mop,
                            "MOB": mob_value,
                            "Online Source": custom_online_source if online_source == "Others" else online_source,
                            "Invoice No": invoice_no,
                            "Enquiry Date": enquiry_date,
                            "Booking Date": booking_date,
                            "Booking ID": reservation["Booking ID"],
                            "Room Type": custom_room_type if room_type == "Other" else room_type,
                            "Breakfast": breakfast,
                            "Plan Status": plan_status,
                            "Submitted By": submitted_by,
                            "Modified By": modified_by,
                            "Modified Comments": modified_comments
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
            if st.button("🗑️ Delete Reservation", key=f"{form_key}_delete", use_container_width=True):
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

def show_analytics():
    """Display analytics dashboard for Management users."""
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
        filter_status = st.selectbox("Filter by Status", ["All", "Confirmed", "Pending", "Cancelled", "Completed", "No Show"], key="analytics_filter_status")
    with col2:
        filter_check_in_date = st.date_input("Check-in Date", value=None, key="analytics_filter_check_in_date")
    with col3:
        filter_check_out_date = st.date_input("Check-out Date", value=None, key="analytics_filter_check_out_date")
    with col4:
        filter_enquiry_date = st.date_input("Enquiry Date", value=None, key="analytics_filter_enquiry_date")
    with col5:
        filter_booking_date = st.date_input("Booking Date", value=None, key="analytics_filter_booking_date")
    with col6:
        filter_property = st.selectbox("Filter by Property", ["All"] + sorted(df["Property Name"].unique()), key="analytics_filter_property")

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
            height=400
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    with col2:
        revenue_by_property = filtered_df.groupby("Property Name")["Total Tariff"].sum().reset_index()
        fig_bar = px.bar(
            revenue_by_property,
            x="Property Name",
            y="Total Tariff",
            title="Total Revenue by Property",
            height=400,
            labels={"Total Tariff": "Revenue (₹)"}
        )
        st.plotly_chart(fig_bar, use_container_width=True)

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
                property_df[["Booking ID", "Guest Name", "Room No", "Check In", "Check Out", "Total Tariff", "Plan Status", "MOB"]],
                use_container_width=True
            )
