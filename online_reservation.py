import streamlit as st
from supabase import create_client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
import chromedriver_autoinstaller
import os
import logging
import shutil
from datetime import datetime
import time
import re
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed
from config import SUPABASE_URL, SUPABASE_KEY
from utils import safe_int, safe_float, check_duplicate_guest, get_property_name

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Chrome profile and ChromeDriver paths
CHROME_PROFILE_PATH = os.getenv("CHROME_PROFILE_PATH", f"/tmp/chrome_profile_{int(time.time())}")
CHROMEDRIVER_PATH = "/tmp/chromedriver/chromedriver"

def setup_driver(chrome_profile_path):
    """Set up Chrome WebDriver with a fresh user profile."""
    try:
        # Clear previous Chrome profile to ensure fresh session
        if os.path.exists(chrome_profile_path):
            shutil.rmtree(chrome_profile_path, ignore_errors=True)
        os.makedirs(chrome_profile_path, exist_ok=True)
        os.makedirs(os.path.dirname(CHROMEDRIVER_PATH), exist_ok=True)
        
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
        chrome_options.add_argument("profile-directory=Profile 20")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--headless=new")  # Use new headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")  # Disable GPU for cloud
        chrome_options.add_argument("--window-size=1920,1080")  # Set window size
        chrome_options.binary_location = "/usr/bin/chromium"
        
        # Install ChromeDriver in a writable directory
        chromedriver_path = chromedriver_autoinstaller.install(path=os.path.dirname(CHROMEDRIVER_PATH))
        logger.info(f"ChromeDriver installed at: {chromedriver_path}")
        # Ensure ChromeDriver is executable
        os.chmod(chromedriver_path, 0o755)
        service = ChromeService(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Failed to set up Chrome WebDriver: {str(e)}")
        st.error(f"❌ Failed to initialize browser: {str(e)}")
        raise

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

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_and_display_bookings(driver, wait, hotel_id):
    """Fetch and display all booking information entries with retries."""
    st.write("🔹 Fetching all booking information entries...")
    bookings = []

    time.sleep(8)

    try:
        booking_cards = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiCollapse-root.MuiCollapse-vertical.MuiCollapse-hidden")))
        st.write(f"📋 Found {len(booking_cards)} booking entries using MuiCollapse-hidden")
    except Exception as e:
        logger.warning(f"Could not find booking entries with MuiCollapse-hidden: {str(e)}")
        st.write(f"⚠️ Could not find booking entries with MuiCollapse-hidden: {str(e)}")
        try:
            booking_cards = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiAccordionSummary-content.Mui-expanded.MuiAccordionSummary-contentGutters")))
            st.write(f"📋 Found {len(booking_cards)} booking entries using MuiAccordionSummary-expanded")
        except Exception as e:
            logger.warning(f"Could not find booking entries with MuiAccordionSummary-expanded: {str(e)}")
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
            logger.error(f"Error extracting booking #{i+1}: {str(e)}")
            st.write(f"⚠️ Error extracting booking #{i+1}: {str(e)}")
    
    return bookings

def is_ota_booking(booking):
    """Check if booking is from OTA."""
    source = booking.get('booking_source', '').lower()
    return any(ota.lower() in source for ota in OTA_SOURCES)

def login_to_stayflexi(chrome_profile_path, property_name, hotel_id):
    """Login to Stayflexi and navigate to reservations."""
    driver = None
    try:
        # Check for stayflexi secrets
        if "stayflexi" not in st.secrets:
            logger.error("Missing 'stayflexi' secrets in Streamlit configuration")
            st.error("❌ Missing Stayflexi credentials. Please add 'stayflexi' email and password to Streamlit secrets.")
            return []
        
        driver = setup_driver(chrome_profile_path)
        wait = WebDriverWait(driver, 30)  # Increased timeout
        bookings = []
        
        st.write(f"🔹 Opening StayFlexi for {property_name}...")
        driver.get("https://app.stayflexi.com/auth/login")
        logger.info(f"Navigated to Stayflexi login page for {property_name}")
        
        try:
            email_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
            email_field.clear()
            email_field.send_keys(st.secrets["stayflexi"]["email"])
            logger.info(f"Entered email for {property_name}")
            
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]")))
            login_button.click()
            logger.info(f"Clicked first Sign In button for {property_name}")
            
            password_field = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='password']")))
            password_field.send_keys(st.secrets["stayflexi"]["password"])
            logger.info(f"Entered password for {property_name}")
            
            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Sign In')]")))
            login_button.click()
            st.write("✅ Logged in successfully")
            logger.info(f"Logged in successfully for {property_name}")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Login attempt failed for {property_name}: {str(e)}")
            st.warning(f"⚠️ Login failed for {property_name}: {str(e)}")
            return []
        
        # Navigate to dashboard
        dashboard_button = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[@href='/dashboard?hotelId={hotel_id}']")))
        dashboard_button.click()
        logger.info(f"Clicked dashboard button for hotel ID {hotel_id}")
        time.sleep(3)
        driver.switch_to.window(driver.window_handles[-1])
        
        # Navigate to reservations
        reservations_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Reservations')]")))
        reservations_button.click()
        logger.info(f"Clicked Reservations button for {property_name}")
        
        all_bookings = fetch_and_display_bookings(driver, wait, hotel_id)
        bookings = [b for b in all_bookings if is_ota_booking(b)]
        st.write(f"📋 Fetched {len(bookings)} OTA bookings for {property_name}")
        logger.info(f"Fetched {len(bookings)} OTA bookings for {property_name}")
        
        return bookings
    except Exception as e:
        logger.error(f"Error for {property_name}: {str(e)}")
        st.error(f"❌ Error for {property_name}: {str(e)}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"Closed WebDriver for {property_name}")
            except Exception as e:
                logger.warning(f"Failed to close WebDriver for {property_name}: {str(e)}")

def store_in_supabase(bookings, property_name):
    """Store OTA bookings in Supabase 'otabooking' table."""
    for booking in bookings:
        try:
            is_duplicate, existing_id = check_duplicate_guest(
                supabase, "otabooking", 
                booking.get('guest_name', ''), 
                booking.get('guest_phone', ''), 
                booking.get('room_number', '')
            )
            if is_duplicate:
                st.warning(f"ℹ️ Duplicate booking {booking.get('booking_id')} (exists as {existing_id})")
                logger.info(f"Skipped duplicate booking {booking.get('booking_id')} for {property_name}")
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
        
            supabase.table("otabooking").insert(data).execute()
            st.success(f"✅ Stored booking {booking.get('booking_id')} for {property_name}")
            logger.info(f"Stored booking {booking.get('booking_id')} for {property_name}")
        except Exception as e:
            st.error(f"❌ Error storing booking {booking.get('booking_id', 'unknown')}: {str(e)}")
            logger.error(f"Error storing booking for {property_name}: {str(e)}")

def fetch_for_property(property_name, hotel_id):
    """Fetch OTA bookings for a single property."""
    bookings = login_to_stayflexi(CHROME_PROFILE_PATH, property_name, hotel_id)
    if bookings:
        store_in_supabase(bookings, property_name)
    else:
        st.warning(f"⚠️ No bookings fetched for {property_name}")
        logger.warning(f"No bookings fetched for {property_name}")

def show_online_reservations():
    """Streamlit UI for online reservations."""
    st.title("📡 Online Reservations (OTA Bookings)")
    st.markdown("Sync bookings from Stayflexi for each property.")

    if st.button("🔄 Sync All Properties", key="sync_all"):
        with st.spinner("Syncing all properties..."):
            progress_bar = st.progress(0)
            total = len(PROPERTIES)
            for i, (name, id) in enumerate(PROPERTIES.items()):
                try:
                    fetch_for_property(name, id)
                    progress_bar.progress((i + 1) / total)
                except Exception as e:
                    st.error(f"❌ Error syncing {name}: {str(e)}")
                    logger.error(f"Error syncing {name}: {str(e)}")
            st.success("✅ All properties synced!")
            logger.info("Completed syncing all properties")

    for name, id in PROPERTIES.items():
        col1, col2 = st.columns([4, 1])
        col1.write(f"🏨 {name} (ID: {id})")
        if col2.button(f"🔄 Sync {name}", key=f"sync_{name}"):
            with st.spinner(f"Syncing {name}..."):
                try:
                    fetch_for_property(name, id)
                except Exception as e:
                    st.error(f"❌ Error syncing {name}: {str(e)}")
                    logger.error(f"Error syncing {name}: {str(e)}")
