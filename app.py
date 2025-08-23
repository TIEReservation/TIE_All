import streamlit as st
from directreservation import show_new_reservation_form, show_reservations, show_edit_reservations, show_analytics, load_reservations_from_supabase
from supabase import create_client, Client
import pandas as pd

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "role" not in st.session_state:
    st.session_state.role = None
if "reservations" not in st.session_state:
    st.session_state.reservations = []
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False
if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

# Initialize Supabase client
try:
    supabase: Client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
except KeyError as e:
    st.error(f"Missing Supabase secret: {e}. Please check Streamlit Cloud secrets configuration.")
    st.stop()

def check_authentication():
    """Handle user authentication with role-based access."""
    try:
        if not st.session_state.authenticated:
            st.header("🔒 Login")
            role = st.selectbox("Select Role", ["ReservationTeam", "Management"])
            password = st.text_input("Password", type="password")
            if st.button("Login"):
                # Simple password check for demo purposes
                if (role == "ReservationTeam" and password == "TIE123") or \
                   (role == "Management" and password == "TIE2024"):
                    st.session_state.authenticated = True
                    st.session_state.role = role
                    st.session_state.reservations = load_reservations_from_supabase()
                    st.success(f"Logged in as {role}")
                    st.rerun()
                else:
                    st.error("Invalid password")
            st.stop()
    except Exception as e:
        st.error(f"Authentication error: {e}")
        st.stop()

def main():
    """Main application logic with simplified page navigation."""
    try:
        check_authentication()
        
        # Simplified page options without property selection
        page_options = ["Direct Reservations", "View Reservations", "Edit Reservations", "Analytics"]
        page = st.sidebar.selectbox("Select Page", page_options, key="page_select")
        
        # Render pages based on selection
        if page == "Direct Reservations":
            show_new_reservation_form()
        elif page == "View Reservations":
            show_reservations()
        elif page == "Edit Reservations":
            show_edit_reservations()
        elif page == "Analytics":
            show_analytics()
            
    except Exception as e:
        st.error(f"Error rendering page: {e}")

if __name__ == "__main__":
    try:
        st.set_page_config(page_title="TIE Reservation System", page_icon="🏨", layout="wide")
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
