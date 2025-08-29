import streamlit as st
import os
from supabase import create_client, Client
try:
    from directreservation import show_new_reservation_form, show_reservations, show_edit_reservations, show_analytics, load_reservations_from_supabase
    from online_reservation import show_online_reservations
except ImportError as e:
    st.error(f"❌ Import error: {e}. Please ensure directreservation.py and online_reservation.py are in the repository.")
    st.stop()

# Page config
st.set_page_config(
    page_title="TIE Reservations",
    page_icon="https://github.com/TIEReservation/TIEReservation-System/raw/main/TIE_Logo_Icon.png",
    layout="wide"
)

# Display logo in top-left corner
st.image("https://github.com/TIEReservation/TIEReservation-System/raw/main/TIE_Logo_Icon.png", width=100)

# Initialize Supabase client with environment variables or secrets
SUPABASE_URL = st.secrets.get("supabase", {}).get("url") or os.environ.get("SUPABASE_URL", "https://oxbrezracnmazucnnqox.supabase.co")
SUPABASE_KEY = st.secrets.get("supabase", {}).get("key") or os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im94YnJlenJhY25tYXp1Y25ucW94Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM3NjUxMTgsImV4cCI6MjA2OTM0MTExOH0.nqBK2ZxntesLY9qYClpoFPVnXOW10KrzF-UI_DKjbKo")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_authentication():
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.role = None
    if not st.session_state.authenticated:
        st.title("🔐 TIE Reservations Login")
        st.write("Please select your role and enter the password to access the system.")
        role = st.selectbox("Select Role", ["Management", "ReservationTeam"])
        password = st.text_input("Enter password:", type="password")
        if st.button("🔑 Login"):
            if role == "Management" and password == "TIE2024":
                st.session_state.authenticated = True
                st.session_state.role = "Management"
                st.session_state.reservations = []
                st.session_state.edit_mode = False
                st.session_state.edit_index = None
                try:
                    st.session_state.reservations = load_reservations_from_supabase()
                    if st.session_state.reservations:
                        st.success("✅ Management login successful! Reservations fetched.")
                    else:
                        st.warning("✅ Management login successful! No reservations found.")
                except Exception as e:
                    st.error(f"❌ Error fetching reservations: {e}")
                st.rerun()
            elif role == "ReservationTeam" and password == "TIE123":
                st.session_state.authenticated = True
                st.session_state.role = "ReservationTeam"
                st.session_state.reservations = []
                st.session_state.edit_mode = False
                st.session_state.edit_index = None
                try:
                    st.session_state.reservations = load_reservations_from_supabase()
                    if st.session_state.reservations:
                        st.success("✅ Agent login successful! Reservations fetched.")
                    else:
                        st.warning("✅ Agent login successful! No reservations found.")
                except Exception as e:
                    st.error(f"❌ Error fetching reservations: {e}")
                st.rerun()
            else:
                st.error("❌ Invalid password. Please try again.")
        st.stop()

def main():
    check_authentication()
    st.title("🏢 TIE Reservations")
    st.markdown("---")
    st.sidebar.title("Navigation")
    page_options = ["Direct Reservations", "View Reservations", "Edit Reservations", "Online Reservations"]
    if st.session_state.role == "Management":
        page_options.append("Analytics")
    page = st.sidebar.selectbox("Choose a page", page_options)

    if page == "Direct Reservations":
        show_new_reservation_form()
    elif page == "View Reservations":
        show_reservations()
    elif page == "Edit Reservations":
        show_edit_reservations()
    elif page == "Online Reservations":
        show_online_reservations()
    elif page == "Analytics" and st.session_state.role == "Management":
        show_analytics()

    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.role = None
        st.session_state.reservations = []
        st.session_state.edit_mode = False
        st.session_state.edit_index = None
        st.rerun()

if __name__ == "__main__":
    main()
