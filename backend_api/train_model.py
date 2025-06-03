import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import warnings

warnings.filterwarnings("ignore")


def generate_forecast(ticker_symbol):
    """
    Loads data for a given ticker, trains an ARIMA model,
    and returns a one-step-ahead forecast.
    """
    print(f"--- Generating forecast for {ticker_symbol} ---")

    # 1. Load the Data
    try:
        # Construct the file path and load the data
        file_path = f'../data/{ticker_symbol}.csv'
        data = pd.read_csv(file_path, index_col='Date', parse_dates=True)
        # Ensure the data is sorted by date
        data = data.asfreq('D')  # Ensure daily frequency, filling missing days with NaN
        # Forward-fill missing values, common for crypto data (weekends, etc.)
        data.fillna(method='ffill', inplace=True)

        # Select the 'Close' price for modeling
        close_prices = data['Close']
        print(f"Loaded {len(close_prices)} data points.")

    except FileNotFoundError:
        print(f"Error: Data file not found for {ticker_symbol} at {file_path}")
        return

    # 2. Build and Train the ARIMA Model
    model = ARIMA(close_prices, order=(5, 1, 0))

    print("Training ARIMA(5,1,0) model... This may take a moment.")
    model_fit = model.fit()
    print("Model training complete.")

    # 3. Generate Forecast
    # We are forecasting one step into the future.
    forecast = model_fit.get_forecast(steps=1)

    # Extract the predicted mean value (the forecasted price)
    predicted_price = forecast.predicted_mean.iloc[0]

    # Extract the confidence interval
    conf_int = forecast.conf_int(alpha=0.05).iloc[0]  # 95% confidence interval
    lower_bound = conf_int[0]
    upper_bound = conf_int[1]

    print("\n--- Forecast Results ---")
    print(f"Predicted Next Day's Close Price: ${predicted_price:,.2f}")
    print(f"95% Confidence Interval: ${lower_bound:,.2f} to ${upper_bound:,.2f}")

    return predicted_price, conf_int


# --- Main Execution Block ---
if __name__ == '__main__':
    generate_forecast('BTC-USD')