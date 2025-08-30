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
import time
from datetime import datetime
import re
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed
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
    """Set up Chrome WebDriver with a fresh user profile."""
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

def extract_booking_data_from_text(text: str, hotel_id: str) -> Dict[str, str]:
    """Extract booking information including room number and type from text - ENHANCED with source detection"""
    booking_data = {
        'name': None,
        'booking_id': None,
        'phone': None,
        'booking_period': None,
        'booking_source': None,
        'total_without_taxes': None,
        'total_tax_amount': None,
        'total_with_taxes': None,
        'payment_made': None,
        'balance_due': None,
        'room_number': 'N/A',
        'room_type': 'N/A',
        'rate_plan': 'N/A',
        'adults_children_infant': 'N/A',
        '_original_text': text  # Store for debugging
    }

    lines = text.split('\n')

    # ENHANCED BOOKING SOURCE DETECTION FROM TEXT
    text_upper = text.upper()
    source_found = False
    
    # Check for OTA sources in the text with more comprehensive patterns
    ota_patterns = {
        'BOOKING.COM': ['BOOKING.COM', 'BOOKING COM', 'BOOKINGCOM', 'BOOKING DOT COM', 'BOOKING_COM'],
        'AGODA': ['AGODA'],
        'EXPEDIA': ['EXPEDIA', 'EXPEDIA.COM'],
        'MAKEMYTRIP': ['MAKEMYTRIP', 'MAKE MY TRIP', 'MMT'],
        'GOIBIBO': ['GOIBIBO'],
        'CLEARTRIP': ['CLEARTRIP', 'CLEAR TRIP'],
        'TRAVELOKA': ['TRAVELOKA'],
        'AIRBNB': ['AIRBNB'],
        'HOTELS.COM': ['HOTELS.COM', 'HOTELS COM'],
        'PRICELINE': ['PRICELINE']
    }
    
    for ota_name, patterns in ota_patterns.items():
        if any(pattern in text_upper for pattern in patterns):
            booking_data['booking_source'] = ota_name
            source_found = True
            logger.info(f"Booking source detected from text: {ota_name} for booking ID: {booking_data.get('booking_id', 'unknown')}")
            break
    
    if not source_found:
        # Look for less obvious OTA indicators
        ota_indicators = ['COMMISSION', 'BOOKING REFERENCE', 'CONFIRMATION CODE', 'CHANNEL', 'PARTNER']
        if any(indicator in text_upper for indicator in ota_indicators):
            booking_data['booking_source'] = 'UNKNOWN_OTA'
            logger.info("Possible OTA booking detected based on text indicators")
        else:
            # Check for patterns that might indicate online booking vs walk-in
            online_indicators = ['ONLINE', 'WEB', 'INTERNET', 'EMAIL', 'CONFIRMED']
            if any(indicator in text_upper for indicator in online_indicators):
                booking_data['booking_source'] = 'POSSIBLE_OTA'
                logger.info("Possible online booking detected")

    # Extract name - should be the first line if it doesn't contain booking patterns
    if lines and not re.search(r'SFBOOKING|Rs\.|CONFIRMED|ON_HOLD|Mar| - |[0-9]', lines[0]):
        booking_data['name'] = lines[0].strip()

    # Extract booking ID with specific hotel_id pattern
    booking_id_match = re.search(rf'SFBOOKING_{hotel_id}_\d+', text)
    if booking_id_match:
        booking_data['booking_id'] = booking_id_match.group(0)

    # Extract phone number
    for line in lines:
        line = line.strip()
        if re.match(r'NA|(\+\d{1,3}\s*)?[\d\s()-]{8,}', line):
            booking_data['phone'] = line
            break

    # Extract booking period (check-in to check-out dates)
    date_pattern = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+(?:AM|PM)\s+-\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s+(?:AM|PM)'
    date_match = re.search(date_pattern, text)
    if date_match:
        booking_data['booking_period'] = date_match.group(0)
    else:
        # Try alternate pattern for dates split across lines
        for i in range(len(lines) - 1):
            if " - " in lines[i] and re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', lines[i]):
                booking_data['booking_period'] = f"{lines[i].strip()} - {lines[i+1].strip()}"
                break

    # Extract room number and type from pattern like "101 (Deluxe Room)"
    room_pattern = r'(\d+)\s*\(\s*([^)]+)\s*\)'
    room_match = re.search(room_pattern, text)
    if room_match:
        booking_data['room_number'] = room_match.group(1).strip()
        booking_data['room_type'] = room_match.group(2).strip()

    return booking_data

