import time
import ccxt
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Streamlit Page Setup
st.set_page_config(
    page_title="Crypto RSI + MACD + EMA Scanner",
    page_icon="📈",
    layout="wide",
)


def calculate_rsi(df, period=14):
    """RSI ගණනය කිරීම"""
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(df, fast=12, slow=26, signal=9):
    """MACD ගණනය කිරීම"""
    exp1 = df["close"].ewm(span=fast, adjust=False).mean()
    exp2 = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    return macd_line, signal_line, macd_hist


def fetch_coin_data(symbol, timeframe="1h", limit=100):
    """Binance එකෙන් දත්ත ලබාගෙන EMA 20/50, RSI සහ MACD ගණනය කිරීම"""
    exchange = ccxt.binance()
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(
        ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    # Technical Indicators
    df["EMA_20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA_50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["RSI"] = calculate_rsi(df)
    df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = calculate_macd(df)

    return df


def plot_interactive_chart(df, symbol):
    """Candlestick (with EMA 20 & 50), RSI, සහ MACD Plotly Chart එක ඇඳීම"""
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            f"{symbol} Candlestick Chart with EMA 20 & EMA 50",
            "RSI (14)",
            "MACD",
        ),
        row_heights=[0.5, 0.25, 0.25],
    )

    # 1. Candlestick Chart
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )

    # EMA 20 Line (Orange)
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["EMA_20"],
            line=dict(color="orange", width=1.5),
            name="EMA 20",
        ),
        row=1,
        col=1,
    )

    # EMA 50 Line (Cyan / Light Blue)
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["EMA_50"],
            line=dict(color="#00E5FF", width=1.5),
            name="EMA 50",
        ),
        row=1,
        col=1,
    )

    # 2. RSI Chart
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["RSI"],
            line=dict(color="purple", width=2),
            name="RSI",
        ),
        row=2,
        col=1,
    )

    # RSI Overbought/Oversold Limits
    fig.add_hline(
        y=70, line_dash="dash", line_color="red", row=2, col=1, opacity=0.5
    )
    fig.add_hline(
        y=30, line_dash="dash", line_color="green", row=2, col=1, opacity=0.5
    )

    # 3. MACD Chart
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["MACD"],
            line=dict(color="blue", width=1.5),
            name="MACD",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["MACD_Signal"],
            line=dict(color="orange", width=1.5),
            name="Signal Line",
        ),
        row=3,
        col=1,
    )

    colors = ["green" if val >= 0 else "red" for val in df["MACD_Hist"]]
    fig.add_trace(
        go.Bar(
            x=df["timestamp"],
            y=df["MACD_Hist"],
            marker_color=colors,
            name="Histogram",
        ),
        row=3,
        col=1,
    )

    # Layout Customization
    fig.update_layout(
        height=800,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
        margin=dict(l=20, r=20, t=60, b=20),
    )

    return fig


def scan_market(symbols, timeframe, oversold, overbought):
    """Market Scan කර දත්ත ලබාගැනීම"""
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(symbols)
    for idx, symbol in enumerate(symbols):
        status_text.text(f"Scanning {symbol} ({idx+1}/{total})...")
        try:
            df = fetch_coin_data(symbol, timeframe=timeframe)
            latest = df.iloc[-1]

            price = latest["close"]
            rsi_val = round(latest["RSI"], 2)
            macd_val = round(latest["MACD"], 4)
            macd_sig = round(latest["MACD_Signal"], 4)
            ema_20 = round(latest["EMA_20"], 2)
            ema_50 = round(latest["EMA_50"], 2)

            is_buy = (rsi_val <= oversold) and (macd_val > macd_sig)
            is_sell = (rsi_val >= overbought) and (macd_val < macd_sig)

            status = (
                "🟢 STRONG BUY"
                if is_buy
                else ("🔴 STRONG SELL" if is_sell else "⚪ NEUTRAL")
            )

            results.append(
                {
                    "Coin": symbol,
                    "Price ($)": price,
                    "EMA 20": ema_20,
                    "EMA 50": ema_50,
                    "RSI": rsi_val,
                    "MACD": macd_val,
                    "MACD Signal": macd_sig,
                    "Status": status,
                }
            )
            time.sleep(0.05)
        except Exception as e:
            st.warning(f"Could not fetch {symbol}: {e}")

        progress_bar.progress((idx + 1) / total)

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# ---------------- HEADER ----------------
st.title("📈 Crypto Multi-Coin Scanner & Pro Dashboard")
st.caption(
    "RSI + MACD Dual Confirmation with EMA 20 / EMA 50 Trend Lines (Binance Data)"
)
st.markdown("---")

# ---------------- SIDEBAR CONTROLS ----------------
st.sidebar.header("⚙️ Scanner Settings")

timeframe = st.sidebar.selectbox(
    "Timeframe එක තෝරන්න", options=["15m", "1h", "4h", "1d"], index=1
)
rsi_oversold = st.sidebar.slider("RSI Oversold Limit (BUY)", 10, 45, 35)
rsi_overbought = st.sidebar.slider("RSI Overbought Limit (SELL)", 55, 90, 65)

