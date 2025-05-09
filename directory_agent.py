from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from helper.form_field import form_field
import logging
import time
import json
import re
import os
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class DirectoryAgent:
    def __init__(self, business_data: Dict[str, Any]):
        """Initialize with business data for directory submissions."""
        self.business_data = business_data
        self.captcha_api_key = os.environ.get("CAPTCHA_API_KEY", "")
        
        # Configure Chrome options for Selenium
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument("--start-maximized")
        self.chrome_options.add_argument("--disable-extensions")
        self.chrome_options.add_argument("--disable-popup-blocking")
        self.chrome_options.add_argument("--disable-notifications")
        self.chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
        
    def submit_to_directory(self, url: str) -> Dict[str, Any]:
        """Submit business to a directory and return submission results."""
        driver = None
        try:
            # Initialize Chrome driver
            driver = webdriver.Chrome(options=self.chrome_options)
            wait = WebDriverWait(driver, 20)
            
            # Navigate to URL and take initial screenshot
            driver.get(url)
            time.sleep(2)
            
            screenshot_path = f"static/screenshots/{url.replace('://', '_').replace('/', '_')}.png"
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            driver.save_screenshot(screenshot_path)
            
            # Try to find submission link
            submission_link = self._find_submission_link(driver)
            if submission_link:
                driver.get(submission_link)
                time.sleep(2)
            
            # Handle login if required
            if self._is_login_required(driver):
                logger.info(f"Login required for {url}")
                self._handle_login(driver)
                time.sleep(2)
            
            # Fill the directory form
            form_data = self._fill_directory_form(driver)
            
            # Handle CAPTCHA if present
            captcha_result = self._handle_captcha(driver)
            
            # Submit the form
            submit_result = self._submit_form(driver)
            time.sleep(3)
            
            # Take confirmation screenshot
            confirmation_screenshot = f"static/screenshots/{url.replace('://', '_').replace('/', '_')}_confirmation.png"
            driver.save_screenshot(confirmation_screenshot)
            
            # Verify submission success
            success = self._verify_submission_success(driver)
            
            result = {
                "status": "success" if success else "failed",
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "screenshots": {
                    "initial": screenshot_path,
                    "confirmation": confirmation_screenshot
                },
                "form_data": form_data,
                "captcha_solved": captcha_result.get("solved", False) if captcha_result else False,
                "html_content": driver.page_source
            }
            
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            result = {
                "status": "error",
                "url": url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            
            if driver:
                error_screenshot = f"static/screenshots/{url.replace('://', '_').replace('/', '_')}_error.png"
                driver.save_screenshot(error_screenshot)
                result["screenshots"] = {"error": error_screenshot}
        
        finally:
            if driver:
                driver.quit()
        
        return result
    
    def _find_submission_link(self, driver):
        """Find the link to submit a business to the directory."""
        potential_texts = [
            "submit", "add", "list", "submit your site", "add your site", 
            "submit business", "add business", "add listing", "submit listing"
        ]
        
        for text in potential_texts:
            try:
                elements = driver.find_elements(By.XPATH, f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                if elements:
                    return elements[0].get_attribute("href")
            except NoSuchElementException:
                continue
        
        return None
    
    def _is_login_required(self, driver):
        """Check if login is required before submission."""
        login_indicators = [
            "login", "sign in", "log in", "signin", "log-in",
            "register", "sign up", "signup", "create account"
        ]
        
        page_content = driver.page_source.lower()
        
        for indicator in login_indicators:
            if indicator in page_content:
                try:
                    login_form = driver.find_elements(By.XPATH, "//form[.//input[@type='password']]")
                    if login_form:
                        return True
                except NoSuchElementException:
                    continue
        
        return False
    
    def _handle_login(self, driver):
        """Attempt to login using business credentials."""
        try:
            email_fields = driver.find_elements(By.XPATH, "//input[@type='email' or contains(@name, 'email') or contains(@id, 'email')]")
            if email_fields:
                email_fields[0].send_keys(self.business_data["email"])
            
            password_fields = driver.find_elements(By.XPATH, "//input[@type='password']")
            if password_fields:
                password = self.business_data['password']
                password_fields[0].send_keys(password)
            
            submit_buttons = driver.find_elements(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            if submit_buttons:
                submit_buttons[0].click()
                time.sleep(3)
            
            return True
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return False
    
    
        """Fill out directory submission form with business data."""
        form_data = {}
        
        field_mappings = {
            "name": self.business_data["company_name"],
            "title": self.business_data["company_name"],
            "company": self.business_data["company_name"],
            "business": self.business_data["company_name"],
            "url": self.business_data["website_url"],
            "website": self.business_data["website_url"],
            "site": self.business_data["website_url"],
            "email": self.business_data["email"],
            "phone": self.business_data["phone"],
            "description": self.business_data["business_description"],
            "about": self.business_data["business_description"],
            "category": self.business_data["business_category"],
            "keywords": ", ".join(self.business_data["keywords"]),
            "tags": ", ".join(self.business_data["keywords"]),
            "address": self.business_data["address"],
            "city": self.business_data["location"].get("city", ""),
            "state": self.business_data["location"].get("state", ""),
            "country": self.business_data["location"].get("country", ""),
            "zip": self.business_data["location"].get("zip", ""),
            "postal": self.business_data["location"].get("zip", ""),
            "facebook": self.business_data["social_media_links"].get("facebook", ""),
            "twitter": self.business_data["social_media_links"].get("twitter", ""),
            "linkedin": self.business_data["social_media_links"].get("linkedin", ""),
            "instagram": self.business_data["social_media_links"].get("instagram", ""),
            "founder": self.business_data["founder_name"],
            "owner": self.business_data["founder_name"],
        }
        
        # Fill text inputs
        for field_key, value in field_mappings.items():
            xpaths = [
                f"//input[contains(@name, '{field_key}')]",
                f"//input[contains(@id, '{field_key}')]",
                f"//input[contains(@placeholder, '{field_key}')]",
                f"//textarea[contains(@name, '{field_key}')]",
                f"//textarea[contains(@id, '{field_key}')]",
                f"//textarea[contains(@placeholder, '{field_key}')]"
            ]
            
            for xpath in xpaths:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for element in elements:
                        input_type = element.get_attribute("type") or ""
                        if input_type.lower() not in ["submit", "button", "hidden", "checkbox", "radio"]:
                            element.clear()
                            element.send_keys(str(value))
                            name = element.get_attribute("name") or element.get_attribute("id") or ""
                            form_data[name] = value
                except Exception as e:
                    logger.debug(f"Error filling field {field_key}: {str(e)}")
        
        # Handle category dropdowns
        try:
            select_elements = driver.find_elements(By.XPATH, "//select[contains(@name, 'category') or contains(@id, 'category')]")
            for select in select_elements:
                options = select.find_elements(By.TAG_NAME, "option")
                
                best_match = None
                for option in options:
                    option_text = option.text
                    if self.business_data["business_category"].lower() in option_text.lower():
                        best_match = option.get_attribute("value")
                        break
                
                if not best_match:
                    for option in options:
                        value = option.get_attribute("value")
                        if value and value != "0" and value != "-1":
                            best_match = value
                            break
                
                if best_match:
                    from selenium.webdriver.support.ui import Select
                    dropdown = Select(select)
                    dropdown.select_by_value(best_match)
                    name = select.get_attribute("name") or select.get_attribute("id") or ""
                    form_data[name] = best_match
        except Exception as e:
            logger.debug(f"Error handling category select: {str(e)}")
        
        # Handle checkboxes (like terms and conditions)
        try:
            checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
            for checkbox in checkboxes:
                checkbox_id = checkbox.get_attribute("id") or ""
                checkbox_name = checkbox.get_attribute("name") or ""
                
                if ("term" in checkbox_id.lower() or "agree" in checkbox_id.lower() or 
                    "accept" in checkbox_id.lower() or "consent" in checkbox_id.lower()):
                    if not checkbox.is_selected():
                        checkbox.click()
                    form_data[checkbox_name or checkbox_id] = True
                elif ("term" in checkbox_name.lower() or "agree" in checkbox_name.lower() or 
                      "accept" in checkbox_name.lower() or "consent" in checkbox_name.lower()):
                    if not checkbox.is_selected():
                        checkbox.click()
                    form_data[checkbox_name] = True
        except Exception as e:
            logger.debug(f"Error handling checkboxes: {str(e)}")
        
        return form_data
    
    def _fill_directory_form(self, driver):
        form_data = {}
        
        field_mappings = form_field(self.business_data)
        
        def try_fill_element(element, value):
            """Helper function to safely fill an element"""
            try:
                element.clear()
                element.send_keys(str(value))
                name = element.get_attribute("name") or element.get_attribute("id") or ""
                form_data[name] = value
                return True
            except Exception as e:
                logger.debug(f"Error filling field: {str(e)}")
                return False

        # First pass: Try exact matches
        for field_key, value in field_mappings.items():
            if not value:  # Skip empty values
                continue
                
            xpaths = [
                f"//input[contains(@name, '{field_key}')]",
                f"//input[contains(@id, '{field_key}')]",
                f"//input[contains(@placeholder, '{field_key}')]",
                f"//textarea[contains(@name, '{field_key}')]",
                f"//textarea[contains(@id, '{field_key}')]",
                f"//textarea[contains(@placeholder, '{field_key}')]"
            ]
            
            for xpath in xpaths:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for element in elements:
                        input_type = element.get_attribute("type") or ""
                        if input_type.lower() not in ["submit", "button", "hidden", "checkbox", "radio"]:
                            if try_fill_element(element, value):
                                break  # Move to next field if successful
                except Exception:
                    continue

        # Second pass: Try more flexible matching for location fields
        location_fields = {
            "city": ["town", "city", "location", "place"],
            "state": ["state", "province", "region", "county"],
            "zip": ["zip", "postal", "postcode"],
            "country": ["country", "nation"]
        }

        for field_type, variants in location_fields.items():
            value = self.business_data["location"].get(field_type, "")
            if not value:
                continue
                
            # Try each variant pattern
            for variant in variants:
                xpath = f"//*[contains(translate(@name, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{variant}')] | " \
                        f"//*[contains(translate(@id, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{variant}')] | " \
                        f"//*[contains(translate(@placeholder, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{variant}')] | " \
                        f"//label[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{variant}')]/following-sibling::input"
                
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for element in elements:
                        input_type = element.get_attribute("type") or ""
                        if input_type.lower() not in ["submit", "button", "hidden", "checkbox", "radio"]:
                            if try_fill_element(element, value):
                                break  # Move to next field if successful
                except Exception:
                    continue

        # Handle dropdowns (same as before)
        try:
            select_elements = driver.find_elements(By.XPATH, "//select[contains(@name, 'category') or contains(@id, 'category')]")
            for select in select_elements:
                options = select.find_elements(By.TAG_NAME, "option")
                
                best_match = None
                for option in options:
                    option_text = option.text
                    if self.business_data["business_category"].lower() in option_text.lower():
                        best_match = option.get_attribute("value")
                        break
                
                if not best_match:
                    for option in options:
                        value = option.get_attribute("value")
                        if value and value != "0" and value != "-1":
                            best_match = value
                            break
                
                if best_match:
                    from selenium.webdriver.support.ui import Select
                    dropdown = Select(select)
                    dropdown.select_by_value(best_match)
                    name = select.get_attribute("name") or select.get_attribute("id") or ""
                    form_data[name] = best_match
        except Exception as e:
            logger.debug(f"Error handling category select: {str(e)}")

        # Handle checkboxes (same as before)
        try:
            checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
            for checkbox in checkboxes:
                checkbox_id = checkbox.get_attribute("id") or ""
                checkbox_name = checkbox.get_attribute("name") or ""
                
                if ("term" in checkbox_id.lower() or "agree" in checkbox_id.lower() or 
                    "accept" in checkbox_id.lower() or "consent" in checkbox_id.lower()):
                    if not checkbox.is_selected():
                        checkbox.click()
                    form_data[checkbox_name or checkbox_id] = True
                elif ("term" in checkbox_name.lower() or "agree" in checkbox_name.lower() or 
                    "accept" in checkbox_name.lower() or "consent" in checkbox_name.lower()):
                    if not checkbox.is_selected():
                        checkbox.click()
                    form_data[checkbox_name] = True
        except Exception as e:
            logger.debug(f"Error handling checkboxes: {str(e)}")
        
        return form_data

    def _handle_captcha(self, driver):
        """Handle CAPTCHA challenges if present."""
        try:
            recaptcha_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'g-recaptcha') or contains(@class, 'recaptcha')]")
            if recaptcha_elements and self.captcha_api_key:
                site_key = recaptcha_elements[0].get_attribute("data-sitekey")
                if site_key:
                    # This is a placeholder for actual CAPTCHA solving service integration
                    url = "https://2captcha.com/in.php"
                    params = {
                        "key": self.captcha_api_key,
                        "method": "userrecaptcha",
                        "googlekey": site_key,
                        "pageurl": driver.current_url,
                        "json": 1
                    }
                    
                    try:
                        response = requests.get(url, params=params)
                        data = response.json()
                        if data["status"] == 1:
                            time.sleep(20)
                            
                            solution_url = f"https://2captcha.com/res.php?key={self.captcha_api_key}&action=get&id={data['request']}&json=1"
                            solution_response = requests.get(solution_url)
                            solution_data = solution_response.json()
                            
                            if solution_data["status"] == 1:
                                driver.execute_script(f"""
                                    document.querySelector('[name="g-recaptcha-response"]').innerHTML = '{solution_data["request"]}';
                                    if (typeof grecaptcha !== 'undefined') {{
                                        grecaptcha.ready(function() {{
                                            grecaptcha.execute('{site_key}');
                                        }});
                                    }}
                                """)
                                
                                return {"solved": True, "type": "recaptcha"}
                    except Exception as e:
                        logger.error(f"Error solving CAPTCHA: {str(e)}")
                        return {"solved": False, "error": str(e)}
        except Exception as e:
            logger.debug(f"Error checking for CAPTCHA: {str(e)}")
        
        return {"solved": False, "type": "none"}
    
    def _submit_form(self, driver):
        """Submit the filled-out form."""
        submit_xpaths = [
            "//button[@type='submit']",
            "//input[@type='submit']",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add')]",
            "//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
            "//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send')]",
            "//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'add')]"
        ]
        
        for xpath in submit_xpaths:
            try:
                submit_button = driver.find_element(By.XPATH, xpath)
                submit_button.click()
                time.sleep(3)
                return True
            except NoSuchElementException:
                continue
        
        return False
    
    def _verify_submission_success(self, driver):
        """Verify if the submission was successful."""
        current_url = driver.current_url
        page_text = driver.page_source.lower()
        
        success_indicators = [
            "success", "thank", "thanks", "confirm", "confirmation", 
            "submitted", "complete", "completed"
        ]
        
        # Check URL for success indicators
        for indicator in success_indicators:
            if indicator in current_url.lower():
                return True
        
        # Check page content for success messages
        for indicator in success_indicators:
            if indicator in page_text:
                patterns = [
                    f".*{indicator}.*submission.*",
                    f".*submission.*{indicator}.*",
                    f".*{indicator}.*received.*",
                    f".*{indicator}.*added.*",
                    f".*successfully.*{indicator}.*"
                ]
                
                for pattern in patterns:
                    if re.search(pattern, page_text):
                        return True
        
        # Check for error indicators
        error_indicators = ["error", "failed", "invalid", "wrong"]
        for indicator in error_indicators:
            if indicator in page_text:
                return False
        
        # Default to True if no clear error indicators
        return True