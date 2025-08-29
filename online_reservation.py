import streamlit as st
from supabase import create_client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup
from config import SUPABASE_URL, SUPABASE_KEY
from utils import safe_int, safe_float, calculate_days, check_duplicate_guest, get_property_name
from Daily_DMS_All import PROPERTIES, setup_driver, fetch_and_display_bookings, extract_booking_data_from_text, match_patterns_on_page

# OTA sources to filter (common ones; adjust based on Stayflexi)
OTA_SOURCES = ['Booking.com', 'Expedia', 'Agoda', 'Goibibo', 'MakeMyTrip', 'Stayflexi OTA']  # Add more if needed

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Hard-coded chrome profile path (from app.py; make env var in production)
CHROME_PROFILE_PATH = r"C:\Users\somas\AppData\Local\Google\Chrome\User Data\Default"  # Adjust as needed

def is_ota_booking(booking):
    """Check if booking is from OTA."""
    source = booking.get('booking_source', '').lower()
    return any(ota.lower() in source for ota in OTA_SOURCES)

def login_to_stayflexi(chrome_profile_path, property_name, hotel_id):
    """Login to Stayflexi and navigate to reservations (adapted for OTA focus)."""
    driver = setup_driver(chrome_profile_path)
    wait = WebDriverWait(driver, 20)
    bookings = []
    
    try:
        st.write(f"🔹 Opening StayFlexi for {property_name}...")
        driver.get("https://app.stayflexi.com/auth/login")
        
        # Login logic (reuse from Daily_DMS_All.py)
        try:
            email_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
            email_field.clear()
            email_field.send_keys("gayathri.tie@gmail.com")
            
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]")))
            login_button.click()
            
            password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
            password_field.send_keys("Alliswell@2025")
            
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]")))
            login_button.click()
            st.write("✅ Logged in successfully")
            time.sleep(5)
        except:
            st.write("🔹 Already logged in.")
        
        # Navigate to dashboard
        dashboard_button = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[@href='/dashboard?hotelId={hotel_id}']")))
        dashboard_button.click()
        time.sleep(3)
        driver.switch_to.window(driver.window_handles[-1])
        
        # Navigate to reservations
        reservations_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Reservations')]")))
        reservations_button.click()
        
        # Fetch bookings (reuse and filter for OTA)
        all_bookings = fetch_and_display_bookings(driver, wait, hotel_id)
        bookings = [b for b in all_bookings if is_ota_booking(b)]
        st.write(f"📋 Fetched {len(bookings)} OTA bookings for {property_name}")
        
    except Exception as e:
        st.error(f"❌ Error for {property_name}: {str(e)}")
    finally:
        driver.quit()
        return bookings

def store_in_supabase(bookings, property_name):
    """Store OTA bookings in Supabase 'otabooking' table."""
    for booking in bookings:
        is_duplicate, existing_id = check_duplicate_guest(supabase, "otabooking", booking.get('guest_name', ''), booking.get('guest_phone', ''), booking.get('room_number', ''))
        if is_duplicate:
            st.warning(f"ℹ️ Duplicate booking {booking.get('booking_id')} (exists as {existing_id})")
            continue
        
        data = {
            "property": property_name,
            "report_date": datetime.now().date().isoformat(),
            "booking_date": booking.get('booking_date'),  # Assume date object or str
            "booking_id": booking.get('booking_id'),
            "booking_source": booking.get('booking_source'),
            "guest_name": booking.get('name'),
            "guest_phone": booking.get('guest_phone'),
            "check_in": booking.get('check_in'),
            "check_out": booking.get('check_out'),
            "total_with_taxes": safe_float(booking.get('total_with_taxes')),
            "payment_made": safe_float(booking.get('payment_made')),
            "adults_children_infant": booking.get('adults_children_infant'),
            "room_number": booking.get('room_number'),
            "total_without_taxes": safe_float(booking.get('total_without_taxes')),
            "total_tax_amount": safe_float(booking.get('total_tax_amount')),
            "room_type": booking.get('room_type'),
            "rate_plan": booking.get('rate_plan'),
            "created_at": datetime.now().isoformat()
        }
        
        try:
            supabase.table("otabooking").insert(data).execute()
            st.success(f"✅ Stored booking {booking.get('booking_id')} for {property_name}")
        except Exception as e:
            st.error(f"❌ Error storing booking: {str(e)}")

def fetch_for_property(property_name, hotel_id):
    """Fetch OTA bookings for a single property."""
    bookings = login_to_stayflexi(CHROME_PROFILE_PATH, property_name, hotel_id)
    store_in_supabase(bookings, property_name)

def show_online_reservations():
    """Streamlit UI for online reservations."""
    st.title("📡 Online Reservations (OTA Bookings)")
    st.markdown("Sync bookings from Stayflexi for each property.")

    # Sync All button
    if st.button("🔄 Sync All Properties", key="sync_all"):
        with st.spinner("Syncing all properties..."):
            progress_bar = st.progress(0)
            total = len(PROPERTIES)
            for i, (name, id) in enumerate(PROPERTIES.items()):
                fetch_for_property(name, id)
                progress_bar.progress((i + 1) / total)
            st.success("✅ All properties synced!")

    # Property list with individual sync buttons
    for name, id in PROPERTIES.items():
        col1, col2 = st.columns([4, 1])
        col1.write(f"🏨 {name} (ID: {id})")
        if col2.button(f"🔄 Sync {name}", key=f"sync_{name}"):
            with st.spinner(f"Syncing {name}..."):
                fetch_for_property(name, id)
