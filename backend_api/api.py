# /backend_api/api.py

import pandas as pd
from flask import Flask, request, jsonify
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_squared_error
from itertools import product
import warnings

# Suppress warnings to keep the output clean
warnings.filterwarnings("ignore")

# Initialize the Flask application
app = Flask(__name__)

def evaluate_arima_model(train, test, arima_order):
    try:
        model = ARIMA(train, order=arima_order)
        model_fit = model.fit()
        predictions = model_fit.forecast(steps=len(test))
        mse = mean_squared_error(test, predictions)
        return mse, model_fit
    except:
        return float('inf'), None


def generate_forecast(price_data, predict_ahead_days):
    """
    Takes a list of prices, trains an ARIMA model, and returns a forecast.
    """
    # Convert the list of prices into a pandas Series with a daily frequency
    close_prices = pd.Series(price_data)

    # Prepare train_test split (80% train, 20% test)
    train_size = int(len(close_prices) * 0.8)
    train, test = close_prices[:train_size], close_prices[train_size:]

    # Build and Train the ARIMA Model (p,d,q)
    results = []
    p_values = range(0,6)
    d_values = range(0,2)
    q_values = range(0,6)

    for p, d, q in product(p_values, d_values, q_values):
        arima_order = (p, d, q)
        mse, model_fit = evaluate_arima_model(train, test, arima_order)
        if model_fit is not None:
            results.append((arima_order, mse, model_fit))

    if not results:
        raise ValueError("No valid ARIMA model could be fit.")

    best_order, best_mse, best_model = min(results, key=lambda x: x[1])
    model_fit = best_model

    # Generate predictions for test + forecast horizon
    total_steps = len(test) + predict_ahead_days
    forecast = model_fit.get_forecast(steps=total_steps)

    # Extract the prediction and confidence interval
    predicted_all = forecast.predicted_mean.tolist()
    conf_int = forecast.conf_int(alpha=0.05)
    lower_bounds = conf_int.iloc[:, 0].tolist()
    upper_bounds = conf_int.iloc[:, 1].tolist()

    test_pred = predicted_all[:len(test)]
    forecast_pred = predicted_all[len(test):]
    forecast_lower = lower_bounds[len(test):]
    forecast_upper = upper_bounds[len(test):]

    # Return the results as a dictionary
    return {
        "train_size": train_size,
        "test_size": len(test),
        "test_pred": test_pred,
        "forecast_pred": forecast_pred,
        "predicted_price_nd": forecast_pred[0] if forecast_pred else None,
        "confidence_interval_lower": forecast_lower,
        "confidence_interval_upper": forecast_upper
    }

@app.route('/')
def index():
    return "CryptoViz ARIMA API"

# Define the API endpoint
@app.route('/forecast', methods=['POST'])
def handle_forecast():
    """
    Handles POST requests to the /forecast endpoint.
    Expects a JSON payload with historical close prices.
    """
    # Get the JSON data from the request body
    json_data = request.get_json() or {}
    forecast_days = json_data.get("predict_days", 1)

    # Basic validation
    if 'close_prices' not in json_data:
        return jsonify({"error": "Missing 'close_prices' in request body"}), 400

    prices = json_data['close_prices']

    if len(prices) < 50:  # ARIMA needs a reasonable amount of data
        return jsonify({"error": "Not enough data points to forecast. Need at least 50."}), 400

    try:
        forecast_days = int(forecast_days)
        if forecast_days < 1:
            forecast_days = 1
    except (TypeError, ValueError):
        forecast_days = 1

    try:
        # Generate the forecast using our function
        forecast_result = generate_forecast(prices, forecast_days)
        # Return the forecast as a JSON response
        return jsonify(forecast_result)
    except Exception as e:
        # Return a generic error message if something goes wrong
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# Main execution block to run the Flask app
if __name__ == '__main__':
    # Runs the app on localhost, port 5000
    app.run(debug=False, host='0.0.0.0',port=5001)