default_coins = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "AVAX/USDT",
    "DOT/USDT",
    "LINK/USDT",
    "NEAR/USDT",
    "SUI/USDT",
]

selected_coins = st.sidebar.multiselect(
    "Scan කිරීමට අවශ්‍ය Coins",
    options=default_coins + ["APT/USDT", "PEPE/USDT", "SHIB/USDT", "INJ/USDT"],
    default=default_coins,
)

scan_button = st.sidebar.button("🚀 Start Scan", use_container_width=True)

# ---------------- MAIN DASHBOARD ----------------
if scan_button or "scan_data" in st.session_state:

    if scan_button or "scan_data" not in st.session_state:
        if not selected_coins:
            st.error("කරුණාකර අවම වශයෙන් එක Coin එකක්වත් තෝරන්න!")
        else:
            st.session_state["scan_data"] = scan_market(
                selected_coins, timeframe, rsi_oversold, rsi_overbought
            )

    df = st.session_state.get("scan_data")

    if df is not None and not df.empty:
        # Metrics / Summary
        buy_count = len(df[df["Status"] == "🟢 STRONG BUY"])
        sell_count = len(df[df["Status"] == "🔴 STRONG SELL"])
        neutral_count = len(df[df["Status"] == "⚪ NEUTRAL"])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Scanned", len(df))
        col2.metric("🟢 Strong BUY Signals", buy_count)
        col3.metric("🔴 Strong SELL Signals", sell_count)
        col4.metric("⚪ Neutral Coins", neutral_count)

        st.markdown("---")

        # Tables Section
        tab1, tab2, tab3, tab4 = st.tabs(
            [
                "🎯 Confirmed Signals",
                "🟢 BUY Signals",
                "🔴 SELL Signals",
                "📊 All Scanned Coins",
            ]
        )

        with tab1:
            filtered_df = df[df["Status"] != "⚪ NEUTRAL"]
            if filtered_df.empty:
                st.info(
                    "⚪ දැනට Confirm වූ කිසිදු BUY හෝ SELL Signal එකක් නොමැත."
                )
            else:
                st.dataframe(filtered_df, use_container_width=True)

        with tab2:
            buys_df = df[df["Status"] == "🟢 STRONG BUY"]
            if buys_df.empty:
                st.info("🟢 BUY Signals කිසිවක් නැත.")
            else:
                st.dataframe(buys_df, use_container_width=True)

        with tab3:
            sells_df = df[df["Status"] == "🔴 STRONG SELL"]
            if sells_df.empty:
                st.info("🔴 SELL Signals කිසිවක් නැත.")
            else:
                st.dataframe(sells_df, use_container_width=True)

        with tab4:
            st.dataframe(df, use_container_width=True)

        st.markdown("---")

        # ---------------- DETAILED CHART SECTION ----------------
        st.subheader("📊 Interactive Chart Analysis with Moving Averages")

        scanned_coin_list = df["Coin"].tolist()
        selected_chart_coin = st.selectbox(
            "Chart එක පරීක්ෂා කිරීමට Coin එක තෝරන්න:", options=scanned_coin_list
        )

        if selected_chart_coin:
            with st.spinner(f"Loading chart for {selected_chart_coin}..."):
                coin_df = fetch_coin_data(
                    selected_chart_coin, timeframe=timeframe, limit=100
                )
                fig = plot_interactive_chart(coin_df, selected_chart_coin)
                st.plotly_chart(fig, use_container_width=True)

else:
    st.info(
        "👈 Scan එක ආරම්භ කිරීමට වම් පස ඇති **'Start Scan'** Button එක Click කරන්න."
    )
# Crypto RSI + MACD + EMA Scanner & Pro Dashboard

An advanced, real-time multi-coin cryptocurrency scanning tool built using Python, Streamlit, and the CCXT library. This dashboard fetches live market data directly from the Binance exchange to help traders quickly analyze and identify potential market trends across multiple trading pairs simultaneously.

### Key Features:
- **Multi-Coin Scanning:** Scan popular assets like BTC, ETH, SOL, BNB, and more at once.
- **Dual Confirmation Strategy:** Generates dynamic BUY/SELL/NEUTRAL signals using a combination of RSI (Oversold/Overbought limits) and MACD crossovers.
- **Trend Following Indicator:** Integrated EMA 20 and EMA 50 indicators on the chart to confirm long-term market trends.
- **Interactive Visualizations:** High-quality, multi-panel interactive Candlestick charts generated using Plotly for deep dive analysis.
- **Customizable Inputs:** Adjust timeframes (15m, 1h, 4h, 1d) and RSI limits dynamically from the sidebar.

### Tech Stack:
- Python
- Streamlit (Frontend Dashboard)
- CCXT (Binance API Integration)
- Pandas (Data Processing)
- Plotly (Interactive Charts)
