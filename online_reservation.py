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
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from selenium.common.exceptions import ElementNotInteractableException
from typing import List, Dict
from config import SUPABASE_URL, SUPABASE_KEY, PROPERTIES, OTA_SOURCES
from utils import safe_int, safe_float, check_duplicate_guest, get_property_name

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Chrome profile and ChromeDriver paths
CHROME_PROFILE_PATH = os.getenv("CHROME_PROFILE_PATH", f"/tmp/chrome_profile_{int(time.time())}")
CHROMEDRIVER_PATH = "/tmp/chromedriver/chromedriver"

def setup_driver(chrome_profile_path: str) -> webdriver.Chrome:
    """Set up Chrome WebDriver with a fresh user profile.
    
    Args:
        chrome_profile_path (str): Path to Chrome profile directory.
    
    Returns:
        webdriver.Chrome: Initialized WebDriver instance.
    """
    try:
        if os.path.exists(chrome_profile_path):
            shutil.rmtree(chrome_profile_path, ignore_errors=True)
        os.makedirs(chrome_profile_path, exist_ok=True)
        os.makedirs(os.path.dirname(CHROMEDRIVER_PATH), exist_ok=True)
        
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={chrome_profile_path}")
        chrome_options.add_argument("profile-directory=Profile 20")
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.binary_location = "/usr/bin/chromium"
        
        chromedriver_path = chromedriver_autoinstaller.install(path=os.path.dirname(CHROMEDRIVER_PATH))
        logger.info(f"ChromeDriver installed at: {chromedriver_path}")
        os.chmod(chromedriver_path, 0o755)
        service = ChromeService(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome WebDriver initialized successfully")
        return driver
    except Exception as e:
        logger.error(f"Failed to set up Chrome WebDriver: {str(e)}")
        st.error(f"Failed to initialize browser: {str(e)}")
        raise

def match_patterns_on_page(page_source: str) -> Dict[str, str]:
    """Extract specific fields from page source using regex patterns.
    
    Args:
        page_source (str): HTML or text content to parse.
    
    Returns:
        Dict[str, str]: Extracted booking fields.
    """
    patterns = {
        'booking_id': r'(Booking|Reservation)\s*ID.*?[:\s]+([A-Z0-9-]+)',
        'name': r'(Guest|Customer)\s*Name.*?[:\s]+(.*?)(?=\n|$)',
        'guest_phone': r'(Contact|Phone)\s*(Number|No).*?[:\s]+(.*?)(?=\n|$)',
        'check_in': r'Check-in.*?[:\s]+(\d{4}-\d{2}-\d{2})',
        'check_out': r'Check-out.*?[:\s]+(\d{4}-\d{2}-\d{2})',
        'total_with_taxes': r'Total\s*(with|including)\s*Taxes.*?[:\s]+₹?\s*([\d,]+\.?\d*)',
        'payment_made': r'Payment\s*Made.*?[:\s]+₹?\s*([\d,]+\.?\d*)',
        'adults_children_infant': r'(Adults/Children/Infant|Guests).*?[:\s]+(.*?)(?=\n|$)',
        'room_number': r'Room\s*(Number|No).*?[:\s]+(.*?)(?=\n|$)',
        'total_without_taxes': r'Total\s*(without|excluding)\s*Taxes.*?[:\s]+₹?\s*([\d,]+\.?\d*)',
        'total_tax_amount': r'Total\s*Tax\s*(Amount|).*?[:\s]+₹?\s*([\d,]+\.?\d*)',
        'room_type': r'Room\s*Type.*?[:\s]+(.*?)(?=\n|$)',
        'rate_plan': r'Rate\s*Plan.*?[:\s]+(.*?)(?=\n|$)',
        'booking_source': r'(Booking|Reservation)\s*Source.*?[:\s]+(.*?)(?=\n|$)',
        'booking_date': r'(Booking|Reservation)\s*Date.*?[:\s]+(\d{4}-\d{2}-\d{2})'
    }
    extracted_data = {}
    matched = []
    unmatched = []
    for key, pattern in patterns.items():
        match = re.search(pattern, page_source, re.IGNORECASE | re.DOTALL)
        if match and len(match.groups()) > 1:
            extracted_data[key] = match.group(2).strip()
            matched.append(key)
        elif match:
            extracted_data[key] = match.group(1).strip()
            matched.append(key)
        else:
            extracted_data[key] = ''
            unmatched.append(key)
    if matched:
        logger.info(f"Matched fields: {matched}")
    if unmatched:
        logger.warning(f"Unmatched fields: {unmatched}")
    return extracted_data

def extract_booking_data_from_text(text: str) -> Dict[str, str]:
    """Extract booking data from text using regex.
    
    Args:
        text (str): Text content to parse.
    
    Returns:
        Dict[str, str]: Extracted booking data.
    """
    return match_patterns_on_page(text)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry_if_exception_type=(ElementNotInteractableException,))
