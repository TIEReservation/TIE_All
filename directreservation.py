import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from supabase import create_client, Client

# Booking source dropdown options
BOOKING_SOURCES = [
    "Booking", "Direct", "Bkg-Direct", "Agoda", "Go-MMT", "Walk-In",
    "TIE Group", "Stayflexi", "Airbnb", "Social Media", "Expedia",
    "Cleartrip", "Website"
]

# MOP (Mode of Payment) options - same as online reservations
MOP_OPTIONS = [
    "", "UPI", "Cash", "Go-MMT", "Agoda", "Not Paid", "Bank Transfer", 
    "Card Payment", "Expedia", "Cleartrip", "Website", "AIRBNB"
]

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
        "Le Poshe Beach view": {
            "Double Room": ["101", "102", "202", "203", "204"],
            "Standard Room": ["201"],
            "Deluex Double Room Seaview": ["301", "302", "303", "304"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Millionaire Resort": {
            "Double Room": ["101", "102", "103", "105"],
            "Deluex Double Room with Balcony": ["205", "304", "305"],
            "Deluex Triple Room with Balcony": ["201", "202", "203", "204", "301", "302", "303"],
            "Deluex Family Room with Balcony": ["206", "207", "208", "306", "307", "308"],
            "Deluex Triple Room": ["402"],
            "Deluex Family Room": ["401"],
            "Day Use": ["Day Use 1", "Day Use 2", "Day Use 3", "Day Use 5"],
            "No Show": ["No Show"]
        },
        "Le Poshe Luxury": {
            "2BHA Appartment": ["101&102", "101", "102"],
            "2BHA Appartment with Balcony": ["201&202", "201", "202", "301&302", "301", "302", "401&402", "401", "402"],
            "3BHA Appartment": ["203to205", "203", "204", "205", "303to305", "303", "304", "305", "403to405", "403", "404", "405"],
            "Double Room with Private Terrace": ["501"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "Le Poshe Suite": {
            "2BHA Appartment": ["601&602", "601", "602", "603", "604", "703", "704"],
            "2BHA Appartment with Balcony": ["701&702", "701", "702"],
            "Double Room with Terrace": ["801"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Paradise Residency": {
            "Double Room": ["101", "102", "103", "301", "302", "304"],
            "Family Room": ["201", "203"],
            "Triple Room": ["202", "303"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Paradise Luxury": {
            "3BHA Appartment": ["101to103", "101", "102", "103", "201to203", "201", "202", "203"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Villa Heritage": {
            "Double Room": ["101", "102", "103"],
            "4BHA Appartment": ["201to203&301", "201", "202", "203", "301"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "Le Pondy Beach Side": {
            "Villa": ["101to104", "101", "102", "103", "104"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "Le Royce Villa": {
            "Villa": ["101to102&201to202", "101", "102", "201", "202"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Tamara Luxury": {
            "3BHA": ["101to103", "101", "102", "103", "104to106", "104", "105", "106", "201to203", "201", "202", "203", "204to206", "204", "205", "206", "301to303", "301", "302", "303", "304to306", "304", "305", "306"],
            "4BHA": ["401to404", "401", "402", "403", "404"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Antilia Luxury": {
            "Deluex Suite Room": ["101"],
            "Deluex Double Room": ["203", "204", "303", "304"],
            "Family Room": ["201", "202", "301", "302"],
            "Deluex suite Room with Tarrace": ["404"],
            "Day Use": ["Day Use 1", "Day Use 2"],
            "No Show": ["No Show"]
        },
        "La Tamara Suite": {
            "Two Bedroom apartment": ["101&102"],
            "Deluxe Apartment": ["103&104"],
            "Deluxe Double Room": ["203", "204", "205"],
            "Deluxe Triple Room": ["201", "202"],
            "Deluxe Family Room": ["206"]
        }
    }

def generate_booking_id():
    """
    Generate a unique booking ID by checking existing IDs in Supabase.
    """
    try:
        today = datetime.now().strftime('%Y%m%d')
        response = supabase.table("reservations").select("bookingId").like("bookingId", f"TIE{today}%").execute()
        existing_ids = [record["bookingId"] for record in response.data]
        sequence = 1
        while f"TIE{today}{sequence:03d}" in existing_ids:
            sequence += 1
        return f"TIE{today}{sequence:03d}"
    except Exception as e:
        st.error(f"Error generating booking ID: {e}")
        return None

def insert_reservation_in_supabase(reservation):
    """Insert a new reservation into Supabase."""
    try:
        response = supabase.table("reservations").insert(reservation).execute()
        return bool(response.data)
    except Exception as e:
        st.error(f"Error inserting reservation: {e}")
        return False

def show_new_reservation_form():
    """Display form to create a new direct reservation."""
    st.header("🏠 New Direct Reservation")
    
    # Form layout
    with st.form(key="new_reservation_form"):
        col1, col2 = st.columns(2)
        
        # Column 1
        with col1:
            property_name = st.selectbox(
                "Property Name", 
                sorted(load_property_room_map().keys()),
                key="new_property_name"
            )
            # Get room types for selected property
            room_types = sorted(load_property_room_map()[property_name].keys())
            room_type = st.selectbox(
                "Room Type",
                room_types,
                key="new_room_type"
            )
            # Get room numbers for selected room type
            room_numbers = load_property_room_map()[property_name][room_type]
            room_no = st.selectbox(
                "Room No",
                room_numbers,
                key="new_room_no"
            )
            guest_name = st.text_input("Guest Name", key="new_guest_name")
            guest_phone = st.text_input("Guest Phone", key="new_guest_phone")
            check_in = st.date_input(
                "Check In",
                value=date.today(),
                key="new_check_in"
            )
            check_out = st.date_input(
                "Check Out",
                value=date.today() + timedelta(days=1),
                key="new_check_out"
            )
        
        # Column 2
        with col2:
            no_of_adults = st.number_input(
                "No of Adults",
                min_value=0,
                value=1,
                step=1,
                key="new_no_of_adults"
            )
            no_of_children = st.number_input(
                "No of Children",
                min_value=0,
                value=0,
                step=1,
                key="new_no_of_children"
            )
            no_of_infants = st.number_input(
                "No of Infants",
                min_value=0,
                value=0,
                step=1,
                key="new_no_of_infants"
            )
            rate_plans = st.text_input("Rate Plans", key="new_rate_plans")
            booking_source = st.selectbox(
                "Booking Source",
                BOOKING_SOURCES,
                key="new_booking_source"
            )
            total_tariff = st.number_input(
                "Total Tariff",
                min_value=0.0,
                step=100.0,
                key="new_total_tariff"
            )
            advance_payment = st.number_input(
                "Advance Payment",
                min_value=0.0,
                step=100.0,
                key="new_advance_payment"
            )
            balance = st.number_input(
                "Balance",
                min_value=0.0,
                step=100.0,
                value=total_tariff - advance_payment,
                key="new_balance"
            )
            advance_mop = st.selectbox(
                "Advance MOP",
                MOP_OPTIONS,
                key="new_advance_mop"
            )
            balance_mop = st.selectbox(
                "Balance MOP",
                MOP_OPTIONS,
                key="new_balance_mop"
            )
            booking_status = st.selectbox(
                "Booking Status",
                ["Pending", "Confirmed", "Cancelled", "Completed", "No Show"],
                key="new_booking_status"
            )
            payment_status = st.selectbox(
                "Payment Status",
                ["Not Paid", "Partially Paid", "Fully Paid"],
                key="new_payment_status"
            )
            submitted_by = st.text_input(
                "Submitted By",
                value=st.session_state.username if st.session_state.get('username') else "",
                key="new_submitted_by"
            )
            remarks = st.text_area("Remarks", key="new_remarks")
        
        # Submit button
        submitted = st.form_submit_button("Submit Reservation")
        
        if submitted:
            # Generate booking ID
            booking_id = generate_booking_id()
            if not booking_id:
                st.error("Failed to generate booking ID. Please try again.")
                return
            
            # Prepare reservation data for Supabase
            reservation = {
                "propertyName": property_name,
                "bookingId": booking_id,
                "guestName": guest_name,
                "guestPhone": guest_phone,
                "checkIn": check_in.isoformat(),
                "checkOut": check_out.isoformat(),
                "roomNo": room_no,
                "roomType": room_type,
                "noOfAdults": int(no_of_adults),
                "noOfChildren": int(no_of_children),
                "noOfInfants": int(no_of_infants),
                "ratePlans": rate_plans,
                "bookingSource": booking_source,
                "totalTariff": float(total_tariff),
                "advancePayment": float(advance_payment),
                "balance": float(balance),
                "advanceMop": advance_mop,
                "balanceMop": balance_mop,
                "bookingStatus": booking_status,
                "paymentStatus": payment_status,
                "submittedBy": submitted_by,
                "modifiedBy": "",
                "modifiedComments": "",
                "remarks": remarks
            }
            
            # Insert reservation into Supabase
            if insert_reservation_in_supabase(reservation):
                st.success(f"✅ Reservation {booking_id} created successfully!")
                st.session_state.reservations.append({
                    "Property Name": property_name,
                    "Booking ID": booking_id,
                    "Guest Name": guest_name,
                    "Guest Phone": guest_phone,
                    "Check In": check_in.isoformat(),
                    "Check Out": check_out.isoformat(),
                    "Room No": room_no,
                    "Room Type": room_type,
                    "No of Adults": int(no_of_adults),
                    "No of Children": int(no_of_children),
                    "No of Infants": int(no_of_infants),
                    "Rate Plans": rate_plans,
                    "Booking Source": booking_source,
                    "Total Tariff": float(total_tariff),
                    "Advance Payment": float(advance_payment),
                    "Balance": float(balance),
                    "Advance MOP": advance_mop,
                    "Balance MOP": balance_mop,
                    "Booking Status": booking_status,
                    "Payment Status": payment_status,
                    "Submitted By": submitted_by,
                    "Modified By": "",
                    "Modified Comments": "",
                    "Remarks": remarks
                })
                st.rerun()
            else:
                st.error("❌ Failed to create reservation. Please try again.")

def load_reservations_from_supabase():
    """Load all reservations from Supabase."""
    try:
        response = supabase.table("reservations").select("*").order("checkIn", desc=True).execute()
        if not response.data:
            st.warning("No reservations found in Supabase.")
            return []
        
        # Transform Supabase camelCase to title case for UI consistency
        transformed_data = []
        for record in response.data:
            transformed_record = {
                "Property Name": record.get("propertyName", ""),
                "Booking ID": record.get("bookingId", ""),
                "Guest Name": record.get("guestName", ""),
                "Guest Phone": record.get("guestPhone", ""),
                "Check In": record.get("checkIn", ""),
                "Check Out": record.get("checkOut", ""),
                "Room No": record.get("roomNo", ""),
                "Room Type": record.get("roomType", ""),
                "No of Adults": record.get("noOfAdults", 0),
                "No of Children": record.get("noOfChildren", 0),
                "No of Infants": record.get("noOfInfants", 0),
                "Rate Plans": record.get("ratePlans", ""),
                "Booking Source": record.get("bookingSource", ""),
                "Total Tariff": record.get("totalTariff", 0.0),
                "Advance Payment": record.get("advancePayment", 0.0),
                "Balance": record.get("balance", 0.0),
                "Advance MOP": record.get("advanceMop", "Not Paid"),
                "Balance MOP": record.get("balanceMop", "Not Paid"),
                "Booking Status": record.get("bookingStatus", "Pending"),
                "Payment Status": record.get("paymentStatus", "Not Paid"),
                "Submitted By": record.get("submittedBy", ""),
                "Modified By": record.get("modifiedBy", ""),
                "Modified Comments": record.get("modifiedComments", ""),
                "Remarks": record.get("remarks", "")
            }
            transformed_data.append(transformed_record)
        return transformed_data
    except Exception as e:
        st.error(f"Error loading reservations: {e}")
        return []

def insert_reservation_in_supabase(reservation):
    """Insert a new reservation into Supabase."""
    try:
        response = supabase.table("reservations").insert(reservation).execute()
        return bool(response.data)
    except Exception as e:
        st.error(f"Error inserting reservation: {e}")
        return False

def update_reservation_in_supabase(booking_id, updated_reservation):
    """Update a reservation in Supabase."""
    try:
        supabase_reservation = {
            "propertyName": updated_reservation["propertyName"],
            "bookingId": updated_reservation["bookingId"],
            "guestName": updated_reservation["guestName"],
            "guestPhone": updated_reservation["guestPhone"],
            "checkIn": updated_reservation["checkIn"],
            "checkOut": updated_reservation["checkOut"],
            "roomNo": updated_reservation["roomNo"],
            "roomType": updated_reservation["roomType"],
            "noOfAdults": updated_reservation["noOfAdults"],
            "noOfChildren": updated_reservation["noOfChildren"],
            "noOfInfants": updated_reservation["noOfInfants"],
            "ratePlans": updated_reservation["ratePlans"],
            "bookingSource": updated_reservation["bookingSource"],
            "totalTariff": updated_reservation["totalTariff"],
            "advancePayment": updated_reservation["advancePayment"],
            "balance": updated_reservation["balance"],
            "advanceMop": updated_reservation["advanceMop"],
            "balanceMop": updated_reservation["balanceMop"],
            "bookingStatus": updated_reservation["bookingStatus"],
            "paymentStatus": updated_reservation["paymentStatus"],
            "submittedBy": updated_reservation["submittedBy"],
            "modifiedBy": updated_reservation["modifiedBy"],
            "modifiedComments": updated_reservation["modifiedComments"],
            "remarks": updated_reservation["remarks"]
        }
        response = supabase.table("reservations").update(supabase_reservation).eq("bookingId", booking_id).execute()
        return bool(response.data)
    except Exception as e:
        st.error(f"Error updating reservation {booking_id}: {e}")
        return False

def delete_reservation_in_supabase(booking_id):
    """Delete a reservation from Supabase."""
    try:
        response = supabase.table("reservations").delete().eq("bookingId", booking_id).execute()
        return bool(response.data)
    except Exception as e:
        st.error(f"Error deleting reservation {booking_id}: {e}")
        return False

def display_filtered_analysis(df, start_date, end_date, view_mode=True):
    """Helper function to filter dataframe for analytics or view."""
    filtered_df = df.copy()
    try:
        if start_date:
            filtered_df = filtered_df[pd.to_datetime(filtered_df["Check In"]) >= pd.to_datetime(start_date)]
        if end_date:
            filtered_df = filtered_df[pd.to_datetime(filtered_df["Check In"]) <= pd.to_datetime(end_date)]
    except Exception as e:
        st.error(f"Error filtering data: {e}")
    return filtered_df
