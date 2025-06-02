# /backend_api/api.py

import pandas as pd
from flask import Flask, request, jsonify
from statsmodels.tsa.arima.model import ARIMA
import warnings

# Suppress warnings to keep the output clean
warnings.filterwarnings("ignore")

# Initialize the Flask application
app = Flask(__name__)


def generate_forecast(price_data):
    """
    Takes a list of prices, trains an ARIMA model, and returns a forecast.
    """
    # Convert the list of prices into a pandas Series with a daily frequency
    close_prices = pd.Series(price_data)

    # Build and Train the ARIMA Model (p,d,q)
    # Using a standard order of ARIMA(5,1,0) as a starting point
    model = ARIMA(close_prices, order=(5, 1, 0))
    model_fit = model.fit()

    # Generate Forecast for the next step
    forecast = model_fit.get_forecast(steps=1)

    # Extract the prediction and confidence interval
    predicted_price = forecast.predicted_mean.iloc[0]
    conf_int = forecast.conf_int(alpha=0.05).iloc[0]
    lower_bound = conf_int[0]
    upper_bound = conf_int[1]

    # Return the results as a dictionary
    return {
        "predicted_price": predicted_price,
        "confidence_interval_lower": lower_bound,
        "confidence_interval_upper": upper_bound
    }


# Define the API endpoint
@app.route('/forecast', methods=['POST'])
def handle_forecast():
    """
    Handles POST requests to the /forecast endpoint.
    Expects a JSON payload with historical close prices.
    """
    # Get the JSON data from the request body
    json_data = request.get_json()

    # Basic validation
    if not json_data or 'close_prices' not in json_data:
        return jsonify({"error": "Missing 'close_prices' in request body"}), 400

    prices = json_data['close_prices']

    if len(prices) < 50:  # ARIMA needs a reasonable amount of data
        return jsonify({"error": "Not enough data points to forecast. Need at least 50."}), 400

    try:
        # Generate the forecast using our function
        forecast_result = generate_forecast(prices)
        # Return the forecast as a JSON response
        return jsonify(forecast_result)
    except Exception as e:
        # Return a generic error message if something goes wrong
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# Main execution block to run the Flask app
if __name__ == '__main__':
    # Runs the app on localhost, port 5000
    app.run(debug=True, port=5000)