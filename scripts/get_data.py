import os
import json
import time
import pandas as pd
import numpy as np
import yfinance as yf

# --- Configuration ---
DATA_DIR = os.path.join('..', 'data')
TICKERS_FILE = os.path.join(DATA_DIR, 'crypto_tickers.json')
START_DATE_DEFAULT = '2022-01-01'


def initial_download(ticker):
    """
    Performs a full historical data download for a new ticker.
    """
    print(f"Performing initial download for new ticker: {ticker}...")

    # Download data from the default start date to the present
    today = pd.to_datetime('today').strftime('%Y-%m-%d')
    try:
        data = yf.download(ticker, start=START_DATE_DEFAULT, end=today)
    except Exception as e:
        print(f"Could not download data for {ticker}. Error: {e}")
        return

    if isinstance(data.columns, pd.MultiIndex):
        print("Multi-level header detected. Removing extra 'Ticker' row...")
        # This keeps the top-level column names ('Close', 'High', etc.)
        # and discards the lower levels.
        data.columns = data.columns.get_level_values(0)

    if data.empty:
        print(f"No data downloaded for {ticker}. It may be a bad ticker symbol.")
        return

    # Calculate derived metrics and save the new file
    data['Log_Return'] = np.log(data['Close'] / data['Close'].shift(1))

    csv_path = os.path.join(DATA_DIR, f'{ticker}.csv')
    data.to_csv(csv_path)
    print(f"Successfully saved new data file to {csv_path}")


def update_existing_data(ticker, csv_path):
    """
    Updates an existing data file, refreshing the last known day and appending new records.
    """
    print(f"Updating existing data for ticker: {ticker}...")

    existing_df = pd.read_csv(csv_path, header=[0, 1], index_col=0, parse_dates=True)

    if existing_df.empty:
        print(f"Existing file for {ticker} is empty. Performing initial download instead.")
        initial_download(ticker)
        return

    last_date = existing_df.index.max()

    # --- MODIFIED LINE ---
    # Start download from the last saved date to create a one-day overlap.
    # This will refresh the last day's data if it was revised.
    start_date = last_date.strftime('%Y-%m-%d')
    today = pd.to_datetime('today').strftime('%Y-%m-%d')

    if start_date > today:
        print("Data is already up-to-date.")
        return

    print(f"Last entry is from {last_date.date()}. Refreshing data from {start_date}...")
    try:
        new_data = yf.download(ticker, start=start_date, end=today)
    except Exception as e:
        print(f"Could not download new data for {ticker}. Error: {e}")
        return

    if isinstance(new_data.columns, pd.MultiIndex):
        print("Multi-level header detected. Removing extra 'Ticker' row...")
        new_data.columns = new_data.columns.get_level_values(0)

    if new_data.empty or len(new_data) <= 1:
        print("No new daily records were found.")
        return

    print("Merging new records...")
    combined_df = pd.concat([existing_df, new_data])
    combined_df = combined_df.sort_index()

    # This command now becomes even more important. For the overlapping date,
    # it will discard the old record ('first') and keep the new one ('last').
    combined_df = combined_df[~combined_df.index.duplicated(keep='last')]

    combined_df['Log_Return'] = np.log(combined_df['Close'] / combined_df['Close'].shift(1))

    combined_df.to_csv(csv_path)
    print(f"Successfully updated data for {ticker}.")


def process_all_tickers():
    """
    Main controller function to orchestrate the data update process.
    """
    try:
        with open(TICKERS_FILE, 'r') as f:
            tickers = json.load(f)
        print(f"Loaded {len(tickers)} tickers to process from {TICKERS_FILE}.")
    except FileNotFoundError:
        print(f"Error: Ticker file not found at {TICKERS_FILE}.")
        print("Please run the scrape_tickers.py script first.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)

    for ticker in tickers:
        print(f"\n--- Processing: {ticker} ---")
        csv_path = os.path.join(DATA_DIR, f'{ticker}.csv')

        # Decide which function to call based on file existence
        if os.path.exists(csv_path):
            update_existing_data(ticker, csv_path)
        else:
            initial_download(ticker)

        time.sleep(1)  # Be respectful to the API server

    print("\n--- All data updates are complete! ---")


# --- Main Execution Block ---
if __name__ == '__main__':
    # existing_df = pd.read_csv("../data/BTC-USD.csv", header=[0, 1], index_col=0, parse_dates=True)
    # print(existing_df['Close'])
    # new_data = yf.download("BTC-USD", start='2023-01-01', end='2024-01-01')
    # print(new_data)
    # combined_df = pd.concat([existing_df, new_data])
    # print(combined_df)
    process_all_tickers()

    # update_existing_data("BTC-USD", "../data/BTC-USD.csv")
    # initial_download("BTC-USD")
