import streamlit as st
from supabase import create_client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup
import os
from config import SUPABASE_URL, SUPABASE_KEY
from utils import safe_int, safe_float, check_duplicate_guest, get_property_name

# Dictionary of properties and their hotel IDs
PROPERTIES = {
    "EdenBeachResort": "30357",
    "Villa Shakti": "27724",
    "Le Pondy Beachside": "27723",
    "Le Royce Villa": "27722",
    "Le Poshe Suite": "27721",
    "Le Poshe Luxury": "27720",
    "Le Poshe Beach View": "27719",
    "La Villa Heritage": "27711",
    "La Tamara suite": "27710",
    "La Tamara Luxury": "27709",
    "La Paradise Residency": "27707",
    "La Paradise Luxury": "27706",
    "La Antilia Luxury": "27704",
    "La Millionaire Resort": "31550",
    "Le Park Resort": "32470"
}

# OTA sources to filter
OTA_SOURCES = ['Booking.com', 'Expedia', 'Agoda', 'Goibibo', 'MakeMyTrip', 'Stayflexi OTA']

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Chrome profile path for cloud compatibility
CHROME_PROFILE_PATH = os.getenv("CHROME_PROFILE_PATH", "/tmp/chrome_profile")

def setup_driver(chrome_profile_path):
    """Set up Chrome WebDriver with the specified user profile."""
    os.makedirs(chrome_profile_path, exist_ok=True)
    chrome_options = Options()
    chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
    chrome_options.add_argument("profile-directory=Profile 20")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--headless")  # Run headless for cloud
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(service=webdriver.Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

def match_patterns_on_page(page_source):
    """Extract specific fields from page source using regex patterns."""
    patterns = {
        'booking_id': r'Booking ID.*?[:\s]*([A-Z0-9-]+)',
        'name': r'Guest Name.*?[:\s]*(.*?)(?=\n|$)',
        'guest_phone': r'Contact Number.*?[:\s]*(.*?)(?=\n|$)',
        'check_in': r'Check-in.*?[:\s]*(\d{4}-\d{2}-\d{2})',
        'check_out': r'Check-out.*?[:\s]*(\d{4}-\d{2}-\d{2})',
        'total_with_taxes': r'Total with Taxes.*?[:\s]*₹?\s*([\d,]+\.?\d*)',
        'payment_made': r'Payment Made.*?[:\s]*₹?\s*([\d,]+\.?\d*)',
        'adults_children_infant': r'Adults/Children/Infant.*?[:\s]*(.*?)(?=\n|$)',
        'room_number': r'Room Number.*?[:\s]*(.*?)(?=\n|$)',
        'total_without_taxes': r'Total without Taxes.*?[:\s]*₹?\s*([\d,]+\.?\d*)',
        'total_tax_amount': r'Total Tax Amount.*?[:\s]*₹?\s*([\d,]+\.?\d*)',
        'room_type': r'Room Type.*?[:\s]*(.*?)(?=\n|$)',
        'rate_plan': r'Rate Plan.*?[:\s]*(.*?)(?=\n|$)',
        'booking_source': r'Booking Source.*?[:\s]*(.*?)(?=\n|$)',
        'booking_date': r'Booking Date.*?[:\s]*(\d{4}-\d{2}-\d{2})'
    }
    extracted_data = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, page_source, re.IGNORECASE | re.DOTALL)
        extracted_data[key] = match.group(1).strip() if match else ''
    return extracted_data

def extract_booking_data_from_text(text):
    """Extract booking data from text using regex."""
    booking_data = match_patterns_on_page(text)
    return booking_data

def fetch_and_display_bookings(driver, wait, hotel_id):
    """Fetch and display all booking information entries."""
    st.write("🔹 Fetching all booking information entries...")
    bookings = []

    time.sleep(8)

    try:
        booking_cards = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiCollapse-root.MuiCollapse-vertical.MuiCollapse-hidden")))
        st.write(f"📋 Found {len(booking_cards)} booking entries using MuiCollapse-hidden")
    except Exception as e:
        st.write(f"⚠️ Could not find booking entries with MuiCollapse-hidden: {str(e)}")
        try:
            booking_cards = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiAccordionSummary-content.Mui-expanded.MuiAccordionSummary-contentGutters")))
            st.write(f"📋 Found {len(booking_cards)} booking entries using MuiAccordionSummary-expanded")
        except Exception as e:
            st.write(f"⚠️ Could not find booking entries with MuiAccordionSummary-expanded: {str(e)}")
            booking_cards = []

    for i, card in enumerate(booking_cards):
        st.write(f"\n🔖 Booking #{i+1}:")
        try:
            card.click()
            time.sleep(2)
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            booking_text = soup.get_text(separator='\n', strip=True)
            booking_data = extract_booking_data_from_text(booking_text)
            if booking_data.get('booking_id'):
                bookings.append(booking_data)
                st.write(f"📋 Extracted booking: {booking_data.get('booking_id')}")
            else:
                st.write("⚠️ No booking ID found, skipping...")
        except Exception as e:
            st.write(f"⚠️ Error extracting booking #{i+1}: {str(e)}")
    
    return bookings

def is_ota_booking(booking):
    """Check if booking is from OTA."""
    source = booking.get('booking_source', '').lower()
    return any(ota.lower() in source for ota in OTA_SOURCES)

def login_to_stayflexi(chrome_profile_path, property_name, hotel_id):
    """Login to Stayflexi and navigate to reservations."""
    driver = setup_driver(chrome_profile_path)
    wait = WebDriverWait(driver, 20)
    bookings = []
    
    try:
        st.write(f"🔹 Opening StayFlexi for {property_name}...")
        driver.get("https://app.stayflexi.com/auth/login")
        
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
        
        dashboard_button = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[@href='/dashboard?hotelId={hotel_id}']")))
        dashboard_button.click()
        time.sleep(3)
        driver.switch_to.window(driver.window_handles[-1])
        
        reservations_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Reservations')]")))
        reservations_button.click()
        
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
        is_duplicate, existing_id = check_duplicate_guest(supabase, "otabooking", 
                                                        booking.get('guest_name', ''), 
                                                        booking.get('guest_phone', ''), 
                                                        booking.get('room_number', ''))
        if is_duplicate:
            st.warning(f"ℹ️ Duplicate booking {booking.get('booking_id')} (exists as {existing_id})")
            continue
        
        data = {
            "property": property_name,
            "report_date": datetime.now().date().isoformat(),
            "booking_date": booking.get('booking_date'),
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

    if st.button("🔄 Sync All Properties", key="sync_all"):
        with st.spinner("Syncing all properties..."):
            progress_bar = st.progress(0)
            total = len(PROPERTIES)
            for i, (name, id) in enumerate(PROPERTIES.items()):
                fetch_for_property(name, id)
                progress_bar.progress((i + 1) / total)
            st.success("✅ All properties synced!")

    for name, id in PROPERTIES.items():
        col1, col2 = st.columns([4, 1])
        col1.write(f"🏨 {name} (ID: {id})")
        if col2.button(f"🔄 Sync {name}", key=f"sync_{name}"):
            with st.spinner(f"Syncing {name}..."):
                fetch_for_property(name, id)
