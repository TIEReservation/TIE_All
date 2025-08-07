```python
from datetime import datetime
import streamlit as st
import requests

def safe_int(value, default=0):
    """Convert value to integer with a default if invalid."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    """Convert value to float with a default if invalid."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default

def calculate_days(check_in, check_out):
    """Calculate number of days between check-in and check-out."""
    if check_in and check_out and check_out > check_in:
        delta = check_out - check_in
        return delta.days
    return 0

def generate_booking_id(supabase, table_name="reservations"):
    """Generate a unique booking ID for the specified table."""
    try:
        today = datetime.now().strftime('%Y%m%d')
        prefix = "SFX" if table_name == "online_reservations" else "TIE"
        response = supabase.table(table_name).select("booking_id").like("booking_id", f"{prefix}{today}%").execute()
        existing_ids = [record["booking_id"] for record in response.data]
        sequence = 1
        while f"{prefix}{today}{sequence:03d}" in existing_ids:
            sequence += 1
        return f"{prefix}{today}{sequence:03d}"
    except Exception as e:
        st.error(f"Error generating booking ID: {e}")
        return None

def check_duplicate_guest(supabase, table_name, guest_name, guest_phone, room_no, exclude_booking_id=None):
    """Check for duplicate guest in the specified table."""
    try:
        response = supabase.table(table_name).select("*").execute()
        for reservation in response.data:
            if exclude_booking_id and reservation["booking_id"] == exclude_booking_id:
                continue
            if (reservation["guest_name"].lower() == guest_name.lower() and
                reservation.get("guest_phone") == guest_phone and
                reservation["room_no"] == room_no):
                return True, reservation["booking_id"]
        return False, None
    except Exception as e:
        st.error(f"Error checking duplicate guest: {e}")
        return False, None

def get_property_name(hotel_id):
    """Map Stayflexi hotelId to property_name."""
    property_mapping = {
        "27704": "La Antilia Luxury",
        "27706": "La Paradise Luxury",
        "27707": "La Paradise Residency",
        "27709": "La Tamara Luxury",
        "27710": "La Tamara Suite",
        "27711": "La Villa Heritage",
        "27719": "Le Poshe Beach View",
        "27720": "Le Poshe Luxury",
        "27721": "Le Poshe Suite",
        "27722": "Le Royce Villa",
        "27723": "Le Pondy Beachside",
        "27724": "Villa Shakti",
        "30357": "Eden Beach Resort",
        "31550": "La Millionaire Luxury Resort",
        "32470": "Le Park Resort"
    }
    return property_mapping.get(hotel_id, "Unknown Property")
```
