import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from supabase import create_client, Client
from urllib.parse import urlencode

# Safe imports and initialization
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    st.warning("Requests library not available")
    REQUESTS_AVAILABLE = False

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    st.warning("Supabase library not available")
    SUPABASE_AVAILABLE = False

# Initialize Supabase client
supabase = None
if SUPABASE_AVAILABLE:
    try:
        supabase = create_client(
            st.secrets["supabase"]["url"],
            st.secrets["supabase"]["key"]
        )
    except Exception as e:
        st.error(f"Failed to initialize Supabase: {str(e)}")

# Stayflexi API configuration
try:
    from config import STAYFLEXI_API_TOKEN, STAYFLEXI_API_BASE_URL, STAYFLEXI_EMAIL
except ImportError:
    try:
        STAYFLEXI_API_TOKEN = st.secrets.get("stayflexi", {}).get("STAYFLEXI_API_TOKEN", "")
        STAYFLEXI_API_BASE_URL = st.secrets.get("stayflexi", {}).get("STAYFLEXI_API_BASE_URL", "")
        STAYFLEXI_EMAIL = st.secrets.get("stayflexi", {}).get("STAYFLEXI_EMAIL", "")
    except Exception as e:
        st.warning(f"Could not load API configuration: {str(e)}")

def generate_booking_id():
    """Generate a unique booking ID."""
    try:
        today = datetime.now().strftime('%Y%m%d')
        response = supabase.table("reservations").select("booking_id").like("booking_id", f"TIE{today}%").execute()
        existing_ids = [record["booking_id"] for record in response.data]
        sequence = 1
        while f"TIE{today}{sequence:03d}" in existing_ids:
            sequence += 1
        return f"TIE{today}{sequence:03d}"
    except Exception as e:
        st.error(f"Error generating booking ID: {str(e)}")
        return None

def fetch_stayflexi_properties():
    """Fetch list of properties from Stayflexi API."""
    if not REQUESTS_AVAILABLE or not STAYFLEXI_API_TOKEN or not STAYFLEXI_API_BASE_URL or not STAYFLEXI_EMAIL:
        st.error("Cannot fetch properties: Missing requests library or API configuration")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {STAYFLEXI_API_TOKEN}",
            "Content-Type": "application/json"
        }
        endpoint = f"{STAYFLEXI_API_BASE_URL}/common/hotel-detail"
        params = {
            "isGroupProperty": "true",
            "emailId": STAYFLEXI_EMAIL
        }
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return [hotel for hotel in response.json() if hotel.get("status") == "ACTIVE"]
    except requests.RequestException as e:
        st.error(f"Failed to fetch Stayflexi properties: {str(e)}")
        return None

def fetch_stayflexi_bookings(start_date: str, end_date: str = None):
    """
    Fetch bookings from Stayflexi API for all active properties.
    Args:
        start_date: YYYY-MM-DD format
        end_date: YYYY-MM-DD format (optional, defaults to start_date)
    Returns:
        List of bookings with property details
    """
    if not REQUESTS_AVAILABLE or not STAYFLEXI_API_TOKEN or not STAYFLEXI_API_BASE_URL:
        st.error("Cannot fetch bookings: Missing requests library or API configuration")
        return None

    properties = fetch_stayflexi_properties()
    if not properties:
        return None

    all_bookings = []
    try:
        headers = {
            "Authorization": f"Bearer {STAYFLEXI_API_TOKEN}",
            "Content-Type": "application/json"
        }
        for property in properties:
            hotel_id = property.get("hotelId")
            hotel_name = property.get("hotelName")
            endpoint = f"{STAYFLEXI_API_BASE_URL}/api/v2/reports/generateDashDataLite/"
            params = {
                "date": start_date,
                "is_today": "true",
                "hotel_id": hotel_id,
                "hotelId": hotel_id
            }
            if end_date:
                params["end_date"] = end_date

            response = requests.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            booking_data = response.json()
            # Combine all booking statuses (CHECKINS, NEW_BOOKINGS, CANCELLED, etc.)
            for status in ["CHECKINS", "NEW_BOOKINGS", "CANCELLED", "ON_HOLD", "NO_SHOW"]:
                bookings = booking_data.get(status, [])
                for booking in bookings:
                    booking["hotel_id"] = hotel_id
                    booking["hotel_name"] = hotel_name
                    all_bookings.append(booking)
        return all_bookings
    except requests.RequestException as e:
        st.error(f"Failed to fetch Stayflexi bookings: {str(e)}")
        return None