def fetch_and_display_bookings(driver: webdriver.Chrome, wait: WebDriverWait, hotel_id: str) -> List[Dict[str, str]]:
    """Fetch and display all booking information entries with retries.
    
    Args:
        driver (webdriver.Chrome): Selenium WebDriver instance.
        wait (WebDriverWait): WebDriverWait instance for waiting.
        hotel_id (str): Hotel ID for the property.
    
    Returns:
        List[Dict[str, str]]: List of extracted booking data.
    """
    property_name = get_property_name(hotel_id) or "Unknown"
    st.write(f"🔹 Fetching bookings for {property_name} (ID: {hotel_id})...")
    bookings = []
    attempt = 0

    try:
        booking_cards = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiAccordionSummary-root")))
        st.write(f"📋 Found {len(booking_cards)} booking entries using MuiAccordionSummary-root for {property_name}")
    except Exception as e:
        logger.warning(f"Could not find booking entries with MuiAccordionSummary-root for {property_name} (ID: {hotel_id}): {str(e)}")
        st.error(f"Could not find booking entries with MuiAccordionSummary-root for {property_name} (ID: {hotel_id}): {str(e)}")
        try:
            booking_cards = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiCollapse-root.MuiCollapse-vertical")))
            st.write(f"📋 Found {len(booking_cards)} booking entries using MuiCollapse-root for {property_name}")
        except Exception as e:
            logger.warning(f"Could not find booking entries with MuiCollapse-root for {property_name} (ID: {hotel_id}): {str(e)}")
            st.error(f"Could not find booking entries with MuiCollapse-root for {property_name} (ID: {hotel_id}): {str(e)}")
            try:
                booking_cards = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "button.MuiButtonBase-root")))
                st.write(f"📋 Found {len(booking_cards)} booking entries using MuiButtonBase-root for {property_name}")
            except Exception as e:
                logger.warning(f"Could not find booking entries with MuiButtonBase-root for {property_name} (ID: {hotel_id}): {str(e)}")
                st.error(f"Could not find booking entries with MuiButtonBase-root for {property_name} (ID: {hotel_id}): {str(e)}")
                try:
                    st.write(f"🔹 Attempting to scrape booking data from page source for {property_name}...")
                    page_source = driver.page_source
                    soup = BeautifulSoup(page_source, 'html.parser')
                    booking_sections = soup.select("div.MuiCollapse-root.MuiCollapse-vertical, div.MuiAccordionDetails-root")
                    st.write(f"📋 Found {len(booking_sections)} booking sections in page source for {property_name}")
                    for i, section in enumerate(booking_sections):
                        st.write(f"\n🔖 Booking #{i+1} for {property_name}:")
                        booking_text = section.get_text(separator='\n', strip=True)
                        booking_data = extract_booking_data_from_text(booking_text)
                        if booking_data.get('booking_id'):
                            bookings.append(booking_data)
                            st.write(f"📋 Extracted booking: {booking_data.get('booking_id')} for {property_name}")
                        else:
                            st.write(f"⚠️ No booking ID found for booking #{i+1} in {property_name}, skipping...")
                    return bookings
                except Exception as e:
                    logger.error(f"Error scraping page source for {property_name} (ID: {hotel_id}): {str(e)}")
                    st.error(f"Error scraping page source for {property_name} (ID: {hotel_id}): {str(e)}")
                    return bookings

    if booking_cards:
        logger.info(f"Found {len(booking_cards)} booking cards for {property_name}. First card HTML: {booking_cards[0].get_attribute('outerHTML')}")
        if not os.getenv("STREAMLIT_CLOUD"):
            try:
                driver.save_screenshot(f"/tmp/booking_page_{hotel_id}.png")
                logger.info(f"Screenshot saved to /tmp/booking_page_{hotel_id}.png for {property_name}")
            except Exception as e:
                logger.warning(f"Failed to save screenshot for {property_name} (ID: {hotel_id}): {str(e)}")

    for i, card in enumerate(booking_cards):
        st.write(f"\n🔖 Booking #{i+1} for {property_name}:")
        try:
            attempt += 1
            logger.info(f"Attempt {attempt} to click booking #{i+1} for {property_name}")
            wait.until(EC.element_to_be_clickable((By.ID, card.get_attribute('id')) if card.get_attribute('id') else (By.CSS_SELECTOR, "div.MuiAccordionSummary-root")))
            driver.execute_script("arguments[0].click();", card)
            time.sleep(2)
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            booking_text = soup.get_text(separator='\n', strip=True)
            booking_data = extract_booking_data_from_text(booking_text)
            if booking_data.get('booking_id'):
                bookings.append(booking_data)
                st.write(f"📋 Extracted booking: {booking_data.get('booking_id')} for {property_name}")
            else:
                st.write(f"⚠️ No booking ID found for booking #{i+1} in {property_name}, skipping...")
        except Exception as e:
            logger.error(f"Error extracting booking #{i+1} (attempt {attempt}) for {property_name} (ID: {hotel_id}): {str(e)}")
            st.error(f"Error extracting booking #{i+1} for {property_name} (ID: {hotel_id}): {str(e)}")
            try:
                st.write(f"🔹 Attempting to scrape booking #{i+1} directly for {property_name}...")
                card_source = card.get_attribute('outerHTML')
                soup = BeautifulSoup(card_source, 'html.parser')
                booking_text = soup.get_text(separator='\n', strip=True)
                booking_data = extract_booking_data_from_text(booking_text)
                if booking_data.get('booking_id'):
                    bookings.append(booking_data)
                    st.write(f"📋 Extracted booking: {booking_data.get('booking_id')} for {property_name}")
                else:
                    st.write(f"⚠️ No booking ID found in card #{i+1} for {property_name}, skipping...")
            except Exception as e:
                logger.error(f"Error scraping booking #{i+1} directly for {property_name} (ID: {hotel_id}): {str(e)}")
                st.error(f"Error scraping booking #{i+1} directly for {property_name} (ID: {hotel_id}): {str(e)}")
    
    return bookings

