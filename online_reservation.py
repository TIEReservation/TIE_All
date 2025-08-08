import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from config import STAYFLEXI_API_TOKEN, STAYFLEXI_API_BASE_URL, STAYFLEXI_EMAIL, SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_stayflexi_hotels():
    """Fetch list of hotels from Stayflexi."""
    url = f"{STAYFLEXI_API_BASE_URL}/common/hotel-detail?isGroupProperty=true&emailId={STAYFLEXI_EMAIL}"
    headers = {
        "Authorization": f"Bearer {STAYFLEXI_API_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        hotels = response.json()
        return [(hotel["hotelId"], hotel["name"]) for hotel in hotels if hotel["status"] == "active"]
    except requests.RequestException as e:
        st.error(f"Error fetching hotels: {e}")
        return []

def fetch_stayflexi_bookings(hotel_id, start_date, end_date):
    """Fetch bookings for a specific hotel from Stayflexi."""
    url = f"{STAYFLEXI_API_BASE_URL}/core/api/v1/reservation/navigationGetRoomBookings?hotel_id={hotel_id}&hotelId={hotel_id}"
    headers = {
        "Authorization": f"Bearer {STAYFLEXI_API_TOKEN}",
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://app.stayflexi.com",
        "Referer": "https://app.stayflexi.com/",
        "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36"
    }
    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "hotelId": str(hotel_id)
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        bookings = data.get("allRoomReservations", {}).get("singleRoomReservations", [])
        return bookings
    except requests.RequestException as e:
        st.error(f"Error fetching bookings for hotel {hotel_id}: {e}")
        return []

def map_stayflexi_to_supabase(booking, hotel_id, hotel_name):
    """Map Stayflexi booking to Supabase reservation format."""
    return {
        "reservation_id": booking.get("reservationId"),
        "hotel_id": hotel_id,
        "hotel_name": hotel_name,
        "room_id": booking.get("roomId"),
        "room_type": booking.get("roomTypeName", ""),
        "guest_name": booking.get("username"),
        "guest_email": booking.get("userEmail"),
        "guest_contact": booking.get("userContact"),
        "check_in": booking.get("checkin"),
        "check_out": booking.get("checkout"),
        "room_price": booking.get("roomPrice"),
        "booking_source": booking.get("bookingSource", "Unknown"),
        "reservation_status": booking.get("reservationStatus"),
        "mob": "Online",  # Mark as online reservation
        "created_at": datetime.now().isoformat(),
        "group_booking": booking.get("groupBooking", False),
        "balance_due": booking.get("balanceDue", 0.0)
    }

def save_to_supabase(reservations):
    """Save reservations to Supabase."""
    try:
        response = supabase.table("reservations").upsert(reservations, on_conflict=["reservation_id"]).execute()
        return response.data
    except Exception as e:
        st.error(f"Error saving to Supabase: {e}")
        return []

def show_online_reservations():
    """Display online reservations in Streamlit."""
    st.header("Online Reservations")
    hotels = fetch_stayflexi_hotels()
    if not hotels:
        st.warning("No hotels found or error fetching hotels.")
        return

    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=datetime.now())
    with col2:
        end_date = st.date_input("End Date", value=datetime.now())

    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    all_reservations = []
    for hotel_id, hotel_name in hotels:
        st.subheader(f"Reservations for {hotel_name} (ID: {hotel_id})")
        bookings = fetch_stayflexi_bookings(hotel_id, start_date_str, end_date_str)
        if bookings:
            hotel_reservations = []
            for room in bookings:
                for res in room.get("resInfoList", []):
                    if res.get("reservationStatus") == "CONFIRMED":  # Exclude BLOCKED
                        mapped_res = map_stayflexi_to_supabase(res, hotel_id, hotel_name)
                        hotel_reservations.append(mapped_res)
            if hotel_reservations:
                # Save to Supabase
                saved_res = save_to_supabase(hotel_reservations)
                all_reservations.extend(saved_res)
                # Display in table
                df = pd.DataFrame(hotel_reservations)
                st.dataframe(df[["reservation_id", "guest_name", "check_in", "check_out", "room_price", "booking_source"]])
            else:
                st.info(f"No confirmed reservations for {hotel_name}.")
        else:
            st.info(f"No bookings found for {hotel_name}.")

    # Display all reservations across properties
    if all_reservations:
        st.subheader("All Online Reservations")
        df_all = pd.DataFrame(all_reservations)
        st.dataframe(df_all[["hotel_name", "reservation_id", "guest_name", "check_in", "check_out", "room_price", "booking_source"]])

if __name__ == "__main__":
    show_online_reservations()
