import os
import json
import requests
from lxml import html

# --- Configuration ---
DATA_DIR = os.path.join('..', 'data')
TICKERS_FILE = os.path.join(DATA_DIR, 'crypto_tickers.json')
YAHOO_URL = "https://finance.yahoo.com/markets/crypto/all/?start=0&count=100"


def scrape_and_update_tickers(top_num=30):
    """
    Scrapes top crypto tickers and merges them with the existing list in the JSON file,
    ensuring no duplicates and that old tickers are not removed.
    """
    print(f"Fetching page content from {YAHOO_URL}...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(YAHOO_URL, headers=headers)
        response.raise_for_status()
    except requests.requests.exceptions.RequestException as e:
        print(f"Error fetching the page: {e}")
        return

    tree = html.fromstring(response.content)

    scraped_tickers = []
    print("Scraping new tickers using XPath...")

    for i in range(1, top_num + 1):
        try:
            xpath = f'/html/body/div[2]/main/section/section/section/article/section[1]/div/div[2]/div/table/tbody/tr[{i}]/td[1]/div/span/a/div/span/text()'
            ticker = tree.xpath(xpath)
            if ticker:
                cleaned_ticker = ticker[0].strip()
                scraped_tickers.append(cleaned_ticker)
                print(f"Found ticker #{i}: {cleaned_ticker}")
        except Exception as e:
            print(f"An error occurred at row {i}: {e}")
            break

    if not scraped_tickers:
        print("Scraping did not find any new tickers.")
        return

    # --- MODIFIED SECTION: Load, Merge, and Save ---

    # 1. Load existing tickers from the file, if it exists
    existing_tickers = []
    if os.path.exists(TICKERS_FILE):
        try:
            with open(TICKERS_FILE, 'r') as f:
                existing_tickers = json.load(f)
            print(f"\nLoaded {len(existing_tickers)} existing tickers from {TICKERS_FILE}.")
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Warning: Could not read existing tickers file. A new one will be created.")
            existing_tickers = []

    # 2. Combine old and new lists using a set to automatically remove duplicates
    combined_set = set(existing_tickers)
    combined_set.update(scraped_tickers)

    # 3. Convert the set back to a list (sorting is good practice for consistency)
    updated_tickers_list = sorted(list(combined_set))

    # 4. Save the new, comprehensive list back to the file
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TICKERS_FILE, 'w') as f:
        json.dump(updated_tickers_list, f, indent=4)

    newly_added_count = len(updated_tickers_list) - len(existing_tickers)
    print(f"\nMerge complete. Added {newly_added_count} new unique tickers.")
    print(f"Total tickers in updated file: {len(updated_tickers_list)}")


# --- Main Execution Block ---
if __name__ == '__main__':
    scrape_and_update_tickers(top_num=30)