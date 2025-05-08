from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
import time
import json
import re
from datetime import datetime
from urllib.parse import urlparse, quote

logger = logging.getLogger(__name__)

class ListingChecker:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        # Configure Chrome options
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument("--start-maximized")
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-popup-blocking")
        self.chrome_options.add_argument("--disable-notifications")
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        # For headless mode (uncomment if needed)
        # self.chrome_options.add_argument("--headless")
        # self.chrome_options.add_argument("--disable-gpu")
    
    def check_listings_for_business(self, business_id: int):
        """Check listing status for all successful submissions of a business"""
        submissions = self.data_manager.get_submissions_for_checking(business_id)
        
        for submission in submissions:
            try:
                business_data = json.loads(submission["data"])
                company_name = business_data["company_name"]
                
                listing_status = self._check_listing(
                    directory_url=submission["directory_url"],
                    company_name=company_name,
                    website_url=business_data["website_url"]
                )
                
                # Update status in database
                self.data_manager.update_listing_status(
                    business_id=submission["business_id"],
                    directory_url=submission["directory_url"],
                    listing_status=listing_status
                )
                
                logger.info(f"Updated listing status for {submission['directory_url']}: {listing_status}")
                
            except Exception as e:
                logger.error(f"Error checking listing for {submission['directory_url']}: {str(e)}")
    
    def _check_listing(self, directory_url: str, company_name: str, website_url: str) -> str:
        """Check if a listing is live on a directory using Selenium"""
        driver = None
        try:
            # Initialize Chrome driver
            driver = webdriver.Chrome(options=self.chrome_options)
            wait = WebDriverWait(driver, 20)
            
            # Navigate to directory homepage
            driver.get(directory_url)
            time.sleep(2)  # Initial page load
            
            # Look for search box
            search_boxes = driver.find_elements(By.XPATH, "//input[@type='search' or contains(@name, 'search') or contains(@placeholder, 'search')]")
            
            if search_boxes:
                # Use search box to find listing
                search_box = search_boxes[0]
                search_box.clear()
                search_box.send_keys(company_name)
                search_box.submit()
                time.sleep(3)  # Wait for search results
            else:
                # Try to construct a search URL
                parsed_url = urlparse(directory_url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                search_paths = ["/search", "/directory", "/listings", "/find"]
                
                for path in search_paths:
                    try:
                        search_url = f"{base_url}{path}?q={quote(company_name)}"
                        driver.get(search_url)
                        time.sleep(2)
                        # Check if we landed on a search results page
                        page_content = driver.page_source.lower()
                        if company_name.lower() in page_content:
                            break
                    except Exception:
                        continue
            
            # Check if company name or website URL appears on the page
            page_content = driver.page_source.lower()
            company_name_lower = company_name.lower()
            website_url_lower = website_url.lower()
            
            if company_name_lower in page_content:
                # Check if we can find the website URL as well for higher confidence
                if website_url_lower in page_content:
                    return "live"
                
                # Try to find a link that contains the domain
                domain = urlparse(website_url).netloc
                links = driver.find_elements(By.XPATH, f"//a[contains(@href, '{domain}')]")
                
                if links:
                    return "live"
                
                # If we only found the name but not the URL, it's potentially live
                return "potential"
            else:  
                # No listing found
                return "not_found"
            
        except Exception as e:
            logger.error(f"Error during listing check for {directory_url}: {str(e)}")
            return "error"
        
        finally:
            if driver:
                driver.quit()
    
    def check_all_listings(self):
        """Check all listings that need verification"""
        logger.info("Running weekly listing check for all businesses")
        
        # Get all submissions that need checking
        submissions = self.data_manager.get_submissions_for_checking()
        
        # Group by business_id for efficiency
        businesses = {}
        for submission in submissions:
            business_id = submission["business_id"]
            if business_id not in businesses:
                businesses[business_id] = []
            businesses[business_id].append(submission)
        
        # Check each business
        for business_id, business_submissions in businesses.items():
            self.check_listings_for_business(business_id)
            
        logger.info(f"Completed weekly listing check for {len(businesses)} businesses")
