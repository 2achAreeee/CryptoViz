# /shiny_app/app.py

import os
import json
import pandas as pd
import numpy as np
from shiny import App, render, ui, reactive, req, Session
import plotly.graph_objects as go
import requests
from datetime import timedelta, date
from data_manager import fetch_and_save_ticker_data


# --- Helper Function to Get Available Tickers ---
def get_available_tickers():
    app_script_dir = os.path.dirname(os.path.abspath(__file__)) # This should be /app in the container
    data_dir_absolute_path = os.path.join(app_script_dir, 'data')

    if not os.path.exists(data_dir_absolute_path):
        os.makedirs(data_dir_absolute_path, exist_ok=True)  # Create if it doesn't exist
        return []
    try:
        files = os.listdir(data_dir_absolute_path)
        tickers = sorted([f.replace('.csv', '') for f in files if f.endswith('.csv')])
        return tickers
    except Exception:
        return []


# Define global file path for tickers JSON correctly
_app_script_dir_global = os.path.dirname(os.path.abspath(__file__))
_project_root_dir_global = os.path.dirname(_app_script_dir_global)
TICKERS_FILE = os.path.join(_project_root_dir_global, 'data', 'crypto_tickers.json')

# --- Shiny App UI ---
app_ui = ui.page_navbar(
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
                         ui.hr(),
                         ui.h4("User-Driven Analysis"),
                         ui.input_text("add_ticker_symbol", "Add New Ticker:", placeholder="e.g., MATIC-USD"),
                         ui.input_action_button("add_ticker_button", "Add Ticker", class_="btn-success"),
                         ui.output_text_verbatim("add_ticker_status"),
                     ),
                     ui.output_ui("price_plot"),
                     ui.output_ui("forecast_display"),
                 ),
                 ),
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
def server(input, output, session: Session):
    available_tickers = reactive.Value(get_available_tickers())

    @reactive.Effect
    def _():
        tickers = available_tickers.get()
        current_forecast_selected = input.forecast_crypto_select()
        forecast_selected_to_set = None
        if current_forecast_selected in tickers:
            forecast_selected_to_set = current_forecast_selected
        elif tickers:
            forecast_selected_to_set = tickers[0]

        ui.update_select("forecast_crypto_select", choices=tickers, selected=forecast_selected_to_set)

        current_corr_selected = list(input.corr_crypto_select() or [])
        corr_selected_to_set = [t for t in current_corr_selected if t in tickers]
        if not corr_selected_to_set and len(tickers) >= 3:
            corr_selected_to_set = tickers[:3]
        elif not corr_selected_to_set and tickers:
            corr_selected_to_set = tickers[:1]
        ui.update_selectize("corr_crypto_select", choices=tickers, selected=corr_selected_to_set)

    forecast_result = reactive.Value(None)

    @reactive.Calc
    def load_forecast_data():
        ticker = input.forecast_crypto_select()
        req(ticker)
        # Path relative to app.py's directory
        app_script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(app_script_dir, 'data', f"{ticker}.csv")
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
        if df.empty or len(df) < 50:
            forecast_result.set({"error": "Not enough data to forecast."})
            return
        price_list = df['Close'].tail(100).tolist()
        api_url = os.environ.get("API_URL", "http://cryptoviz-api-container:5000/forecast")
        json_payload = {"close_prices": price_list}
        try:
            response = requests.post(api_url, json=json_payload, timeout=10)
            if response.status_code == 200:
                forecast_result.set(response.json())
            else:
                forecast_result.set({"error": f"API Error: {response.status_code} - {response.text}"})
        except requests.exceptions.RequestException as e:
            forecast_result.set({"error": f"Connection Error: {e}"})

    @output
    @render.ui
    def price_plot():
        df = load_forecast_data()
        if df.empty:  # Replaced req(not df.empty) for explicit UI feedback
            return ui.p("Data not available for the selected ticker.", style="color: orange;")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=df['Date'], y=df['Close'], mode='lines', name='Close Price', line=dict(color='#007bff')))
        result = forecast_result()
        if result and "predicted_price" in result:
            last_date = df['Date'].iloc[-1]
            forecast_date = last_date + timedelta(days=1)
            pred_price = result['predicted_price']
            lower_b = result['confidence_interval_lower']
            upper_b = result['confidence_interval_upper']
            fig.add_trace(
                go.Scatter(x=[forecast_date], y=[pred_price], mode='markers', marker=dict(color='red', size=10),
                           name='Forecast'))
            fig.add_trace(go.Scatter(
                x=[last_date, forecast_date, forecast_date, last_date],
                y=[df['Close'].iloc[-1], lower_b, upper_b, df['Close'].iloc[-1]],
                fill="toself",
                fillcolor="rgba(255,0,0,0.2)",
                line=dict(color="rgba(255,255,255,0)"),
                hoverinfo="skip",
                showlegend=False,
                name='Confidence Interval'
            ))
        fig.update_layout(title=f"Historical Close Price for {input.forecast_crypto_select()}", xaxis_title="Date",
                          yaxis_title="Price (USD)")
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs='cdn'))

    @output
    @render.ui
    def forecast_display():
        result = forecast_result()
        if not result: return ui.p("Click the button to generate a forecast.", class_="text-muted")
        if "error" in result: return ui.div(ui.h5("Error:", style="color: red;"), ui.p(result["error"]))
        if "predicted_price" in result:
            df = load_forecast_data()
            if df.empty: return ui.p("Cannot display comparison: data missing.", style="color: orange;")
            last_close = df['Close'].iloc[-1]
            price, lower, upper = result['predicted_price'], result['confidence_interval_lower'], result[
                'confidence_interval_upper']
            comparison_text, text_color = "", "gray"
            change_pct = ((price - last_close) / last_close) * 100 if last_close != 0 else 0
            if price > last_close:
                comparison_text, text_color = f"higher than yesterday's close of ${last_close:,.2f} ({change_pct:+.2f}%)", "green"
            else:
                comparison_text, text_color = f"lower than yesterday's close of ${last_close:,.2f} ({change_pct:+.2f}%)", "red"
            return ui.div(ui.h4("ARIMA Forecast"), ui.p(f"Predicted Next Day's Close: ${price:,.2f}"),
                          ui.p(f"This prediction is ",
                               ui.span(comparison_text, style=f"color: {text_color}; font-weight: bold;")),
                          ui.p(f"95% Confidence Interval: ${lower:,.2f} to ${upper:,.2f}"))

    # --- CORRELATION ANALYSIS LOGIC ---
    @reactive.Calc
    def calculate_correlation():
        from plotnine import ggplot, aes, geom_tile, geom_text, scale_fill_gradient2, labs, theme_minimal
        tickers = input.corr_crypto_select()
        timeframe = input.corr_timeframe()
        req(tickers and len(tickers) >= 2)
        days = int(timeframe[:-1])
        start_date_dt = date.today() - timedelta(days=days)
        log_returns_df = pd.DataFrame()

        app_script_dir = os.path.dirname(os.path.abspath(__file__))

        for ticker in tickers:
            try:
                file_path = os.path.join(app_script_dir, 'data', f"{ticker}.csv")
                df_read = pd.read_csv(file_path, index_col='Date', parse_dates=True)
                # Ensure index is DatetimeIndex for comparison
                df_filtered = df_read[df_read.index >= pd.to_datetime(start_date_dt)]
                log_returns_df[ticker] = df_filtered['Log_Return']
            except FileNotFoundError:
                continue
        return log_returns_df.corr()

    @output
    @render.plot
    def correlation_heatmap():
        from plotnine import ggplot, aes, geom_tile, geom_text, scale_fill_gradient2, labs, theme_minimal
        corr_matrix = calculate_correlation()
        req(corr_matrix is not None and not corr_matrix.empty)
        corr_melted = corr_matrix.reset_index().melt(id_vars='index')
        corr_melted.columns = ['Var1', 'Var2', 'value']
        heatmap = (ggplot(corr_melted, aes(x='Var1', y='Var2', fill='value')) + geom_tile(
            aes(width=0.95, height=0.95)) + geom_text(aes(label='round(value, 2)'), size=10) + scale_fill_gradient2(
            low="red", mid="white", high="blue", limits=(-1, 1)) + labs(
            title=f"Log Return Correlation ({input.corr_timeframe()})", x="", y="",
            fill="Correlation") + theme_minimal())
        return heatmap

    # --- ADD NEW TICKER LOGIC ---
    status_message = reactive.Value("")

    @reactive.Effect
    @reactive.event(input.add_ticker_button)
    def add_new_ticker():
        status_message.set("")
        new_ticker = input.add_ticker_symbol().strip().upper()
        if not new_ticker: status_message.set("Error: Ticker symbol cannot be empty."); return
        if new_ticker in available_tickers.get(): status_message.set(f"'{new_ticker}' is already in the list."); return

        success = fetch_and_save_ticker_data(new_ticker)

        if success:
            try:
                with open(TICKERS_FILE, 'r') as f:
                    existing_tickers = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                existing_tickers = []
            updated_set = set(existing_tickers)
            updated_set.add(new_ticker)
            with open(TICKERS_FILE, 'w') as f:
                json.dump(sorted(list(updated_set)), f, indent=4)

            new_list = get_available_tickers()  # Re-read from file system
            available_tickers.set(new_list)
            status_message.set(f"Success! Added {new_ticker} to the list.")
        else:
            status_message.set(f"Error: Failed to fetch data for {new_ticker}.")

    @output
    @render.text
    def add_ticker_status():
        return status_message.get()


app = App(app_ui, server)