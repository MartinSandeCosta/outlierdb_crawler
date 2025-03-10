import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
from datetime import datetime
import logging
import os
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OutlierDBScraper:
    def __init__(self):
        self.base_url = "https://outlierdb.com"
        self.setup_driver()
        self.scraped_ids = set()  # Keep track of scraped video IDs to avoid duplicates
        self.debug_dir = "debug_html"
        os.makedirs(self.debug_dir, exist_ok=True)

    def save_html(self, name):
        """Save the current page HTML to a file for debugging."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.debug_dir}/{name}_{timestamp}.html"
        
        # Get the page source
        html = self.driver.page_source
        
        # Save to file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✓ Saved HTML to {filename}")
        
        # Also save a prettified version
        soup = BeautifulSoup(html, 'html.parser')
        pretty_filename = f"{self.debug_dir}/{name}_{timestamp}_pretty.html"
        with open(pretty_filename, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print(f"✓ Saved prettified HTML to {pretty_filename}")

    def setup_driver(self):
        """Set up the Chrome WebDriver with appropriate options."""
        print("\nSetting up Chrome WebDriver...")
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')  # Set a larger window size
        
        # Specify the Chrome version to use
        self.driver = uc.Chrome(
            options=options,
            version_main=133  # Specify your Chrome version here
        )
        print("✓ WebDriver setup complete")

    def extract_youtube_id(self, url):
        """Extract YouTube video ID from embed URL."""
        if not url:
            return None
        # Try to find YouTube video ID in the URL
        match = re.search(r'embed/([^?]+)', url)
        if match:
            return match.group(1)
        return None

    def wait_for_iframes(self):
        """Wait for iframes to load in the sequence cards."""
        print("Waiting for iframes to load...")
        try:
            # Wait for iframes to be present
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            print("✓ Iframes found")
            
            # Wait a bit more for them to fully load
            time.sleep(2)
            
            # Count iframes
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            print(f"Found {len(iframes)} iframes")
            
            return len(iframes) > 0
        except Exception as e:
            print(f"Error waiting for iframes: {e}")
            return False

    def scroll_to_bottom(self):
        """Scroll to the bottom of the page."""
        print("\nScrolling to bottom...")
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        # Scroll down in smaller increments
        current_height = 0
        while current_height < last_height:
            current_height += 300  # Scroll 300px at a time
            self.driver.execute_script(f"window.scrollTo(0, {current_height});")
            time.sleep(0.5)  # Small delay between scrolls
        
        # Final scroll to bottom
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)  # Wait for any lazy-loaded content
        
        print("✓ Scrolled to bottom")
        # Save HTML after scrolling
        self.save_html("after_scroll")

    def find_next_button(self):
        """Find and return the Next button element."""
        try:
            # First scroll to bottom
            self.scroll_to_bottom()
            
            # Save HTML before looking for button
            self.save_html("before_finding_button")
            
            # Look for the Next button using more specific selectors
            # First find the container div
            container = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.flex.justify-center.items-center.mt-4.pb-12"))
            )
            
            # Then find the Next button within that container
            next_button = container.find_element(By.XPATH, ".//button[text()='Next']")
            
            # Get the page info
            page_info = container.find_element(By.CSS_SELECTOR, "span.dark\\:text-neutral-200").text
            print(f"Page info: {page_info}")
            
            print("✓ Found Next button")
            return next_button
        except Exception as e:
            print(f"No Next button found: {str(e)}")
            # Save HTML when button not found
            self.save_html("button_not_found")
            return None

    def get_page(self):
        """Load the page and wait for content to be loaded."""
        try:
            print(f"\nLoading page: {self.base_url}")
            self.driver.get(self.base_url)
            
            # Wait for the sequence cards to be loaded
            print("Waiting for sequence cards to load...")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "sequence-card"))
            )
            
            # Give a little extra time for all content to load
            time.sleep(2)
            print("✓ Page loaded successfully")
            
            # Wait for initial iframes to load
            if not self.wait_for_iframes():
                print("Warning: No iframes found on initial load")
            
            # Save HTML after initial load
            self.save_html("initial_load")
            
            # Print page source length for debugging
            page_source = self.driver.page_source
            print(f"Page source length: {len(page_source)} characters")
            
            return page_source
        except Exception as e:
            logger.error(f"Error loading page: {e}")
            return None

    def parse_item(self, item_element):
        """Parse individual item element to extract video URL, tags, and description."""
        try:
            print("\n=== Parsing Item ===")
            
            # Print the HTML structure for debugging
            print("Item HTML structure:")
            print(item_element.prettify()[:500] + "..." if len(str(item_element)) > 500 else item_element.prettify())
            
            # Extract video URL from iframe
            iframe = item_element.find('iframe')
            if iframe:
                print(f"Found iframe with attributes: {iframe.attrs}")
            else:
                print("No iframe found in this item")
                # Try to find the video URL in the data attributes
                video_url = item_element.get('data-video-url', '')
                if video_url:
                    print(f"Found video URL in data attributes: {video_url}")
                else:
                    print("No video URL found in data attributes")
                
            video_url = iframe.get('src', '') if iframe else ''
            
            # Extract YouTube video ID
            video_id = self.extract_youtube_id(video_url)
            
            # Skip if we've already scraped this video
            if video_id in self.scraped_ids:
                print(f"Skipping duplicate video (ID: {video_id})")
                return None
                
            self.scraped_ids.add(video_id)
            print(f"Video URL: {video_url}")
            print(f"Video ID: {video_id}")

            # Extract tags - they are in spans with specific classes
            tags = []
            tag_spans = item_element.find_all('span', class_='py-2')
            print(f"Found {len(tag_spans)} tag spans")
            for tag_span in tag_spans:
                tag_text = tag_span.text.strip()
                if tag_text.startswith('#'):
                    tags.append(tag_text)
            print(f"Tags found: {', '.join(tags) if tags else 'No tags found'}")

            # Extract description - it's in a p tag with specific classes
            description_element = item_element.find('p', class_='text-neutral-900')
            if description_element:
                print(f"Found description element with text length: {len(description_element.text)}")
            else:
                print("No description element found")
                
            description = description_element.text.strip() if description_element else ''
            print(f"Description: {description[:100]}..." if len(description) > 100 else f"Description: {description}")

            print("=== Item Parsed Successfully ===\n")
            
            return {
                'video_url': video_url,
                'video_id': video_id,
                'tags': ','.join(tags),
                'description': description,
                'scraped_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error parsing item: {e}")
            return None

    def scrape_items(self):
        """Main scraping function to get all items."""
        items = []
        page_num = 1
        
        print("\nStarting scraping process...")
        print(f"Base URL: {self.base_url}")
        
        while True:
            print(f"\n=== Processing Page {page_num} ===")
            
            # Get the page with JavaScript content loaded
            html = self.get_page()
            if not html:
                break

            soup = BeautifulSoup(html, 'html.parser')
            
            # Find all item elements - they are in divs with class 'sequence-card'
            item_elements = soup.find_all('div', class_='sequence-card')
            print(f"\nFound {len(item_elements)} items to scrape on page {page_num}")
            
            # Print the HTML structure of the first item for debugging
            if item_elements:
                print("\nFirst item HTML structure:")
                print(item_elements[0].prettify()[:500] + "..." if len(str(item_elements[0])) > 500 else item_elements[0].prettify())
            
            for index, item_element in enumerate(item_elements, 1):
                print(f"\nProcessing item {index}/{len(item_elements)} on page {page_num}")
                
                item_data = self.parse_item(item_element)
                if item_data:
                    items.append(item_data)
                    print(f"✓ Item {index} added to results")
                else:
                    print(f"✗ Failed to parse item {index}")
                
                # Be nice to the server
                print("Waiting 1 second before next item...")
                time.sleep(1)
            
            # Look for the Next button
            next_button = self.find_next_button()
            if not next_button:
                print("\nNo Next button found - we've reached the end")
                break
                
            # Click the Next button
            print("\nClicking Next button...")
            next_button.click()
            page_num += 1
            
            # Wait for the new page to load
            time.sleep(2)
        
        return items

    def save_to_csv(self, items, filename='outlierdb_items.csv'):
        """Save scraped data to CSV."""
        if not items:
            logger.warning("No data to save")
            return
        
        print(f"\nSaving {len(items)} items to {filename}...")
        df = pd.DataFrame(items)
        df.to_csv(filename, index=False)
        print(f"✓ Data successfully saved to {filename}")

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'driver'):
            self.driver.quit()

def main():
    scraper = OutlierDBScraper()
    print("\n=== OutlierDB Scraper Started ===")
    
    try:
        items = scraper.scrape_items()
        scraper.save_to_csv(items)
        
        print(f"\n=== Scraping Completed ===")
        print(f"Total items scraped: {len(items)}")
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main() 