def map_stayflexi_to_supabase(booking):
    """
    Map Stayflexi booking data to Supabase schema.
    """
    try:
        return {
            "booking_id": booking.get("reservation_id", generate_booking_id()),
            "property_name": booking.get("hotel_name", ""),
            "booking_date": booking.get("booking_made", datetime.now().strftime("%Y-%m-%d")),
            "booking_source": booking.get("booking_source", "Stayflexi"),
            "guest_name": booking.get("user_name", ""),
            "guest_phone": booking.get("user_phone", ""),
            "check_in": booking.get("check_in", ""),
            "check_out": booking.get("check_out", ""),
            "total_amount": float(booking.get("booking_amount", 0.0)),
            "advance": float(booking.get("balance_due", 0.0)),
            "no_of_adults": int(booking.get("adults", 0)),
            "no_of_children": int(booking.get("children", 0)),
            "no_of_infants": 0,  # Stayflexi data doesn't provide infants
            "total_pax": int(booking.get("adults", 0)) + int(booking.get("children", 0)),
            "room_no": booking.get("room_ids", ""),
            "amt_without_tax": float(booking.get("booking_amount", 0.0)) - float(booking.get("fee_amount", 0.0)),
            "tax": float(booking.get("fee_amount", 0.0)),
            "room_type": booking.get("room_type", ""),
            "breakfast": booking.get("rate_plan_name", "EP"),
            "status": booking.get("reservation_status", "PENDING").upper(),
            "submitted_by": "Stayflexi API",
            "remarks": "",
            "mob": "Online"
        }
    except Exception as e:
        st.error(f"Error mapping booking to Supabase schema: {str(e)}")
        return None

def save_to_supabase(booking):
    """Save a booking to Supabase reservations table."""
    try:
        # Check for duplicate booking_id
        response = supabase.table("reservations").select("booking_id").eq("booking_id", booking["booking_id"]).execute()
        if response.data:
            return False  # Booking already exists
        response = supabase.table("reservations").insert(booking).execute()
        if response.data:
            return True
        else:
            st.error("Failed to save booking to Supabase")
            return False
    except Exception as e:
        st.error(f"Error saving to Supabase: {str(e)}")
        return False

