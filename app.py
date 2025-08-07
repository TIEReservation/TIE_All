import streamlit as st
from directreservation import show_new_reservation_form, show_reservations, show_edit_reservations, show_analytics

# Page config
st.set_page_config(
 page_title="TIE Direct Reservations",
 page_icon="https://github.com/TIEReservation/TIEReservation-System/raw/main/TIE_Logo_Icon.png",
 layout="wide"
)

# Display logo in top-left corner
st.image("https://github.com/TIEReservation/TIEReservation-System/raw/main/TIE_Logo_Icon.png", width=100)

def check_authentication():
 if 'authenticated' not in st.session_state:
	 st.session_state.authenticated = False
	 st.session_state.role = None
 if not st.session_state.authenticated:
	 st.title("🔐 TIE Direct Reservations Login")
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
			 st.success("✅ Management login successful! Redirecting...")
			 st.rerun()
		 elif role == "ReservationTeam" and password == "TIE123":
			 st.session_state.authenticated = True
			 st.session_state.role = "ReservationTeam"
			 st.session_state.reservations = []
			 st.session_state.edit_mode = False
			 st.session_state.edit_index = None
			 st.success("✅ Agent login successful! Redirecting...")
			 st.rerun()
		 else:
			 st.error("❌ Invalid password. Please try again.")
	 st.stop()

def main():
 check_authentication()
 st.title("🏢 TIE Direct Reservations")
 st.markdown("---")
 st.sidebar.title("Navigation")
 page_options = ["Direct Reservations", "View Reservations", "Edit Reservations"]
 if st.session_state.role == "Management":
	 page_options.append("Analytics")
 page = st.sidebar.selectbox("Choose a page", page_options)

 if page == "Direct Reservations":
	 show_new_reservation_form()
 elif page == "View Reservations":
	 show_reservations()
 elif page == "Edit Reservations":
	 show_edit_reservations()
 elif page == "Analytics" and st.session_state.role == "Management":
	 show_analytics()

if __name__ == "__main__":
 main()
