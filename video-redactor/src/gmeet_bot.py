import time
import logging
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from src.redact import Redactor

class GMeetBot:
    def __init__(self, rules_dict):
        self.rules_dict = rules_dict
        self.redactor = Redactor(rules_dict)
        self.driver = None
        self.running = False

    def start(self, meeting_url):
        chrome_options = Options()
        # Allow real microphone and camera usage
        # (Removed fake device flags so user can participate normally)
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")
        
        # Anti-bot bypass to allow Google Login
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        chrome_options.add_experimental_option("detach", True)
        
        # Save session so you only have to login once
        profile_path = os.path.abspath("bot_profile")
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        logging.info(f"Navigating to {meeting_url}")
        self.driver.get(meeting_url)
        self.running = True
        
        return self.driver

    def read_captions_generator(self):
        """
        Yields redacted text from captions.
        """
        if not self.driver:
            return
            
        logging.info("Waiting for user to join and turn on captions...")
        
        # Wait a few seconds for the page to load
        time.sleep(5)
        
        # Auto-Join Logic (Fireflies style)
        try:
            # 1. Look for name input (if joining as anonymous guest)
            name_inputs = self.driver.find_elements(By.XPATH, "//input[@aria-label='Your name' or @placeholder='Your name']")
            if name_inputs:
                name_inputs[0].send_keys("Video Redactor AI Bot")
                time.sleep(1)
            
            # 2. Click Ask to join or Join now
            join_buttons = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'Ask to join') or contains(text(), 'Join now')]")
            for btn in join_buttons:
                try:
                    btn.click()
                    break
                except:
                    pass
        except Exception as e:
            pass
            
        processed_texts = set()
        
        while self.running:
            try:
                # Check if browser is still open and user is still in the meeting room
                current_url = self.driver.current_url
                
                # If they left the meeting (e.g. URL changed, or 'left the meeting' text appeared)
                if "meet.google.com" in current_url and "-" not in current_url.split("/")[-1]:
                    break
                
                page_source = self.driver.page_source
                if "You've left the meeting" in page_source:
                    break
                
                # Use precise Gmeet caption classes to avoid UI garbage like errors and clocks.
                elements = self.driver.find_elements(By.CSS_SELECTOR, "div.a4cQT span, div[jsname='tgaKEf'] span, div[aria-live='polite'] span, .CNusnd")
                
                new_texts = []
                for el in elements:
                    try:
                        text = el.text.strip()
                        
                        if not text or len(text) < 3:
                            continue
                            
                        # Filter out Material Icons and exact UI words
                        if "_" in text:
                            continue
                            
                        ui_words = {
                            "language", "English", "circle", "settings", "You", "mic", "mood", 
                            "chat", "apps", "info", "Feedback", "Present now", "Meeting details", 
                            "Return to home screen", "You can't join this video call", 
                            "Camera is starting", "Ready to join?", "Join now", "Other ways to join",
                            "videocam", "close", "error", "Camera might be blocked"
                        }
                        
                        if text in ui_words or "Microphone" in text or "Speaker" in text or "Camera might be blocked" in text:
                            continue
                            
                        if text not in processed_texts:
                            processed_texts.add(text)
                            new_texts.append(text)
                    except:
                        pass # Ignore StaleElementReferenceException if element changes while reading
                        
                if new_texts:
                    import datetime
                    # Redact the new text
                    combined_text = " ".join(new_texts)
                    redacted, _ = self.redactor.redact_segment(combined_text)
                    
                    # Format to look exactly like the Video Upload output
                    current_time = datetime.datetime.now().strftime("%H:%M:%S")
                    formatted_original = f"[{current_time}] Speaker: {combined_text}"
                    formatted_redacted = f"[{current_time}] Speaker: {redacted}"
                    
                    yield formatted_original, formatted_redacted
                    
                time.sleep(1.5)
            except Exception as e:
                # Only break if the browser was manually closed or disconnected
                error_str = str(e).lower()
                if "invalid session id" in error_str or "disconnected" in error_str or "no such window" in error_str or "not reachable" in error_str:
                    break
                # Otherwise, it's a transient error, just wait and retry
                time.sleep(1.5)
                
    def close(self):
        self.running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
