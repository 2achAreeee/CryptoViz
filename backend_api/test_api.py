# /test_api.py
import requests
import pandas as pd

# 1. Load some test data from our CSV file
try:
    data = pd.read_csv('../data/BTC-USD.csv')
    # Take the last 100 days of close prices
    price_list = data['Close'].tail(100).tolist()
except FileNotFoundError:
    print("Error: BTC-USD.csv not found. Please ensure the data files exist.")
    exit()

# 2. Define the API endpoint URL
api_url = "http://127.0.0.1:5000/forecast"

# 3. Prepare the JSON data payload
# This matches the format our Flask API expects [cite: 3]
json_payload = {
    "close_prices": price_list
}

# 4. Send the POST request
print("Sending data to the forecast API...")
response = requests.post(api_url, json=json_payload)

# 5. Print the results
if response.status_code == 200:
    print("\n--- Forecast Received ---")
    print(response.json())
else:
    print("\n--- Error ---")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")