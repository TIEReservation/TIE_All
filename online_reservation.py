import streamlit as st
import pandas as pd
from datetime import datetime

# Safe imports with error handling
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

# Safe Supabase initialization
supabase = None
if SUPABASE_AVAILABLE:
    try:
        supabase = create_client(
            st.secrets["supabase"]["url"], 
            st.secrets["supabase"]["key"]
        )
    except Exception as e:
        st.error(f"Failed to initialize Supabase: {str(e)}")

# Safe API configuration
STAYFLEXI_API_TOKEN = ""
STAYFLEXI_API_BASE_URL = ""

try:
    from config import STAYFLEXI_API_TOKEN, STAYFLEXI_API_BASE_URL
except ImportError:
    try:
        STAYFLEXI_API_TOKEN = st.secrets.get("STAYFLEXI_API_TOKEN", "")
        STAYFLEXI_API_BASE_URL = st.secrets.get("STAYFLEXI_API_BASE_URL", "")
    except Exception as e:
        st.warning(f"Could not load API configuration: {str(e)}")

def show_online_reservations():
    """
    Display online reservations with comprehensive error handling.
    """
    st.header("📡 Online Reservations")
    
    # Show system status
    with st.expander("System Status", expanded=False):
        st.write(f"Requests Available: {'✅' if REQUESTS_AVAILABLE else '❌'}")
        st.write(f"Supabase Available: {'✅' if SUPABASE_AVAILABLE else '❌'}")
        st.write(f"Supabase Connected: {'✅' if supabase else '❌'}")
        st.write(f"API Token Configured: {'✅' if STAYFLEXI_API_TOKEN else '❌'}")
        st.write(f"API URL Configured: {'✅' if STAYFLEXI_API_BASE_URL else '❌'}")
    
    # Basic functionality
    col1, col2 = st.columns([2, 1])
    with col1:
        date = st.date_input("Select Date", value=datetime.today(), key="online_reservations_date")
    with col2:
        is_today = st.checkbox("Show Today's Bookings", value=True, key="online_reservations_is_today")
    
    if date:
        formatted_date = date.strftime("%Y-%m-%d")
        st.info(f"Selected date: {formatted_date}")
        
        if not REQUESTS_AVAILABLE or not SUPABASE_AVAILABLE:
            st.warning("Missing required libraries. Showing sample data:")
            
            # Sample data
            sample_data = {
                "Reservation ID": ["RES001", "RES002", "RES003"],
                "Hotel ID": ["27704", "27706", "27707"],
                "Guest Name": ["John Doe", "Jane Smith", "Bob Johnson"],
                "Check In": [date, date, date],
                "Check Out": [date, date, date],
                "Room Type": ["Standard", "Deluxe", "Suite"],
                "Booking Source": ["Online", "Phone", "Walk-in"],
                "Status": ["CHECKINS", "NEW_BOOKINGS", "CANCELLED"]
            }
            
            df = pd.DataFrame(sample_data)
            
            # Display by status
            tabs = st.tabs(["Check-ins", "New Bookings", "Cancelled"])
            
            with tabs[0]:
                checkin_df = df[df["Status"] == "CHECKINS"]
                if not checkin_df.empty:
                    st.dataframe(checkin_df, use_container_width=True)
                else:
                    st.write("No check-ins found.")
            
            with tabs[1]:
                new_df = df[df["Status"] == "NEW_BOOKINGS"]
                if not new_df.empty:
                    st.dataframe(new_df, use_container_width=True)
                else:
                    st.write("No new bookings found.")
            
            with tabs[2]:
                cancelled_df = df[df["Status"] == "CANCELLED"]
                if not cancelled_df.empty:
                    st.dataframe(cancelled_df, use_container_width=True)
                else:
                    st.write("No cancelled bookings found.")
        else:
            st.success("All systems ready! Full functionality would be available here.")
            st.info("Replace this with the full implementation once basic setup is working.")

if __name__ == "__main__":
    show_online_reservations()
