# /shiny_app/app.py

import os
import json
import pandas as pd
import numpy as np
from shiny import App, render, ui, reactive, req, Session
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import timedelta, date
from data_manager import fetch_and_save_ticker_data


# --- Helper Function to Get Available Tickers ---
def get_data_dir():
    app_script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root_dir = os.path.dirname(app_script_dir)
    return os.path.join(project_root_dir, 'data')


def get_available_tickers():
    data_dir_absolute_path = get_data_dir()

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
    ui.nav_panel("Candlestick",
                 ui.layout_sidebar(
                     ui.sidebar(
                         ui.h4("Candlestick Controls"),
                         ui.input_select(
                             "candle_crypto_select",
                             "Select Cryptocurrency:",
                             choices=get_available_tickers(),
                         ),
                         ui.input_radio_buttons(
                             "candle_timeframe",
                             "Timeframe:",
                             choices={"30D": "Last 30 Days", "90D": "Last 90 Days", "180D": "Last 180 Days",
                                      "365D": "Last 365 Days", "MAX": "Max"},
                             selected="180D",
                         ),
                         ui.input_selectize(
                             "candle_ma_windows",
                             "Moving Averages:",
                             choices=["7", "20", "50", "100", "200"],
                             selected=["20", "50"],
                             multiple=True,
                         ),
                     ),
                     ui.output_ui("candlestick_plot"),
                 ),
                 ),
    ui.nav_panel("Forecasting",
                 ui.layout_sidebar(
                     ui.sidebar(
                         ui.h4("Forecast Controls"),
                         ui.input_select(
                             "forecast_crypto_select",
                             "Select Cryptocurrency:",
                             choices=get_available_tickers(),
                         ),
                         ui.input_numeric("predict_ahead_days", "Prediction Days Ahead:", max=30, min=1, value=1),
                         ui.input_action_button("forecast", "Forecast", class_="btn-primary"),
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
        current_candle_selected = input.candle_crypto_select()
        candle_selected_to_set = None
        if current_candle_selected in tickers:
            candle_selected_to_set = current_candle_selected
        elif tickers:
            candle_selected_to_set = tickers[0]
        ui.update_select("candle_crypto_select", choices=tickers, selected=candle_selected_to_set)

    forecast_result = reactive.Value(None)

    @reactive.Effect
    def clear_forecast_on_ticker_change():
        input.forecast_crypto_select()
        forecast_result.set(None)

    @reactive.Calc
    def load_forecast_data():
        ticker = input.forecast_crypto_select()
        req(ticker)
        # Path relative to project root
        file_path = os.path.join(get_data_dir(), f"{ticker}.csv")
        try:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True).reset_index()
            df = df.rename(columns={'index': 'Date'})
            return df
        except FileNotFoundError:
            return pd.DataFrame()

    @reactive.Effect
    @reactive.event(input.forecast)
    def get_forecast_from_api():
        df = load_forecast_data()
        forecast_day = input.predict_ahead_days()
        if df.empty or len(df) < 50:
            forecast_result.set({"error": "Not enough data to forecast."})
            return
        price_list = df['Close'].tail(120).tolist()
        api_url = os.environ.get("API_URL", "http://cryptoviz-api-container:5000/forecast")
        json_payload = {"close_prices": price_list, "predict_days": forecast_day}
        try:
            response = requests.post(api_url, json=json_payload, timeout=30)
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
        df_hist = df.iloc[:-120]
        df_send = df.tail(120)
        if df.empty:  # Replaced req(not df.empty) for explicit UI feedback
            return ui.p("Data not available for the selected ticker.", style="color: orange;")

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(x=df_hist['Date'], y=df_hist['Close'], mode='lines',
                       name='Train', line=dict(color='#1f77b4')))
        result = forecast_result()
        if result and "train_size" in result:
            train_size = result.get("train_size", 0)
            test_size = result.get("test_size", 0)
            test_pred = result.get("test_pred", [])
            forecast_pred = result.get("forecast_pred", [])
            lower_b = result.get("confidence_interval_lower", [])
            upper_b = result.get("confidence_interval_upper", [])

            train_df = df_send.iloc[:train_size]
            test_df = df_send.iloc[train_size:train_size + test_size]

            if not train_df.empty:
                fig.add_trace(
                    go.Scatter(x=train_df['Date'], y=train_df['Close'], mode='lines',
                               name='Train', line=dict(color='#1f77b4')))
            if not test_df.empty:
                fig.add_trace(
                    go.Scatter(x=test_df['Date'], y=test_df['Close'], mode='lines',
                               name='Test', line=dict(color='#ff7f0e')))

            if test_df.shape[0] and test_pred:
                steps = min(len(test_df), len(test_pred))
                fig.add_trace(
                    go.Scatter(x=test_df['Date'].iloc[:steps], y=test_pred[:steps], mode='lines',
                               name='Test Prediction', line=dict(color='#2ca02c', dash='dash')))

            if forecast_pred:
                last_date = df['Date'].iloc[-1]
                steps = min(len(forecast_pred), len(lower_b), len(upper_b))
                forecast_dates = [last_date + timedelta(days=i) for i in range(1, steps + 1)]
                fig.add_trace(
                    go.Scatter(x=forecast_dates, y=forecast_pred[:steps], mode='lines+markers',
                               marker=dict(color='red', size=6), line=dict(color='red'), name='Forecast'))
                if steps:
                    fig.add_trace(
                        go.Scatter(
                            x=forecast_dates + forecast_dates[::-1],
                            y=upper_b[:steps] + lower_b[:steps][::-1],
                            fill="toself",
                            fillcolor="rgba(255,0,0,0.2)",
                            line=dict(color="rgba(255,255,255,0)"),
                            hoverinfo="skip",
                            showlegend=False,
                            name='Confidence Interval'
                        )
                    )

            if train_df.shape[0] and test_df.shape[0]:
                split_date = test_df['Date'].iloc[0]
                fig.add_vline(x=split_date, line_dash="dot", line_color="gray")
        fig.update_layout(title=f"Historical Close Price for {input.forecast_crypto_select()}", xaxis_title="Date",
                          yaxis_title="Price (USD)")
        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs='cdn'))

    @output
    @render.ui
    def candlestick_plot():
        ticker = input.candle_crypto_select()
        if not ticker:
            return ui.p("Select a ticker to view the candlestick chart.", class_="text-muted")
        file_path = os.path.join(get_data_dir(), f"{ticker}.csv")
        try:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True).reset_index()
            df = df.rename(columns={'index': 'Date'})
        except FileNotFoundError:
            return ui.p("Data not available for the selected ticker.", style="color: orange;")

        if df.empty:
            return ui.p("Data not available for the selected ticker.", style="color: orange;")

        timeframe = input.candle_timeframe()
        if timeframe != "MAX":
            days = int(timeframe[:-1])
            start_date_dt = date.today() - timedelta(days=days)
            df = df[df['Date'] >= pd.to_datetime(start_date_dt)]

        if df.empty:
            return ui.p("No data available for the selected timeframe.", style="color: orange;")

        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.7, 0.3],
            subplot_titles=(f"{ticker} Candlestick", "Volume")
        )

        fig.add_trace(
            go.Candlestick(
                x=df['Date'],
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name="Price"
            ),
            row=1, col=1
        )

        ma_windows = [int(w) for w in (input.candle_ma_windows() or [])]
        for window in ma_windows:
            if window > 1:
                df[f"MA_{window}"] = df['Close'].rolling(window=window).mean()
                fig.add_trace(
                    go.Scatter(
                        x=df['Date'],
                        y=df[f"MA_{window}"],
                        mode='lines',
                        name=f"MA {window}"
                    ),
                    row=1, col=1
                )
        fig.add_trace(
            go.Bar(
                x=df['Date'],
                y=df['Volume'],
                name="Volume",
                marker_color="rgba(100, 149, 237, 0.6)"
            ),
            row=2, col=1
        )

        fig.update_layout(
            title=f"{ticker} Price and Volume",
            xaxis_title="Date",
            yaxis_title="Price (USD)",
            xaxis2_title="Date",
            yaxis2_title="Volume",
            xaxis_rangeslider_visible=False,
            height=700,
            showlegend=False
        )

        return ui.HTML(fig.to_html(full_html=False, include_plotlyjs='cdn'))


    @output
    @render.ui
    def forecast_display():
        result = forecast_result()
        if not result: return ui.p("Click the button to generate a forecast.", class_="text-muted")
        if "error" in result: return ui.div(ui.h5("Error:", style="color: red;"), ui.p(result["error"]))
        if "forecast_pred" in result:
            df = load_forecast_data()
            if df.empty: return ui.p("Cannot display comparison: data missing.", style="color: orange;")
            last_close = df['Close'].iloc[-1]
            predicted_prices = result['forecast_pred']
            lower_list = result['confidence_interval_lower']
            upper_list = result['confidence_interval_upper']
            if not predicted_prices:
                return ui.p("Forecast returned no data.", style="color: orange;")
            price = predicted_prices[-1]
            lower = lower_list[-1] if lower_list else None
            upper = upper_list[-1] if upper_list else None
            comparison_text, text_color = "", "gray"
            change_pct = ((price - last_close) / last_close) * 100 if last_close != 0 else 0
            if price > last_close:
                comparison_text, text_color = f"higher than yesterday's close of ${last_close:,.2f} ({change_pct:+.2f}%)", "green"
            else:
                comparison_text, text_color = f"lower than yesterday's close of ${last_close:,.2f} ({change_pct:+.2f}%)", "red"
            return ui.div(ui.h4("ARIMA Forecast"),
                          ui.p(f"Predicted Close on Day {len(predicted_prices)}: ${price:,.2f}"),
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

        for ticker in tickers:
            try:
                file_path = os.path.join(get_data_dir(), f"{ticker}.csv")
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
