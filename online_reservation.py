from datetime import datetime
import streamlit as st
import requests
import logging

# Set up logging for debugging in Streamlit Cloud
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_int(value, default=0):
    """Convert value to integer with a default if invalid."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError) as e:
        logger.error(f"safe_int error: {e}, value: {value}")
        return default

def safe_float(value, default=0.0):
    """Convert value to float with a default if invalid."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError) as e:
        logger.error(f"safe_float error: {e}, value: {value}")
        return default

def calculate_days(check_in, check_out):
    """Calculate number of days between check-in and check-out."""
    try:
        if check_in and check_out and check_out > check_in:
            delta = check_out - check_in
            return delta.days
        return 0
    except Exception as e:
        logger.error(f"calculate_days error: {e}, check_in: {check_in}, check_out: {check_out}")
        return 0

def generate_booking_id(supabase, table_name="reservations"):
    """Generate a unique booking ID for the specified table (e.g., 'reservations' for direct, 'otabooking' for OTA)."""
    try:
        today = datetime.now().strftime('%Y%m%d')
        prefix = "SFX" if table_name == "otabooking" else "TIE"
        response = supabase.table(table_name).select("booking_id").like("booking_id", f"{prefix}{today}%").execute()
        existing_ids = [record["booking_id"] for record in response.data]
        sequence = 1
        while f"{prefix}{today}{sequence:03d}" in existing_ids:
            sequence += 1
        booking_id = f"{prefix}{today}{sequence:03d}"
        logger.info(f"Generated booking ID: {booking_id} for table: {table_name}")
        return booking_id
    except Exception as e:
        st.error(f"Error generating booking ID for {table_name}: {e}")
        logger.error(f"generate_booking_id error: {e}, table: {table_name}")
        return None

def check_duplicate_guest(supabase, table_name, guest_name, guest_phone, room_no, exclude_booking_id=None):
    """Check for duplicate guest in the specified table (e.g., 'reservations' for direct, 'otabooking' for OTA)."""
    try:
        response = supabase.table(table_name).select("*").execute()
        for reservation in response.data:
            if exclude_booking_id and reservation["booking_id"] == exclude_booking_id:
                continue
            if (reservation["guest_name"].lower() == guest_name.lower() and
                reservation.get("guest_phone") == guest_phone and
                reservation.get("room_no") == room_no):
                logger.info(f"Duplicate guest found in {table_name}: {guest_name}, {guest_phone}, {room_no}")
                return True, reservation["booking_id"]
        return False, None
    except Exception as e:
        st.error(f"Error checking duplicate guest in {table_name}: {e}")
        logger.error(f"check_duplicate_guest error: {e}, table: {table_name}, guest: {guest_name}")
        return False, None

def get_property_name(hotel_id):
    """Map Stayflexi hotelId to property_name, consistent with online_reservation.py."""
    property_mapping = {
        "27704": "La Antilia Luxury",
        "27706": "La Paradise Luxury",
        "27707": "La Paradise Residency",
        "27709": "La Tamara Luxury",
        "27710": "La Tamara suite",
        "27711": "La Villa Heritage",
        "27719": "Le Poshe Beach View",
        "27720": "Le Poshe Luxury",
        "27721": "Le Poshe Suite",
        "27722": "Le Royce Villa",
        "27723": "Le Pondy Beachside",
        "27724": "Villa Shakti",
        "30357": "EdenBeachResort",
        "31550": "La Millionaire Resort",
        "32470": "Le Park Resort"
    }
    property_name = property_mapping.get(hotel_id, "Unknown Property")
    logger.info(f"Mapped hotel_id {hotel_id} to {property_name}")
    return property_name
