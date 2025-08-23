import streamlit as st
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

# Initialize Supabase client with secrets
try:
    supabase: Client = create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
except KeyError as e:
    st.error(f"Missing Supabase secret: {e}. Please check Streamlit Cloud secrets configuration.")
    st.stop()

def check_authentication():
    """Handle user authentication and initialize session state."""
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
                try:
                    st.session_state.reservations = load_reservations_from_supabase()
                    if st.session_state.reservations:
                        st.success("✅ Management login successful! Reservations fetched.")
                    else:
                        st.warning("✅ Management login successful! No reservations found.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error fetching reservations: {e}")
                    st.stop()
            elif role == "ReservationTeam" and password == "TIE123":
                st.session_state.authenticated = True
                st.session_state.role = "ReservationTeam"
                st.session_state.reservations = []
                st.session_state.edit_mode = False
                st.session_state.edit_index = None
                # Fetch reservations using load_reservations_from_supabase
                try:
                    st.session_state.reservations = load_reservations_from_supabase()
                    if st.session_state.reservations:
                        st.success("✅ Agent login successful! Reservations fetched.")
                    else:
                        st.warning("✅ Agent login successful! No reservations found.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error fetching reservations: {e}")
                    st.stop()
            else:
                st.error("❌ Invalid password. Please try again.")
        st.stop()

def main():
    """Main application logic with error handling."""
    try:
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
    except Exception as e:
        st.error(f"Application Error: {str(e)}. Please check the code or Supabase connection.")

if __name__ == "__main__":
    main()