def is_ota_booking(booking: Dict[str, str]) -> bool:
    """Check if booking is from OTA.
    
    Args:
        booking (Dict[str, str]): Booking data dictionary.
    
    Returns:
        bool: True if booking is from an OTA source.
    """
    source = booking.get('booking_source', '').lower()
    return any(ota.lower() in source for ota in OTA_SOURCES)

def login_to_stayflexi(chrome_profile_path: str, property_name: str, hotel_id: str) -> List[Dict[str, str]]:
    """Login to Stayflexi and navigate to reservations.
    
    Args:
        chrome_profile_path (str): Path to Chrome profile directory.
        property_name (str): Name of the property.
        hotel_id (str): Hotel ID for the property.
    
    Returns:
        List[Dict[str, str]]: List of extracted bookings.
    """
    driver = None
    try:
        logger.info(f"Available secrets: {list(st.secrets.keys())}")
        if "stayflexi" not in st.secrets:
            logger.error(f"Missing 'stayflexi' secrets for {property_name} (ID: {hotel_id})")
            st.error(f"Missing Stayflexi credentials for {property_name} (ID: {hotel_id}). Available secrets: {list(st.secrets.keys())}")
            return []
        
        driver = setup_driver(chrome_profile_path)
        wait = WebDriverWait(driver, 30)
        bookings = []
        
        st.write(f"🔹 Opening StayFlexi for {property_name} (ID: {hotel_id})...")
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
            st.write(f"✅ Logged in successfully for {property_name}")
            logger.info(f"Logged in successfully for {property_name}")
            time.sleep(5)
        except Exception as e:
            logger.warning(f"Login attempt failed for {property_name} (ID: {hotel_id}): {str(e)}")
            st.error(f"Login failed for {property_name} (ID: {hotel_id}): {str(e)}")
            return []
        
        dashboard_button = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[@href='/dashboard?hotelId={hotel_id}']")))
        dashboard_button.click()
        logger.info(f"Clicked dashboard button for hotel ID {hotel_id}")
        time.sleep(3)
        driver.switch_to.window(driver.window_handles[-1])
        
        reservations_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Reservations')]")))
        reservations_button.click()
        logger.info(f"Clicked Reservations button for {property_name}")
        
        all_bookings = fetch_and_display_bookings(driver, wait, hotel_id)
        bookings = [b for b in all_bookings if is_ota_booking(b)]
        st.write(f"📋 Fetched {len(bookings)} OTA bookings for {property_name}")
        logger.info(f"Fetched {len(bookings)} OTA bookings for {property_name}")
        
        return bookings
    except Exception as e:
        logger.error(f"Error for {property_name} (
