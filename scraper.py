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
            version_main=135  # Updated to match installed Chrome version
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

    def extract_video_info_from_card(self, card):
        """Extract video information from a sequence card."""
        try:
            # Initialize video info dictionary
            video_info = {
                'video_url': None,
                'video_id': None,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'saves': 0,
                'tags': [],
                'description': ''
            }

            # First try to get from iframe if it exists
            iframe = card.find('iframe')
            if iframe and 'youtube' in iframe.get('src', ''):
                video_info['video_url'] = iframe.get('src', '')
                video_info['video_id'] = self.extract_youtube_id(video_info['video_url'])

            # If no iframe, try to get from thumbnail img src
            if not video_info['video_id']:
                img = card.find('img', {'alt': 'YouTube Thumbnail'})
                if img:
                    src = img.get('src', '')
                    match = re.search(r'youtube\.com/vi/([^/]+)/', src)
                    if match:
                        video_id = match.group(1)
                        video_info['video_id'] = video_id
                        video_info['video_url'] = f"https://www.youtube-nocookie.com/embed/{video_id}"

            # Extract metadata (likes, comments, shares, saves)
            spans = card.find_all('span', class_='ml-1')
            for span in spans:
                try:
                    value = int(span.text.strip())
                    prev = span.find_previous_sibling()
                    if prev:
                        if 'M458.4 64.3' in str(prev):  # Heart/likes icon
                            video_info['likes'] = value
                        elif 'M256 32C114.6' in str(prev):  # Comment icon
                            video_info['comments'] = value
                        elif 'M237.66,106.35' in str(prev):  # Share icon
                            video_info['shares'] = value
                        elif 'M18 2H6c-1.103' in str(prev):  # Save icon
                            video_info['saves'] = value
                except ValueError:
                    continue

            # Extract tags
            tags = card.find_all('span', class_=lambda x: x and 'py-2 px-3' in x)
            video_info['tags'] = [tag.text.strip() for tag in tags if tag.text.strip().startswith('#')]

            # Extract description
            desc = card.find('p', class_='text-neutral-900')
            if desc:
                video_info['description'] = desc.text.strip()

            return video_info if video_info['video_id'] else None

        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            return None

    def handle_subscription_popup(self):
        """Check for and close the subscription popup if it appears."""
        try:
            # Look for the close button in the popup
            close_button = self.driver.find_element(By.CSS_SELECTOR, "button[class*='bg-red-300']")
            if close_button and close_button.is_displayed():
                print("Found subscription popup, closing it...")
                close_button.click()
                time.sleep(1)  # Wait for popup to close
                return True
        except Exception as e:
            # Popup not found or not visible, which is fine
            pass
        return False

    def wait_for_videos_to_load(self, timeout=10):
        """Wait for video iframes to load and replace thumbnails."""
        print("Waiting for videos to load...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Get all sequence cards
            cards = self.driver.find_elements(By.CLASS_NAME, "sequence-card")
            if not cards:
                time.sleep(1)
                continue
                
            # Count iframes vs thumbnails
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            thumbnails = self.driver.find_elements(By.CSS_SELECTOR, "img[alt='YouTube Thumbnail']")
            
            print(f"Found {len(iframes)} iframes and {len(thumbnails)} thumbnails")
            
            # If we have more iframes than thumbnails, videos have loaded
            if len(iframes) > len(thumbnails):
                print("✓ Videos loaded successfully")
                return True
                
            # Click each thumbnail to trigger video load
            for thumbnail in thumbnails:
                try:
                    if thumbnail.is_displayed():
                        self.driver.execute_script("arguments[0].click();", thumbnail)
                except:
                    pass
            
            time.sleep(1)
        
        print("Warning: Not all videos loaded completely")
        return False

    def scroll_to_bottom(self):
        """Scroll through the virtualized list and ensure all items are loaded."""
        print("\nScrolling through virtualized list...")
        
        # Track scroll state
        last_height = self.driver.execute_script("return document.documentElement.scrollHeight")
        window_height = self.driver.execute_script("return window.innerHeight")
        current_position = 0
        no_new_items_count = 0
        processed_indices = set()
        
        while no_new_items_count < 3:  # Try 3 times before assuming we're at the bottom
            # Get current items and their indices
            items = self.driver.find_elements(By.CLASS_NAME, "sequence-card")
            current_indices = {item.get_attribute('data-index') for item in items if item.get_attribute('data-index')}
            
            # Check if we found any new items
            new_indices = current_indices - processed_indices
            if new_indices:
                print(f"Found {len(new_indices)} new items")
                processed_indices.update(new_indices)
                no_new_items_count = 0
            else:
                no_new_items_count += 1
                print(f"No new items found (attempt {no_new_items_count}/3)")
            
            # Scroll in smaller increments (25% of window height)
            current_position += int(window_height * 0.25)
            print(f"Scrolling to position {current_position}")
            self.driver.execute_script(f"window.scrollTo(0, {current_position});")
            
            # Wait for content to load
            time.sleep(3)
            
            # Update scroll height in case more content was loaded
            new_height = self.driver.execute_script("return document.documentElement.scrollHeight")
            if new_height > last_height:
                print("Page height increased, resetting counter")
                last_height = new_height
                no_new_items_count = 0
            
            # Wait for videos to load
            self.wait_for_videos_to_load(timeout=5)
            
            # If we've reached the bottom, wait longer and check one more time
            if current_position >= last_height:
                print("Reached bottom, waiting for final items...")
                time.sleep(5)
                final_height = self.driver.execute_script("return document.documentElement.scrollHeight")
                if final_height > last_height:
                    last_height = final_height
                    no_new_items_count = 0
                else:
                    no_new_items_count += 1
        
        print(f"\nFinished scrolling, found {len(processed_indices)} total items")
        return True

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
            
            # Give extra time for initial load
            time.sleep(2)
            print("✓ Page loaded successfully")
            
            # Wait for videos to load
            self.wait_for_videos_to_load()
            
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
            
            # Initialize video info dictionary
            video_info = {
                'video_url': None,
                'video_id': None,
                'likes': 0,
                'comments': 0,
                'shares': 0,
                'saves': 0,
                'tags': [],
                'description': '',
                'data_index': item_element.get('data-index', ''),
                'scraped_at': datetime.now().isoformat()
            }
            
            # First try to get from iframe if it exists
            iframe = item_element.find('iframe')
            if iframe and 'youtube' in iframe.get('src', ''):
                video_info['video_url'] = iframe.get('src', '')
                video_info['video_id'] = self.extract_youtube_id(video_info['video_url'])
            
            # If no iframe, try to get from thumbnail img src
            if not video_info['video_id']:
                img = item_element.find('img', {'alt': 'YouTube Thumbnail'})
                if img:
                    src = img.get('src', '')
                    match = re.search(r'youtube\.com/vi/([^/]+)/', src)
                    if match:
                        video_id = match.group(1)
                        video_info['video_id'] = video_id
                        video_info['video_url'] = f"https://www.youtube-nocookie.com/embed/{video_id}"
            
            # Extract metadata (likes, comments, shares, saves)
            spans = item_element.find_all('span', class_='ml-1')
            for span in spans:
                try:
                    value = int(span.text.strip())
                    prev = span.find_previous_sibling()
                    if prev:
                        svg_path = prev.find('path')
                        if svg_path:
                            path_d = svg_path.get('d', '')
                            if 'M458.4 64.3' in path_d:  # Heart/likes icon
                                video_info['likes'] = value
                            elif 'M256 32C114.6' in path_d:  # Comment icon
                                video_info['comments'] = value
                            elif 'M237.66,106.35' in path_d:  # Share icon
                                video_info['shares'] = value
                            elif 'M18 2H6c-1.103' in path_d:  # Save icon
                                video_info['saves'] = value
                except ValueError:
                    continue
            
            # Extract tags
            tags = item_element.find_all('span', class_=lambda x: x and 'py-2 px-3' in x)
            video_info['tags'] = [tag.text.strip() for tag in tags if tag.text.strip().startswith('#')]
            
            # Extract description
            desc = item_element.find('p', class_='text-neutral-900')
            if desc:
                video_info['description'] = desc.text.strip()
            
            # Log the extracted information
            print(f"Video URL: {video_info['video_url']}")
            print(f"Video ID: {video_info['video_id']}")
            print(f"Likes: {video_info['likes']}")
            print(f"Comments: {video_info['comments']}")
            print(f"Shares: {video_info['shares']}")
            print(f"Saves: {video_info['saves']}")
            print(f"Tags found: {', '.join(video_info['tags'])}")
            print(f"Description: {video_info['description'][:100]}..." if len(video_info['description']) > 100 else f"Description: {video_info['description']}")
            
            return video_info if video_info['video_id'] else None
            
        except Exception as e:
            logger.error(f"Error parsing item: {e}")
            return None

    def scrape_items(self):
        """Main scraping function to get all items."""
        items = []
        processed_indices = set()  # Keep track of which items we've processed
        
        print("\nStarting scraping process...")
        print(f"Base URL: {self.base_url}")
        
        # Initial page load
        html = self.get_page()
        if not html:
            return items
        
        page = 1
        no_new_items_count = 0
        max_retries = 10  # Maximum number of attempts to find new items
        highest_index_seen = -1
        
        while no_new_items_count < max_retries:
            print(f"\nScrolling page {page}")
            
            # Get current visible items
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            visible_items = soup.find_all('div', {'data-index': True, 'class': lambda x: x and 'sequence-card' in x})
            
            # Sort items by data-index to process in order
            visible_items.sort(key=lambda x: int(x.get('data-index', '0')))
            
            print(f"Found {len(visible_items)} visible items")
            
            # Process visible items
            found_new = False
            for item in visible_items:
                try:
                    index = int(item.get('data-index', '-1'))
                    if index > highest_index_seen:
                        highest_index_seen = index
                    
                    if index not in processed_indices:
                        print(f"\nProcessing new item {index}")
                        item_data = self.parse_item(item)
                        if item_data:
                            items.append(item_data)
                            processed_indices.add(index)
                            print(f"✓ Item {index} added to results (Total: {len(items)})")
                            found_new = True
                        else:
                            print(f"✗ Failed to parse item {index}")
                except ValueError:
                    continue
            
            if found_new:
                no_new_items_count = 0
            else:
                no_new_items_count += 1
                print(f"No new items found (attempt {no_new_items_count}/{max_retries})")
            
            # Get the virtualized list container
            try:
                # Try different selectors to find the container
                container_selectors = [
                    "div[style*='position: relative'][style*='overflow: auto']",
                    "div[style*='will-change: transform']",
                    "div.overflow-auto"
                ]
                
                container = None
                for selector in container_selectors:
                    try:
                        container = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if container:
                            break
                    except:
                        continue
                
                if container:
                    # Get the total height from the inner div
                    total_height = self.driver.execute_script("""
                        const container = arguments[0];
                        const innerDiv = container.firstElementChild;
                        return innerDiv ? parseInt(innerDiv.style.height) : 0;
                    """, container)
                    
                    print(f"Container total height: {total_height}px")
                    
                    # Calculate current scroll and scroll to next section
                    current_scroll = self.driver.execute_script("return arguments[0].scrollTop;", container)
                    
                    # Calculate scroll amount based on container height
                    scroll_amount = 800  # Scroll by a larger amount to ensure new content loads
                    new_scroll = current_scroll + scroll_amount
                    
                    print(f"Current container scroll: {current_scroll}px")
                    print(f"Scrolling to: {new_scroll}px")
                    
                    # Scroll the container
                    self.driver.execute_script("""
                        const container = arguments[0];
                        const targetScroll = arguments[1];
                        container.scrollTo({
                            top: targetScroll,
                            behavior: 'smooth'
                        });
                    """, container, new_scroll)
                    
                    # Wait for content to load
                    time.sleep(3)
                    
                    # Check if we actually scrolled
                    new_actual_scroll = self.driver.execute_script("return arguments[0].scrollTop;", container)
                    print(f"New container scroll position: {new_actual_scroll}px")
                    
                    if new_actual_scroll <= current_scroll and not found_new:
                        print("Could not scroll further in container")
                        no_new_items_count += 1
                else:
                    print("Could not find virtualized list container")
                    no_new_items_count += 1
                    
            except Exception as e:
                print(f"Error scrolling container: {e}")
                no_new_items_count += 1
            
            # Handle subscription popup if it appears
            self.handle_subscription_popup()
            
            # Wait for videos to load
            self.wait_for_videos_to_load(timeout=5)
            
            # Save debug HTML periodically
            if len(items) % 10 == 0 and len(items) > 0:
                self.save_html(f"items_{len(items)}")
        
        print(f"\nFinished scraping {len(items)} items")
        print(f"Highest index seen: {highest_index_seen}")
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