def fetch_folio_details(driver: webdriver.Chrome, wait: WebDriverWait, booking: Dict[str, str], hotel_id: str) -> None:
    """Navigate to the folio page and fetch financial details, Rate Plan, and Adults/Children/Infant."""
    try:
        if booking['booking_id']:
            folio_url = f"https://app.stayflexi.com/folio/{booking['booking_id']}?hotelId={hotel_id}"
            logger.info(f"Navigating to folio page for {booking['booking_id']}...")
            driver.get(folio_url)
            time.sleep(5)

            # Try to expand accordion on folio page
            try:
                expand_button = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, ".MuiAccordionSummary-expandIconWrapper.css-1fx8m19")))
                driver.execute_script("arguments[0].scrollIntoView(); arguments[0].click();", expand_button)
                logger.info("Clicked down arrow button using CSS selector on View Folio page")
            except Exception as e:
                logger.warning(f"Could not click down arrow using CSS selector: {str(e)}")

            time.sleep(2)

            # ENHANCED BOOKING SOURCE EXTRACTION
            try:
                booking_source_found = False
                original_source = booking.get('booking_source')  # Keep original detection
                
                # Method 1: Check if we already detected source from original text
                if original_source and original_source not in ['DIRECT', None]:
                    booking_source_found = True
                    logger.info(f"Using booking source from original text: {original_source}")
                
                # Method 2: Look for specific OTA elements on folio page
                if not booking_source_found:
                    try:
                        # Try different selectors for booking source
                        source_selectors = [
                            "div.sourceName",
                            "[class*='source']",
                            "[class*='booking']", 
                            "div[class*='MuiTypography'][class*='body']",
                            ".css-*[class*='source']"
                        ]
                        
                        for selector in source_selectors:
                            try:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for elem in elements:
                                    text = elem.text.strip().upper()
                                    if text and any(ota.upper() in text for ota in ['BOOKING', 'AGODA', 'EXPEDIA', 'MAKEMYTRIP', 'GOIBIBO']):
                                        booking['booking_source'] = text
                                        booking_source_found = True
                                        logger.info(f"Booking Source found via CSS selector '{selector}': {booking['booking_source']}")
                                        break
                                if booking_source_found:
                                    break
                            except Exception as selector_error:
                                logger.debug(f"Selector '{selector}' failed: {str(selector_error)}")
                                continue
                    except Exception as e:
                        logger.warning(f"CSS selector method failed: {str(e)}")
                
                # Method 3: Search entire page source for OTA indicators
                if not booking_source_found:
                    try:
                        page_source = driver.page_source.upper()
                        
                        # More comprehensive OTA detection patterns
                        ota_patterns = {
                            'BOOKING.COM': ['BOOKING.COM', 'BOOKING COM', '"BOOKING"', 'BOOKINGCOM', 'BOOKING_COM'],
                            'AGODA': ['AGODA', '"AGODA"'],
                            'EXPEDIA': ['EXPEDIA', '"EXPEDIA"'],
                            'MAKEMYTRIP': ['MAKEMYTRIP', 'MAKE MY TRIP', '"MAKEMYTRIP"'],
                            'GOIBIBO': ['GOIBIBO', '"GOIBIBO"'],
                            'CLEARTRIP': ['CLEARTRIP', '"CLEARTRIP"'],
                            'TRAVELOKA': ['TRAVELOKA', '"TRAVELOKA"'],
                            'HOTELS.COM': ['HOTELS.COM', 'HOTELS COM'],
                            'AIRBNB': ['AIRBNB']
                        }
                        
                        for ota_name, patterns in ota_patterns.items():
                            if any(pattern in page_source for pattern in patterns):
                                booking['booking_source'] = ota_name
                                booking_source_found = True
                                logger.info(f"Booking Source found in page source: {booking['booking_source']}")
                                break
                    except Exception as e:
                        logger.warning(f"Page source search failed: {str(e)}")
                
                # Method 4: Check URL parameters or hidden fields
                if not booking_source_found:
                    try:
                        current_url = driver.current_url.upper()
                        if 'BOOKING' in current_url or 'AGODA' in current_url:
                            # Extract from URL if possible
                            for ota in ['BOOKING', 'AGODA', 'EXPEDIA']:
                                if ota in current_url:
                                    booking['booking_source'] = ota + '.COM' if ota != 'AGODA' else ota
                                    booking_source_found = True
                                    logger.info(f"Booking Source found in URL: {booking['booking_source']}")
                                    break
                    except Exception as e:
                        logger.warning(f"URL check failed: {str(e)}")
                
                # Method 5: Enhanced JavaScript search for booking source
                if not booking_source_found:
                    try:
                        js_source_check = driver.execute_script("""
                            // Check for data attributes containing source info
                            const elements = document.querySelectorAll('[data-source], [data-booking-source], input[type="hidden"]');
                            for (let elem of elements) {
                                const value = elem.value || elem.dataset.source || elem.dataset.bookingSource || elem.textContent;
                                if (value && (value.toLowerCase().includes('booking') || value.toLowerCase().includes('agoda') || value.toLowerCase().includes('expedia'))) {
                                    return value;
                                }
                            }
                            
                            // Check for any text nodes containing OTA names
                            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                            let node;
                            const candidates = [];
                            
                            while (node = walker.nextNode()) {
                                const text = node.textContent.trim().toLowerCase();
                                if (text.includes('booking.com') || text.includes('agoda') || text.includes('expedia') || 
                                    text.includes('makemytrip') || text.includes('goibibo')) {
                                    candidates.push(text);
                                }
                            }
                            
                            return candidates.length > 0 ? candidates[0] : null;
                        """)
                        
                        if js_source_check:
                            source_text = js_source_check.upper()
                            if 'BOOKING' in source_text:
                                booking['booking_source'] = 'BOOKING.COM'
                            elif 'AGODA' in source_text:
                                booking['booking_source'] = 'AGODA'
                            elif 'EXPEDIA' in source_text:
                                booking['booking_source'] = 'EXPEDIA'
                            elif 'MAKEMYTRIP' in source_text:
                                booking['booking_source'] = 'MAKEMYTRIP'
                            elif 'GOIBIBO' in source_text:
                                booking['booking_source'] = 'GOIBIBO'
                            else:
                                booking['booking_source'] = source_text[:50]  # Limit length
                            booking_source_found = True
                            logger.info(f"Booking Source found via JavaScript: {booking['booking_source']}")
                    except Exception as e:
                        logger.warning(f"JavaScript source check failed: {str(e)}")
                
                # Method 6: Debug logging - capture page content for analysis
                if not booking_source_found:
                    try:
                        # Log detailed page information for debugging
                        logger.warning(f"Could not find booking source for {booking['booking_id']} - logging debug info")
                        logger.info(f"Page title: {driver.title}")
                        logger.info(f"Current URL: {driver.current_url}")
                        
                        # Get all visible text elements for analysis
                        visible_elements = driver.find_elements(By.XPATH, "//*[not(self::script or self::style)][string-length(normalize-space(text())) > 0]")
                        visible_texts = []
                        
                        for elem in visible_elements[:20]:  # First 20 elements
                            try:
                                text = elem.text.strip()
                                if text and len(text) < 100:  # Reasonable length
                                    visible_texts.append(text)
                            except:
                                continue
                        
                        logger.info(f"Visible page elements: {visible_texts}")
                        
                        # Try to get some page content for debugging
                        try:
                            body_text = driver.find_element(By.TAG_NAME, "body").text
                            # Look for any potential OTA indicators in the full text
                            body_upper = body_text.upper()
                            potential_sources = []
                            
                            for word in ['BOOKING', 'AGODA', 'EXPEDIA', 'MAKEMYTRIP', 'GOIBIBO', 'CHANNEL', 'SOURCE']:
                                if word in body_upper:
                                    # Get context around the word
                                    start_idx = max(0, body_upper.find(word) - 50)
                                    end_idx = min(len(body_text), body_upper.find(word) + 50)
                                    context = body_text[start_idx:end_idx]
                                    potential_sources.append(f"{word}: ...{context}...")
                            
                            if potential_sources:
                                logger.info(f"Potential source contexts found: {potential_sources}")
                            else:
                                logger.info("No obvious OTA indicators found in page text")
                                
                        except Exception as debug_error:
                            logger.warning(f"Debug content extraction failed: {str(debug_error)}")
                        
                        # For now, don't default to DIRECT - leave as None/original for investigation
                        if not booking.get('booking_source') or booking['booking_source'] in ['DIRECT']:
                            booking['booking_source'] = None  # Will be handled in is_ota_booking function
                            
                    except Exception as debug_error:
                        logger.error(f"Debug logging failed: {str(debug_error)}")
                        
            except Exception as e:
                logger.error(f"Error in booking source extraction: {str(e)}")
                # Don't override existing source detection from text
                if not booking.get('booking_source'):
                    booking['booking_source'] = None

            # Improved Rate Plan extraction with multiple strategies
            try:
                # Strategy 1: Look for text content that contains rate plan information
                rate_plan_found = False
                
                # Try to find elements containing "Plan" or "Rate" text
                potential_rate_elements = driver.find_elements(By.XPATH, 
                    "//div[contains(text(), 'Plan') or contains(text(), 'Rate') or contains(text(), 'Standard') or contains(text(), 'Flexible')]")
                
                for elem in potential_rate_elements:
                    text = elem.text.strip()
                    # Skip elements that look like labels or contain unwanted text
                    if text and not any(skip_word in text.lower() for skip_word in ['add', 'view', 'booking', 'notes', '(0)']):
                        # Check if this looks like a rate plan (contains "Plan" or is a simple text)
                        if 'plan' in text.lower() or re.match(r'^[A-Za-z\s]+$', text):
                            booking['rate_plan'] = text
                            rate_plan_found = True
                            logger.info(f"Rate Plan found via content search: {booking['rate_plan']}")
                            break
                
                # Strategy 2: If not found, try the original XPath as fallback
                if not rate_plan_found:
                    try:
                        rate_plan_elem = driver.find_element(By.XPATH, "//*[@id='panel1a-content']/div/div/div[1]/div/div[8]/div/div[2]")
                        text = rate_plan_elem.text.strip()
                        if text and not any(skip_word in text.lower() for skip_word in ['add', 'view', 'booking', 'notes', '(0)']):
                            booking['rate_plan'] = text
                            rate_plan_found = True
                            logger.info(f"Rate Plan found via original XPath: {booking['rate_plan']}")
                    except Exception:
                        pass
                
                # Strategy 3: Use JavaScript to search through all text nodes
                if not rate_plan_found:
                    try:
                        js_rate_plan = driver.execute_script("""
                            function findRatePlan() {
                                const walker = document.createTreeWalker(
                                    document.getElementById('panel1a-content') || document.body,
                                    NodeFilter.SHOW_TEXT,
                                    null,
                                    false
                                );
                                
                                let node;
                                const candidates = [];
                                
                                while (node = walker.nextNode()) {
                                    const text = node.textContent.trim();
                                    if (text && 
                                        (text.includes('Plan') || text.includes('Standard') || text.includes('Flexible')) &&
                                        !text.includes('Add') && 
                                        !text.includes('View') && 
                                        !text.includes('booking') &&
                                        !text.includes('(0)') &&
                                        text.length < 50) {
                                        candidates.push(text);
                                    }
                                }
                                
                                return candidates.length > 0 ? candidates[0] : null;
                            }
                            return findRatePlan();
                        """)
                        
                        if js_rate_plan:
                            booking['rate_plan'] = js_rate_plan
                            rate_plan_found = True
                            logger.info(f"Rate Plan found via JavaScript: {booking['rate_plan']}")
                    except Exception as js_e:
                        logger.warning(f"JavaScript rate plan search failed: {str(js_e)}")
                
                if not rate_plan_found:
                    booking['rate_plan'] = 'N/A'
                    logger.warning("Could not find Rate Plan using any method")
                    
            except Exception as e:
                booking['rate_plan'] = 'N/A'
                logger.warning(f"Error in rate plan extraction: {str(e)}")

            # Enhanced Adults/Children/Infant extraction with multiple strategies
            try:
                adults_children_found = False
                
                # Strategy 1: Look specifically for numeric patterns like "7/0/0" and exclude field labels
                numeric_pattern_elements = driver.find_elements(By.XPATH, "//*[text()]")
                
                for elem in numeric_pattern_elements:
                    text = elem.text.strip()
                    # Look for exact numeric patterns and exclude field labels
                    if re.match(r'^\d+/\d+/\d+$', text):
                        booking['adults_children_infant'] = text
                        adults_children_found = True
                        logger.info(f"Adults/Children/Infant found via exact numeric pattern: {booking['adults_children_infant']}")
                        break
                    # Also check for single numbers that might represent guest count
                    elif re.match(r'^\d+$', text) and int(text) <= 20 and int(text) > 0:
                        # Look at the parent/sibling elements to see if this is guest-related
                        try:
                            parent_text = elem.find_element(By.XPATH, "./..").text.lower()
                            if any(keyword in parent_text for keyword in ['guest', 'adult', 'pax', 'occupancy']):
                                booking['adults_children_infant'] = f"{text}/0/0"
                                adults_children_found = True
                                logger.info(f"Adults/Children/Infant found via single guest count: {booking['adults_children_infant']}")
                                break
                        except Exception:
                            pass
                
                # Strategy 2: Enhanced JavaScript search with better filtering
                if not adults_children_found:
                    try:
                        js_adults_children = driver.execute_script("""
                            function findAdultsChildren() {
                                const walker = document.createTreeWalker(
                                    document.body,
                                    NodeFilter.SHOW_TEXT,
                                    null,
                                    false
                                );
                                
                                let node;
                                const candidates = [];
                                
                                while (node = walker.nextNode()) {
                                    const text = node.textContent.trim();
                                    
                                    // Pattern 1: Exact X/Y/Z format (highest priority)
                                    if (/^\\d+\\/\\d+\\/\\d+$/.test(text)) {
                                        candidates.push({text: text, priority: 1});
                                    }
                                    // Pattern 2: Single digit that might be guest count
                                    else if (/^\\d+$/.test(text) && parseInt(text) <= 20 && parseInt(text) > 0) {
                                        const parentText = node.parentElement ? node.parentElement.textContent.toLowerCase() : '';
                                        if (parentText.includes('guest') || parentText.includes('adult') || parentText.includes('pax')) {
                                            candidates.push({text: text + '/0/0', priority: 2});
                                        }
                                    }
                                }
                                
                                // Filter out field labels
                                const filtered = candidates.filter(c => {
                                    const lowerText = c.text.toLowerCase();
                                    return (!lowerText.includes('adult') && 
                                           !lowerText.includes('child') && 
                                           !lowerText.includes('infant')) ||
                                           /^\\d+\\/\\d+\\/\\d+$/.test(c.text) ||
                                           /^\\d+\\/0\\/0$/.test(c.text);
                                });
                                
                                // Sort by priority and return best match
                                filtered.sort((a, b) => a.priority - b.priority);
                                return filtered.length > 0 ? filtered[0].text : null;
                            }
                            return findAdultsChildren();
                        """)
                        
                        if js_adults_children and 'adult' not in js_adults_children.lower():
                            booking['adults_children_infant'] = js_adults_children
                            adults_children_found = True
                            logger.info(f"Adults/Children/Infant found via enhanced JavaScript: {booking['adults_children_infant']}")
                    except Exception as js_e:
                        logger.warning(f"Enhanced JavaScript adults/children search failed: {str(js_e)}")
                
                # Strategy 3: Try original XPath but validate it's not a field label
                if not adults_children_found:
                    try:
                        adults_children_elem = driver.find_element(By.XPATH, "//*[@id='panel1a-content']/div/div/div[2]/div/div[8]/div/div[2]")
                        text = adults_children_elem.text.strip()
                        # Validate it's not a field label and contains actual numeric data
                        if (text and 
                            not any(skip_word in text.lower() for skip_word in ['add', 'view', 'booking', 'notes', '(0)', 'adults', 'children', 'infant']) and
                            (re.search(r'\d+/\d+/\d+', text) or re.match(r'^\d+$', text))):
                            if re.match(r'^\d+$', text):
                                text = f"{text}/0/0"  # Convert single number to format
                            booking['adults_children_infant'] = text
                            adults_children_found = True
                            logger.info(f"Adults/Children/Infant found via original XPath: {booking['adults_children_infant']}")
                    except Exception:
                        pass
                
                if not adults_children_found:
                    booking['adults_children_infant'] = '1/0/0'  # Default to 1 adult instead of N/A
                    logger.warning("Could not find Adults/Children/Infant using any method, defaulting to 1/0/0")
                    
            except Exception as e:
                booking['adults_children_infant'] = '1/0/0'  # Default to 1 adult instead of N/A
                logger.warning(f"Error in adults/children extraction, defaulting to 1/0/0: {str(e)}")

            # Extract financial details
            try:
                financial_section = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//*[@id='kt_content']/div/div/div[1]/div/div[2]/div/div[2]/div")))
                financial_text = financial_section.text.strip().split('\n')

                for i, line in enumerate(financial_text):
                    if "Total without taxes" in line:
                        booking['total_without_taxes'] = re.sub(r'(INR|Rs\.)\s*', '', financial_text[i + 1].strip())
                    elif "Total tax amount" in line:
                        booking['total_tax_amount'] = re.sub(r'(INR|Rs\.)\s*', '', financial_text[i + 1].strip())
                    elif "Total with taxes and fees" in line:
                        booking['total_with_taxes'] = re.sub(r'(INR|Rs\.)\s*', '', financial_text[i + 1].strip())
                    elif "Payment made" in line:
                        booking['payment_made'] = re.sub(r'(INR|Rs\.)\s*', '', financial_text[i + 1].strip())
                    elif "Balance due" in line:
                        booking['balance_due'] = re.sub(r'(INR|Rs\.)\s*', '', financial_text[i + 1].strip())

                logger.info(f"Financial details extracted for {booking['booking_id']}")
            except Exception as e:
                logger.warning(f"Could not fetch financial details: {str(e)}")
                
            logger.info(f"Successfully fetched folio details for {booking['booking_id']}")
        else:
            logger.warning("No booking ID found, skipping folio fetch")
            
    except Exception as e:
        logger.error(f"Error fetching folio details: {str(e)}")

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch_and_display_bookings(driver: webdriver.Chrome, wait: WebDriverWait, hotel_id: str) -> List[Dict[str, str]]:
    """Fetch and display all booking information entries - using logic from Daily_DMS_All.py"""
    property_name = get_property_name(hotel_id) or "Unknown"
    st.write(f"Fetching all booking information entries for {property_name}...")
    bookings = []
    current_url = driver.current_url

    time.sleep(8)

    # Store all booking texts first, then process them
    booking_texts = []
    
    try:
        # Try to find booking cards using the same selectors as Daily_DMS_All.py
        booking_cards = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiCollapse-root.MuiCollapse-vertical.MuiCollapse-hidden")))
        st.write(f"Found {len(booking_cards)} booking entries using MuiCollapse-hidden for {property_name}")
    except Exception as e:
        logger.warning(f"Could not find booking entries with MuiCollapse-hidden: {str(e)}")
        try:
            booking_cards = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.MuiAccordionSummary-content.Mui-expanded.MuiAccordionSummary-contentGutters")))
            st.write(f"Found {len(booking_cards)} booking entries using MuiAccordionSummary-expanded for {property_name}")
        except Exception as e:
            logger.warning(f"Could not find booking entries with MuiAccordionSummary-expanded: {str(e)}")
            booking_cards = []

    # First pass: Extract all booking texts without navigating away
    for i, card in enumerate(booking_cards):
        st.write(f"Extracting text from booking #{i+1} for {property_name}:")
        try:
            # Check if element is collapsed and expand it
            if "MuiCollapse-hidden" in card.get_attribute("class"):
                logger.info("Element is collapsed, attempting to expand...")
                accordion_button = card.find_element(By.XPATH, "./preceding-sibling::div[contains(@class, 'MuiAccordionSummary-root')]")
                driver.execute_script("arguments[0].scrollIntoView(); arguments[0].click();", accordion_button)
                time.sleep(2)

            # Get the accordion container and extract text
            accordion = card.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MuiAccordion-root')]")
            summary_content = accordion.find_element(By.CSS_SELECTOR, "div.MuiAccordionSummary-content")
            raw_text = summary_content.text.strip()

            logger.info(f"Raw text: {raw_text[:200]}{'...' if len(raw_text) > 200 else ''}")
            
            # DEBUG: Show raw text in Streamlit for analysis
            st.write(f"DEBUG - Raw booking text sample: {raw_text[:300]}...")
            
            booking_texts.append(raw_text)
            
        except Exception as e:
            logger.error(f"Error extracting text from booking #{i+1}: {str(e)}")
            st.error(f"Error extracting text from booking #{i+1}: {str(e)}")

    # Second pass: Process each booking text and fetch folio details
    for i, raw_text in enumerate(booking_texts):
        st.write(f"Processing booking #{i+1} for {property_name}:")
        try:
            # Extract booking data using the improved function
            booking_data = extract_booking_data_from_text(raw_text, hotel_id)
            
            # DEBUG: Show extracted booking source
            st.write(f"DEBUG - Extracted booking source: {booking_data.get('booking_source', 'None')}")
            
            if booking_data.get('booking_id'):
                # Fetch additional details from folio page (this navigates away)
                fetch_folio_details(driver, wait, booking_data, hotel_id)
                
                # DEBUG: Show final booking source after folio fetch
                st.write(f"DEBUG - Final booking source after folio: {booking_data.get('booking_source', 'None')}")
                
                # Navigate back to reservations page for next booking
                if i < len(booking_texts) - 1:  # Don't navigate back on last booking
                    driver.get(current_url)
                    time.sleep(3)
                    # Wait for page to reload
                    wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Reservations')]")))
                
                bookings.append(booking_data)
                st.write(f"Extracted booking: {booking_data.get('booking_id')} for {property_name}")
                logger.info(f"Successfully extracted booking: {booking_data.get('booking_id')}")
            else:
                st.write(f"No booking ID found for booking #{i+1} in {property_name}, skipping...")
                logger.warning(f"No booking ID found in booking #{i+1}")

        except Exception as e:
            logger.error(f"Error processing booking #{i+1}: {str(e)}")
            st.error(f"Error processing booking #{i+1}: {str(e)}")
            # Try to navigate back to reservations page if there was an error
            try:
                driver.get(current_url)
                time.sleep(3)
                wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Reservations')]")))
            except Exception as nav_error:
                logger.warning(f"Could not navigate back to reservations: {str(nav_error)}")

    # If no booking cards found, try JavaScript approach from Daily_DMS_All.py
    if not booking_cards:
        st.write(f"No booking cards found, trying JavaScript approach for {property_name}...")
        js_bookings = match_patterns_on_page(driver, hotel_id)
        bookings.extend(js_bookings)

    return bookings