def show_online_reservations():
    """
    Display and sync online reservations from Stayflexi.
    """
    st.header("📡 Online Reservations")

    # Show system status
    with st.expander("System Status", expanded=False):
        st.write(f"Requests Available: {'✅' if REQUESTS_AVAILABLE else '❌'}")
        st.write(f"Supabase Available: {'✅' if SUPABASE_AVAILABLE else '❌'}")
        st.write(f"Supabase Connected: {'✅' if supabase else '❌'}")
        st.write(f"API Token Configured: {'✅' if STAYFLEXI_API_TOKEN else '❌'}")
        st.write(f"API URL Configured: {'✅' if STAYFLEXI_API_BASE_URL else '❌'}")
        st.write(f"API Email Configured: {'✅' if STAYFLEXI_EMAIL else '❌'}")

    # Input for date selection and sync
    col1, col2 = st.columns([2, 1])
    with col1:
        sync_date = st.date_input("Select Date to Sync/View", value=date.today(), key="online_reservations_date")
    with col2:
        sync_button = st.button("Sync Stayflexi Bookings")

    if sync_date:
        formatted_date = sync_date.strftime("%Y-%m-%d")
        st.info(f"Selected date: {formatted_date}")

        # Fetch and sync bookings if button clicked
        if sync_button:
            if not REQUESTS_AVAILABLE or not SUPABASE_AVAILABLE or not STAYFLEXI_API_TOKEN or not STAYFLEXI_API_BASE_URL or not STAYFLEXI_EMAIL:
                st.error("Cannot sync bookings: Missing required libraries or API configuration")
            else:
                bookings = fetch_stayflexi_bookings(formatted_date)
                if bookings:
                    mapped_bookings = [map_stayflexi_to_supabase(booking) for booking in bookings]
                    mapped_bookings = [b for b in mapped_bookings if b]  # Filter out None
                    success_count = 0
                    for booking in mapped_bookings:
                        if save_to_supabase(booking):
                            success_count += 1
                    if success_count > 0:
                        st.success(f"Successfully synced {success_count} bookings to Supabase")
                    else:
                        st.warning("No new bookings synced")
                else:
                    st.warning("No bookings fetched from Stayflexi")

        # Load and display bookings from Supabase
        try:
            response = supabase.table("reservations").select("*").eq("mob", "Online").eq("check_in", formatted_date).execute()
            if response.data:
                df = pd.DataFrame([
                    {
                        "Booking ID": record["booking_id"],
                        "Property Name": record["property_name"],
                        "Guest Name": record["guest_name"],
                        "Guest Phone": record["guest_phone"],
                        "Check In": pd.to_datetime(record["check_in"]) if record["check_in"] else None,
                        "Check Out": pd.to_datetime(record["check_out"]) if record["check_out"] else None,
                        "Total Amount": record["total_amount"],
                        "Room Type": record["room_type"],
                        "Status": record["status"],
                        "Booking Source": record["booking_source"]
                    }
                    for record in response.data
                ])
            else:
                df = pd.DataFrame()
        except Exception as e:
            st.error(f"Error loading reservations: {str(e)}")
            df = pd.DataFrame()

        # Display bookings by property
        if not df.empty:
            properties = df["Property Name"].unique()
            tabs = st.tabs(properties)
            for i, property_name in enumerate(properties):
                with tabs[i]:
                    property_df = df[df["Property Name"] == property_name]
                    st.subheader(f"{property_name}")
                    status_tabs = st.tabs(["Check-ins", "New Bookings", "Cancelled", "On Hold", "No Show"])
                    with status_tabs[0]:
                        checkin_df = property_df[property_df["Status"] == "CONFIRMED"]
                        if not checkin_df.empty:
                            st.dataframe(checkin_df[["Booking ID", "Guest Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                        else:
                            st.write("No check-ins found.")
                    with status_tabs[1]:
                        new_df = property_df[property_df["Status"] == "NEW_BOOKINGS"]
                        if not new_df.empty:
                            st.dataframe(new_df[["Booking ID", "Guest Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                        else:
                            st.write("No new bookings found.")
                    with status_tabs[2]:
                        cancelled_df = property_df[property_df["Status"] == "CANCELLED"]
                        if not cancelled_df.empty:
                            st.dataframe(cancelled_df[["Booking ID", "Guest Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                        else:
                            st.write("No cancelled bookings found.")
                    with status_tabs[3]:
                        on_hold_df = property_df[property_df["Status"] == "ON_HOLD"]
                        if not on_hold_df.empty:
                            st.dataframe(on_hold_df[["Booking ID", "Guest Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                        else:
                            st.write("No on-hold bookings found.")
                    with status_tabs[4]:
                        no_show_df = property_df[property_df["Status"] == "NO_SHOW"]
                        if not no_show_df.empty:
                            st.dataframe(no_show_df[["Booking ID", "Guest Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                        else:
                            st.write("No no-show bookings found.")
        else:
            st.info("No online bookings found for the selected date.")

if __name__ == "__main__":
    show_online_reservations()
