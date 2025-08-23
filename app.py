import streamlit as st
from supabase import create_client, Client
from directreservation import (
    show_new_reservation_form,
    show_reservations,
    show_edit_reservations,
    show_analytics,
    load_reservations_from_supabase,
)
from online_reservation import show_online_reservations

# ---------------- NEW: Property and Room Mapping ----------------
properties = {
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
        "Villa": ["101to102&201to202", "101", "102", "202"]
    },
    "La Tamara Luxury": {
        "3BHA": [
            "101to103", "101", "102", "103", "104to106", "104", "105", "106",
            "201to203", "201", "202", "203", "204to206", "204", "205", "206",
            "301to303", "301", "302", "303", "304to306", "304", "305", "306"
        ],
        "4BHA": ["401to404", "404", "402", "403", "404"]
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
        "Villa with Gardern View": ["111&222", "111", "222"],
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
# -----------------------------------------------------------------

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
            # ----------- NEW DROPDOWNS -----------
            st.subheader("Select Property and Room")
            property_selected = st.selectbox("Select Property", list(properties.keys()))
            room_types = list(properties[property_selected].keys())
            room_type_selected = st.selectbox("Select Room Type", room_types)
            room_numbers = properties[property_selected][room_type_selected]
            room_number_selected = st.selectbox("Select Room Number", room_numbers)
            # Pass these values to your form or database logic if needed
            # -------------------------------------

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
    except Exception as e:
        st.error(f"Application Error: {str(e)}. Please check the code or Supabase connection.")

if __name__ == "__main__":
    main()