def match_patterns_on_page(driver: webdriver.Chrome, hotel_id: str) -> List[Dict[str, str]]:
    """Look for booking patterns directly on page using JavaScript - from Daily_DMS_All.py"""
    logger.info("Executing JavaScript to find booking patterns...")
    
    js_find_bookings = f"""
    const elements = [];
    const nodeIterator = document.createNodeIterator(
        document.body,
        NodeFilter.SHOW_TEXT,
        {{ acceptNode: function(node) {{ 
            return node.textContent.includes('SFBOOKING_{hotel_id}') ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        }} }}
    );
    
    let node;
    while(node = nodeIterator.nextNode()) {{
        let parent = node.parentElement;
        let depth = 0;
        while(parent && depth < 5) {{
            if (parent.offsetWidth > 100 && parent.offsetHeight > 50) {{
                elements.push({{
                    text: parent.innerText,
                    html: parent.outerHTML
                }});
                break;
            }}
            parent = parent.parentElement;
            depth++;
        }}
    }}
    return elements;
    """
    
    booking_elements = driver.execute_script(js_find_bookings)
    bookings = []
    
    if booking_elements:
        st.write(f"Found {len(booking_elements)} booking elements using JavaScript")
        for i, elem in enumerate(booking_elements[:3]):
            st.write(f"Booking Element #{i+1}:")
            text = elem.get('text', '')
            logger.info(f"Raw text: {text[:200]}...")
            booking_data = extract_booking_data_from_text(text, hotel_id)
            
            if booking_data.get('booking_id'):
                bookings.append(booking_data)
                st.write(f"Extracted booking: {booking_data.get('booking_id')}")
            else:
                st.write(f"No booking ID found in element #{i+1}")
    else:
        logger.warning("No booking elements found using JavaScript")
        st.warning("No booking elements found using JavaScript")

    return bookings

