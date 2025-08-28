import streamlit as st
from directreservation import show_new_reservation_form, show_reservations, show_edit_reservations, show_analytics, load_reservations_from_supabase

def main():
    st.set_page_config(page_title="Direct Reservations", layout="wide")
    
    # Initialize session state
    if "reservations" not in st.session_state:
        st.session_state.reservations = load_reservations_from_supabase()
    if "role" not in st.session_state:
        st.session_state.role = "Staff"  # Default role

    # Sidebar navigation
    st.sidebar.title("🏨 Direct Reservations")
    page = st.sidebar.radio("Navigate", ["Direct Reservations", "Edit Reservations", "Analysis"])

    # Render selected page
    if page == "Direct Reservations":
        show_new_reservation_form()
    elif page == "Edit Reservations":
        show_reservations()
    elif page == "Analysis":
        show_analytics()

if __name__ == "__main__":
    main()
