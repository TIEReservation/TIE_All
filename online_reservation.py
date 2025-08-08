import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date
from supabase import create_client, Client

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
    from config import STAYFLEXI_API_TOKEN, STAYFLEXI_API_BASE_URL
except ImportError:
    try:
        STAYFLEXI_API_TOKEN = st.secrets.get("stayflexi", {}).get("STAYFLEXI_API_TOKEN", "")
        STAYFLEXI_API_BASE_URL = st.secrets.get("stayflexi", {}).get("STAYFLEXI_API_BASE_URL", "")
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

def fetch_stayflexi_bookings(start_date: str, end_date: str = None):
    """
    Fetch bookings from Stayflexi API for the given date range.
    Args:
        start_date: YYYY-MM-DD format
        end_date: YYYY-MM-DD format (optional, defaults to start_date)
    Returns:
        List of bookings or None if failed
    """
    if not REQUESTS_AVAILABLE or not STAYFLEXI_API_TOKEN or not STAYFLEXI_API_BASE_URL:
        st.error("Cannot fetch bookings: Missing requests library or API configuration")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {STAYFLEXI_API_TOKEN}",
            "Content-Type": "application/json"
        }
        endpoint = f"{STAYFLEXI_API_BASE_URL}/bookings"
        params = {"date": start_date}
        if end_date:
            params["end_date"] = end_date

        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("data", [])
    except requests.RequestException as e:
        st.error(f"Failed to fetch Stayflexi bookings: {str(e)}")
        return None

def map_stayflexi_to_supabase(booking):
    """
    Map Stayflexi booking data to Supabase schema.
    Adjust field mappings based on actual Stayflexi API response.
    """
    try:
        return {
            "booking_id": booking.get("reservation_id", generate_booking_id()),
            "property_name": booking.get("hotel_name", ""),
            "booking_date": booking.get("booking_date", datetime.now().strftime("%Y-%m-%d")),
            "booking_source": booking.get("source", "Stayflexi"),
            "guest_name": booking.get("guest_name", ""),
            "guest_phone": booking.get("guest_phone", ""),
            "check_in": booking.get("check_in_date", ""),
            "check_out": booking.get("check_out_date", ""),
            "total_amount": float(booking.get("total_amount", 0.0)),
            "advance": float(booking.get("advance_paid", 0.0)),
            "no_of_adults": int(booking.get("adults", 0)),
            "no_of_children": int(booking.get("children", 0)),
            "no_of_infants": int(booking.get("infants", 0)),
            "total_pax": int(booking.get("adults", 0)) + int(booking.get("children", 0)) + int(booking.get("infants", 0)),
            "room_no": booking.get("room_number", ""),
            "amt_without_tax": float(booking.get("amount_excluding_tax", 0.0)),
            "tax": float(booking.get("tax_amount", 0.0)),
            "room_type": booking.get("room_type", ""),
            "breakfast": booking.get("meal_plan", "EP"),
            "status": booking.get("status", "Pending").upper(),
            "submitted_by": "Stayflexi API",
            "remarks": booking.get("notes", ""),
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

    # Input for date selection and sync
    col1, col2 = st.columns([2, 1])
    with col1:
        sync_date = st.date_input("Select Date to Sync/View", value=datetime.today(), key="online_reservations_date")
    with col2:
        sync_button = st.button("Sync Stayflexi Bookings")

    if sync_date:
        formatted_date = sync_date.strftime("%Y-%m-%d")
        st.info(f"Selected date: {formatted_date}")

        # Fetch and sync bookings if button clicked
        if sync_button:
            if not REQUESTS_AVAILABLE or not SUPABASE_AVAILABLE or not STAYFLEXI_API_TOKEN or not STAYFLEXI_API_BASE_URL:
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

        # Display sample data if no real data
        if df.empty and (not REQUESTS_AVAILABLE or not SUPABASE_AVAILABLE or not STAYFLEXI_API_TOKEN or not STAYFLEXI_API_BASE_URL):
            st.warning("Missing required libraries or API configuration. Showing sample data:")
            sample_data = {
                "Booking ID": ["RES001", "RES002", "RES003"],
                "Property Name": ["Eden Beach Resort", "La Paradise Luxury", "Le Poshe Suite"],
                "Guest Name": ["John Doe", "Jane Smith", "Bob Johnson"],
                "Guest Phone": ["+1234567890", "+0987654321", "+1122334455"],
                "Check In": [formatted_date, formatted_date, formatted_date],
                "Check Out": [(pd.to_datetime(formatted_date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), formatted_date, formatted_date],
                "Total Amount": [10000.0, 15000.0, 20000.0],
                "Room Type": ["Standard", "Deluxe", "Suite"],
                "Status": ["CHECKINS", "NEW_BOOKINGS", "CANCELLED"],
                "Booking Source": ["Booking.com", "Expedia", "Stayflexi"]
            }
            df = pd.DataFrame(sample_data)

        # Display bookings by status
        if not df.empty:
            tabs = st.tabs(["Check-ins", "New Bookings", "Cancelled"])
            with tabs[0]:
                checkin_df = df[df["Status"] == "CHECKINS"]
                if not checkin_df.empty:
                    st.dataframe(checkin_df[["Booking ID", "Guest Name", "Property Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                else:
                    st.write("No check-ins found.")
            with tabs[1]:
                new_df = df[df["Status"] == "NEW_BOOKINGS"]
                if not new_df.empty:
                    st.dataframe(new_df[["Booking ID", "Guest Name", "Property Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                else:
                    st.write("No new bookings found.")
            with tabs[2]:
                cancelled_df = df[df["Status"] == "CANCELLED"]
                if not cancelled_df.empty:
                    st.dataframe(cancelled_df[["Booking ID", "Guest Name", "Property Name", "Check In", "Check Out", "Room Type", "Total Amount", "Booking Source"]], use_container_width=True)
                else:
                    st.write("No cancelled bookings found.")
        else:
            st.info("No online bookings found for the selected date.")

if __name__ == "__main__":
    show_online_reservations()
