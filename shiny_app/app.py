# /shiny_app/app.py

import os
import pandas as pd
from shiny import App, render, ui, reactive, req
from plotnine import ggplot, aes, geom_line, labs, theme_minimal, geom_point, geom_ribbon, geom_tile, geom_text, \
    scale_fill_gradient2
import requests
from datetime import timedelta, date


# --- Helper Function to Get Available Tickers ---
def get_available_tickers():
    data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
    if not os.path.exists(data_dir):
        return []
    return sorted([f.replace('.csv', '') for f in os.listdir(data_dir) if f.endswith('.csv')])


# --- Shiny App UI (Corrected) ---
app_ui = ui.page_navbar(
    # MODIFIED: Replaced ui.nav with the correct ui.nav_panel function
    ui.nav_panel("Forecasting",
                 ui.layout_sidebar(
                     ui.sidebar(
                         ui.h4("Forecast Controls"),
                         ui.input_select(
                             "forecast_crypto_select",
                             "Select Cryptocurrency:",
                             choices=get_available_tickers(),
                         ),
                         ui.input_action_button("get_forecast", "Generate Forecast", class_="btn-primary"),
                     ),
                     ui.output_plot("price_plot"),
                     ui.output_ui("forecast_display"),
                 ),
                 ),
    # MODIFIED: Replaced ui.nav with the correct ui.nav_panel function
    ui.nav_panel("Correlation Analysis",
                 ui.layout_sidebar(
                     ui.sidebar(
                         ui.h4("Correlation Controls"),
                         ui.input_selectize(
                             "corr_crypto_select",
                             "Select two or more cryptocurrencies:",
                             choices=get_available_tickers(),
                             selected=get_available_tickers()[:3],
                             multiple=True,
                         ),
                         ui.input_radio_buttons(
                             "corr_timeframe",
                             "Select timeframe:",
                             choices={"7D": "Last 7 Days", "30D": "Last 30 Days", "90D": "Last 90 Days"},
                             selected="30D",
                         ),
                     ),
                     ui.output_plot("correlation_heatmap"),
                 ),
                 ),
    title="CryptoViz Dashboard",
)


# --- Shiny App Server ---
def server(input, output, session):
    # --- FORECASTING LOGIC ---
    forecast_result = reactive.Value(None)

    @reactive.Calc
    def load_forecast_data():
        ticker = input.forecast_crypto_select()
        file_path = os.path.join(os.path.dirname(__file__), '..', 'data', f"{ticker}.csv")
        try:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True).reset_index()
            df = df.rename(columns={'index': 'Date'})
            return df
        except FileNotFoundError:
            return pd.DataFrame()

    @reactive.Effect
    @reactive.event(input.get_forecast)
    def get_forecast_from_api():
        df = load_forecast_data()
        price_list = df['Close'].tail(100).tolist()
        api_url = "http://127.0.0.1:5000/forecast"
        json_payload = {"close_prices": price_list}
        try:
            response = requests.post(api_url, json=json_payload, timeout=10)
            if response.status_code == 200:
                forecast_result.set(response.json())
            else:
                forecast_result.set({"error": f"API Error: {response.text}"})
        except requests.exceptions.RequestException:
            forecast_result.set({"error": "Connection Error: Could not connect to the API."})

    @output
    @render.plot
    def price_plot():
        df = load_forecast_data()
        req(not df.empty)
        plot = (ggplot(df, aes(x='Date')) + geom_line(aes(y='Close'), color="#007bff") + labs(
            title=f"Historical Close Price for {input.forecast_crypto_select()}", x="Date",
            y="Price (USD)") + theme_minimal())
        result = forecast_result()
        if result and "predicted_price" in result:
            last_date = df['Date'].iloc[-1]
            forecast_date = last_date + timedelta(days=1)
            forecast_df = pd.DataFrame({'Date': [forecast_date], 'predicted_price': [result['predicted_price']],
                                        'lower_bound': [result['confidence_interval_lower']],
                                        'upper_bound': [result['confidence_interval_upper']]})
            plot = (plot + geom_point(aes(y='predicted_price'), data=forecast_df, color='red', size=4) + geom_ribbon(
                aes(ymin='lower_bound', ymax='upper_bound'), data=forecast_df, fill='red', alpha=0.2))
        return plot

    @output
    @render.ui
    def forecast_display():
        result = forecast_result()
        if not result: return ui.p("Click the button to generate a forecast.", class_="text-muted")
        if "error" in result: return ui.div(ui.h5("Error:", style="color: red;"), ui.p(result["error"]))
        if "predicted_price" in result:
            price, lower, upper = result['predicted_price'], result['confidence_interval_lower'], result[
                'confidence_interval_upper']
            return ui.div(ui.h4("ARIMA Forecast"), ui.p(f"Predicted Next Day's Close: ${price:,.2f}"),
                          ui.p(f"95% Confidence Interval: ${lower:,.2f} to ${upper:,.2f}"))

    # --- CORRELATION ANALYSIS LOGIC ---
    @reactive.Calc
    def calculate_correlation():
        tickers = input.corr_crypto_select()
        timeframe = input.corr_timeframe()

        req(tickers and len(tickers) >= 2)

        days = int(timeframe[:-1])
        start_date = date.today() - timedelta(days=days)

        log_returns_df = pd.DataFrame()

        for ticker in tickers:
            try:
                file_path = os.path.join(os.path.dirname(__file__), '..', 'data', f"{ticker}.csv")
                df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
                df_filtered = df[df.index >= pd.to_datetime(start_date)]
                log_returns_df[ticker] = df_filtered['Log_Return']
            except FileNotFoundError:
                continue

        return log_returns_df.corr()

    @output
    @render.plot
    def correlation_heatmap():
        corr_matrix = calculate_correlation()
        req(corr_matrix is not None and not corr_matrix.empty)

        corr_melted = corr_matrix.reset_index().melt(id_vars='index')
        corr_melted.columns = ['Var1', 'Var2', 'value']

        heatmap = (
                ggplot(corr_melted, aes(x='Var1', y='Var2', fill='value'))
                + geom_tile(aes(width=0.95, height=0.95))
                + geom_text(aes(label='round(value, 2)'), size=10)
                + scale_fill_gradient2(low="red", mid="white", high="blue", limits=(-1, 1))
                + labs(
            title=f"Log Return Correlation ({input.corr_timeframe()})",
            x="", y="", fill="Correlation"
        )
                + theme_minimal()
        )
        return heatmap


# --- Create and Run the App ---
app = App(app_ui, server)