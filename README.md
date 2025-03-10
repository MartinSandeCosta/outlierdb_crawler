# OutlierDB Scraper

A Python web scraper designed to extract BJJ (Brazilian Jiu-Jitsu) video sequences from OutlierDB.com. This scraper collects video URLs, associated tags, and descriptions from the platform.

## Features

- Automated scraping of BJJ video sequences
- Handles JavaScript-loaded content
- Extracts video URLs, tags, and descriptions
- Saves data to CSV format
- Duplicate detection to avoid repeated entries
- Progress tracking and detailed logging

## Prerequisites

- Python 3.11 or higher
- Google Chrome browser installed
- Git (for cloning the repository)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/outlierdb_scrap.git
cd outlierdb_scrap
```

2. Create and activate a virtual environment:
```bash
python3 -m venv outlierdb_env
source outlierdb_env/bin/activate  # On macOS/Linux
# or
.\outlierdb_env\Scripts\activate  # On Windows
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Make sure your virtual environment is activated:
```bash
source outlierdb_env/bin/activate  # On macOS/Linux
# or
.\outlierdb_env\Scripts\activate  # On Windows
```

2. Run the scraper:
```bash
python3 scraper.py
```

The scraper will:
- Load the OutlierDB website
- Scroll through the page to load all content
- Extract video URLs, tags, and descriptions
- Save the data to `outlierdb_items.csv`

## Output

The scraper generates a CSV file (`outlierdb_items.csv`) with the following columns:
- `video_url`: The URL of the video sequence
- `tags`: Comma-separated list of hashtags associated with the video
- `description`: Text description of the sequence
- `scraped_at`: Timestamp of when the data was scraped

## Project Structure

```
outlierdb_scrap/
├── README.md
├── requirements.txt
├── scraper.py
└── outlierdb_items.csv (generated)
```

## Technical Details

- Uses `undetected-chromedriver` for browser automation
- Implements scrolling to handle infinite scroll pagination
- Includes error handling and logging
- Respects website load times with appropriate delays

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This scraper is for educational purposes only. Please respect the website's terms of service and robots.txt file. Consider implementing appropriate delays between requests to avoid overwhelming the server. 