def is_ota_booking(booking: Dict[str, str]) -> bool:
    """Enhanced OTA detection with better debugging and more inclusive criteria."""
    source = booking.get('booking_source')
    
    # Handle None or empty source
    if not source:
        logger.warning(f"Booking {booking.get('booking_id', 'unknown')} has no booking source")
        
        # TEMPORARY: For debugging, let's include bookings without source to see what we're missing
        # In production, you might want to return False here
        logger.info(f"TEMP: Including booking {booking.get('booking_id', 'unknown')} without source for analysis")
        return True  # TEMPORARY - change to False in production
    
    source_lower = source.lower()
    
    # Include more OTA indicators and temporary sources
    ota_indicators = [
        'booking', 'agoda', 'expedia', 'makemytrip', 'goibibo', 'cleartrip', 
        'traveloka', 'hotels.com', 'airbnb', 'priceline',
        'unknown_ota', 'possible_ota'  # Include our temporary markers
    ]
    
    is_ota = any(indicator in source_lower for indicator in ota_indicators)
    
    logger.info(f"Booking {booking.get('booking_id', 'unknown')} source: '{source}', is_ota: {is_ota}")
    return is_ota

def login_to_stayflexi(chrome_profile_path: str, property_name: str, hotel_id: str) -> List[Dict[str, str]]:
    """Login to Stayflexi and navigate to reservations."""
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
        
        st.write(f"Opening StayFlexi for {property_name} (ID: {hotel_id})...")
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
            st.write(f"Logged in successfully for {property_name}")
            logger.info(f"Logged in successfully for {property_name}")
            wait.until(EC.presence_of_element_located((By.XPATH, f"//a[@href='/dashboard?hotelId={hotel_id}']")))
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
        
        # Fetch all bookings using the improved logic
        all_bookings = fetch_and_display_bookings(driver, wait, hotel_id)
        
        # DEBUG: Show all bookings before filtering
        st.write(f"DEBUG - Total bookings found: {len(all_bookings)}")
        for booking in all_bookings:
            st.write(f"  - {booking.get('booking_id', 'No ID')} | Source: {booking.get('booking_source', 'None')} | Name: {booking.get('name', 'No name')}")
        
        # Filter for OTA bookings with improved error handling
        bookings = []
        for booking in all_bookings:
            try:
                if is_ota_booking(booking):
                    bookings.append(booking)
                    logger.info(f"Added OTA booking: {booking.get('booking_id')} from {booking.get('booking_source', 'unknown')}")
                else:
                    logger.info(f"Skipped non-OTA booking: {booking.get('booking_id')} from {booking.get('booking_source', 'unknown')}")
            except Exception as e:
                logger.error(f"Error filtering booking {booking.get('booking_id', 'unknown')}: {str(e)}")
                # Include booking in results if filtering fails to avoid losing data
                bookings.append(booking)
        
        st.write(f"Fetched {len(bookings)} OTA bookings out of {len(all_bookings)} total bookings for {property_name}")
        logger.info(f"Fetched {len(bookings)} OTA bookings for {property_name}")
        
        return bookings
    except Exception as e:
        logger.error(f"Error for {property_name} (ID: {hotel_id}): {str(e)}")
        st.error(f"Error for {property_name} (ID: {hotel_id}): {str(e)}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
                logger.info(f"Closed WebDriver for {property_name}")
            except Exception as e:
                logger.warning(f"Failed to close WebDriver for {property_name}: {str(e)}")

def store_in_supabase(bookings: List[Dict[str, str]], property_name: str) -> None:
    """Store OTA bookings in Supabase 'otabooking' table with enhanced error handling."""
    if not bookings:
        st.warning(f"No bookings to store for {property_name}")
        return
        
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    stored_count = 0
    skipped_count = 0
    error_count = 0
    
    for booking in bookings:
        if not booking.get('booking_id'):
            logger.warning(f"Skipping booking for {property_name} due to missing booking_id")
            st.warning(f"Skipping booking for {property_name}: No booking ID found")
            skipped_count += 1
            continue
            
        try:
            # Enhanced booking source handling
            booking_source = booking.get('booking_source')
            if not booking_source or booking_source in ['None', '']:
                booking_source = 'UNKNOWN'  # Use UNKNOWN instead of DIRECT for null sources
                logger.info(f"Set booking_source to UNKNOWN for booking {booking.get('booking_id')}")
            
            booking['booking_source'] = booking_source
            
            # Check if this exact combination of booking_id, property, and room_number already exists
            existing_exact_booking = supabase.table("otabooking").select("*").eq("property", property_name).eq("booking_id", booking.get('booking_id')).eq("room_number", booking.get('room_number', 'N/A')).execute()
            
            if existing_exact_booking.data:
                st.warning(f"Exact duplicate: Booking {booking.get('booking_id')} room {booking.get('room_number', 'N/A')} already exists for {property_name}")
                logger.info(f"Skipped exact duplicate booking {booking.get('booking_id')} room {booking.get('room_number', 'N/A')} for {property_name}")
                skipped_count += 1
                continue

            # Check if there are other rooms for this booking_id (multi-room scenario)
            other_rooms = supabase.table("otabooking").select("room_number").eq("property", property_name).eq("booking_id", booking.get('booking_id')).execute()
            
            if other_rooms.data:
                existing_rooms = [room['room_number'] for room in other_rooms.data]
                current_room = booking.get('room_number', 'N/A')
                
                if current_room not in existing_rooms:
                    st.info(f"Multi-room booking detected: {booking.get('booking_id')} adding room {current_room} (existing rooms: {', '.join(existing_rooms)}) for {property_name}")
                    logger.info(f"Adding additional room {current_room} for booking {booking.get('booking_id')} at {property_name}")
                else:
                    st.warning(f"Room {current_room} already exists for booking {booking.get('booking_id')} at {property_name}")
                    logger.info(f"Skipped duplicate room {current_room} for booking {booking.get('booking_id')} at {property_name}")
                    skipped_count += 1
                    continue

            # Additional guest-based duplicate check (for different booking IDs but same guest and room)
            try:
                is_duplicate, existing_id = check_duplicate_guest(
                    supabase, "otabooking", 
                    booking.get('name', ''), 
                    booking.get('phone', ''), 
                    booking.get('room_number', '')
                )
                if is_duplicate and existing_id != booking.get('booking_id'):
                    st.warning(f"Guest duplicate: {booking.get('name')} already has booking {existing_id} for same room at {property_name}")
                    logger.info(f"Skipped guest duplicate: {booking.get('name')} already has booking {existing_id} for {property_name}")
                    skipped_count += 1
                    continue
            except Exception as guest_check_error:
                logger.warning(f"Guest duplicate check failed for {booking.get('booking_id')}: {str(guest_check_error)}")

            # Parse dates from booking_period with enhanced error handling
            check_in = ""
            check_out = ""
            if booking.get('booking_period'):
                try:
                    dates = booking['booking_period'].split(' - ')
                    if len(dates) == 2:
                        check_in_date = datetime.strptime(dates[0], "%b %d, %Y %I:%M %p")
                        check_out_date = datetime.strptime(dates[1], "%b %d, %Y %I:%M %p")
                        check_in = check_in_date.strftime("%Y-%m-%d")
                        check_out = check_out_date.strftime("%Y-%m-%d")
                except ValueError as e:
                    logger.warning(f"Could not parse booking period '{booking.get('booking_period')}': {str(e)}")
        
            # Create a unique identifier for multi-room bookings by appending room number to booking_id
            unique_booking_id = f"{booking.get('booking_id')}_room_{booking.get('room_number', 'N/A')}"
            
            data = {
                "property": property_name,
                "report_date": datetime.now().date().isoformat(),
                "booking_date": datetime.now().date().isoformat(),  # Using report date as booking date
                "booking_id": unique_booking_id,  # Use unique booking ID to avoid constraint violation
                "original_booking_id": booking.get('booking_id'),  # Store original booking ID for reference
                "booking_source": booking_source,  # Ensure not None
                "guest_name": booking.get('name', ''),
                "guest_phone": booking.get('phone', ''),
                "check_in": check_in,
                "check_out": check_out,
                "total_with_taxes": safe_float(booking.get('total_with_taxes')),
                "payment_made": safe_float(booking.get('payment_made')),
                "adults_children_infant": booking.get('adults_children_infant', '1/0/0'),  # Default to 1/0/0
                "room_number": booking.get('room_number', 'N/A'),
                "total_without_taxes": safe_float(booking.get('total_without_taxes')),
                "total_tax_amount": safe_float(booking.get('total_tax_amount')),
                "room_type": booking.get('room_type', 'N/A'),
                "rate_plan": booking.get('rate_plan', 'N/A'),
                "created_at": datetime.now().isoformat()
            }
        
            result = supabase.table("otabooking").insert(data).execute()
            st.success(f"Stored booking {booking.get('booking_id')} (room {booking.get('room_number', 'N/A')}) for {property_name}")
            logger.info(f"Stored booking {booking.get('booking_id')} room {booking.get('room_number', 'N/A')} for {property_name}")
            stored_count += 1
            
        except Exception as e:
            # Handle the specific unique constraint violation
            if 'duplicate key value violates unique constraint' in str(e):
                st.warning(f"Booking {booking.get('booking_id')} already exists in database for {property_name}")
                logger.info(f"Skipped existing booking {booking.get('booking_id')} for {property_name}")
                skipped_count += 1
            else:
                st.error(f"Error storing booking {booking.get('booking_id', 'unknown')} for {property_name}: {str(e)}")
                logger.error(f"Error storing booking for {property_name}: {str(e)}")
                error_count += 1
    
    # Summary
    st.info(f"Storage summary for {property_name}: {stored_count} stored, {skipped_count} skipped, {error_count} errors")
    logger.info(f"Storage summary for {property_name}: {stored_count} stored, {skipped_count} skipped, {error_count} errors")

def fetch_for_property(property_name: str, hotel_id: str) -> None:
    """Fetch OTA bookings for a single property with enhanced error handling."""
    try:
        st.info(f"Starting fetch for {property_name} (ID: {hotel_id})")
        logger.info(f"Starting fetch for {property_name} (ID: {hotel_id})")
        
        bookings = login_to_stayflexi(CHROME_PROFILE_PATH, property_name, hotel_id)
        
        if bookings:
            st.info(f"Retrieved {len(bookings)} bookings for {property_name}, proceeding to store in database...")
            store_in_supabase(bookings, property_name)
        else:
            st.warning(f"No bookings fetched for {property_name} (ID: {hotel_id})")
            logger.warning(f"No bookings fetched for {property_name}")
            
    except Exception as e:
        st.error(f"Critical error during fetch for {property_name} (ID: {hotel_id}): {str(e)}")
        logger.error(f"Critical error during fetch for {property_name}: {str(e)}")

def show_online_reservations() -> None:
    """Streamlit UI for online reservations."""
    st.title("Online Reservations (OTA Bookings)")
    st.markdown("Sync bookings from Stayflexi for each property.")

    if st.button("Sync All Properties", key="sync_all"):
        with st.spinner("Syncing all properties..."):
            progress_bar = st.progress(0)
            total = len(PROPERTIES)
            success_count = 0
            error_count = 0
            
            for i, (name, id) in enumerate(PROPERTIES.items()):
                try:
                    st.write(f"Processing {i+1}/{total}: {name} (ID: {id})")
                    fetch_for_property(name, id)
                    success_count += 1
                    progress_bar.progress((i + 1) / total)
                except Exception as e:
                    st.error(f"Error syncing {name} (ID: {id}): {str(e)}")
                    logger.error(f"Error syncing {name}: {str(e)}")
                    error_count += 1
                    progress_bar.progress((i + 1) / total)
                    
            st.success(f"Sync completed! {success_count} successful, {error_count} errors")
            logger.info(f"Completed syncing all properties: {success_count} successful, {error_count} errors")

    st.markdown("---")
    st.subheader("Individual Property Sync")
    
    for name, id in PROPERTIES.items():
        col1, col2 = st.columns([4, 1])
        col1.write(f"Hotel: {name} (ID: {id})")
        if col2.button(f"Sync {name}", key=f"sync_{name}"):
            with st.spinner(f"Syncing {name}..."):
                try:
                    fetch_for_property(name, id)
                    st.success(f"Successfully synced {name}")
                except Exception as e:
                    st.error(f"Error syncing {name} (ID: {id}): {str(e)}")
                    logger.error(f"Error syncing {name}: {str(e)}")

if __name__ == "__main__":
    show_online_reservations()
