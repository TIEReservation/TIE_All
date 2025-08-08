import streamlit as st
import os
from supabase import create_client, Client
from directreservation import show_new_reservation_form, show_reservations, show_edit_reservations, show_analytics, load_reservations_from_supabase
from online_reservation import show_online_reservations

# Page config
st.set_page_config(
    page_title="TIE Reservations",
    page_icon="https://github.com/TIEReservation/TIEReservation-System/raw/main/TIE_Logo_Icon.png",
    layout="wide"
)

# Display logo in top-left corner
st.image("https://github.com/TIEReservation/TIEReservation-System/raw/main/TIE_Logo_Icon.png", width=100)

# Initialize Supabase client with environment variables
os.environ["SUPABASE_URL"] = "https://oxbrezracnmazucnnqox.supabase.co"
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im94YnJlenJhY25tYXp1Y25ucW94Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM3NjUxMTgsImV4cCI6MjA2OTM0MTExOH0.nqBK2ZxntesLY9qYClpoFPVnXOW10KrzF-UI_DKjbKo"
supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

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
                # Fetch reservations using load_reservations_from_supabase
                st.session_state.reservations = load_reservations_from_supabase()
                if st.session_state.reservations:
                    st.success("✅ Management login successful! Reservations fetched.")
                else:
                    st.warning("✅ Management login successful! No reservations found.")
                st.rerun()
            elif role == "ReservationTeam" and password == "TIE123":
                st.session_state.authenticated = True
                st.session_state.role = "ReservationTeam"
                st.session_state.reservations = []
                st.session_state.edit_mode = False
                st.session_state.edit_index = None
                # Fetch reservations using load_reservations_from_supabase
                st.session_state.reservations = load_reservations_from_supabase()
                if st.session_state.reservations:
                    st.success("✅ Agent login successful! Reservations fetched.")
                else:
                    st.warning("✅ Agent login successful! No reservations found.")
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

    # Logout button
    if st.sidebar.button("Log Out"):
        st.session_state.authenticated = False
        st.session_state.role = None
        st.session_state.reservations = []
        st.session_state.edit_mode = False
        st.session_state.edit_index = None
        st.rerun()

if __name__ == "__main__":
    main() 
