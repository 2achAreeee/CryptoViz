import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import date

# Define the data directory relative to this file's location
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
START_DATE_DEFAULT = '2022-01-01'

def fetch_and_save_ticker_data(ticker_symbol: str) -> bool:
    """
    Downloads, processes, and saves historical data for a single ticker.
    Returns True on success, False on failure.
    """
    print(f"Data Manager: Fetching data for {ticker_symbol}...")
    try:
        data = yf.download(ticker_symbol, start=START_DATE_DEFAULT, end=date.today())
        if data.empty:
            raise ValueError("No data returned from yfinance. Ticker may be invalid.")

        # Clean the header if it's a multi-level index
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Calculate derived metrics
        data['Log_Return'] = np.log(data['Close'] / data['Close'].shift(1))

        # Save the data
        os.makedirs(DATA_DIR, exist_ok=True)
        file_path = os.path.join(DATA_DIR, f"{ticker_symbol}.csv")
        data.to_csv(file_path)

        print(f"Data Manager: Successfully saved data for {ticker_symbol}.")
        return True

    except Exception as e:
        print(f"Data Manager: Error fetching data for {ticker_symbol}. Reason: {e}")
        return False