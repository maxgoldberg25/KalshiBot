# 🤖 KalshiBot

An intelligent bot that analyzes Kalshi prediction markets by gathering market data, historical trends, and news headlines to provide informed betting recommendations.

## Features

- **Market Analysis**: Fetches real-time market data from Kalshi API
- **News Aggregation**: Gathers relevant news from Google News, RSS feeds, and NewsAPI
- **Sentiment Analysis**: Analyzes news sentiment using NLP (TextBlob)
- **Trend Analysis**: Examines historical price movements and momentum
- **Decision Engine**: Combines multiple signals to generate recommendations
- **Interactive CLI**: Beautiful terminal interface with Rich

## Installation

1. **Clone and navigate to the project:**
   ```bash
   cd KalshiBot
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables (optional but recommended):**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## Configuration

Create a `.env` file with your API credentials:

```env
# Kalshi API (get from https://kalshi.com/settings/api)
KALSHI_API_KEY=your_api_key_here

# NewsAPI (optional, get from https://newsapi.org)
NEWS_API_KEY=your_newsapi_key_here
```

> **Note**: The bot works without API keys using free RSS feeds and public Kalshi data, but API keys provide better data quality.

## Usage

### Interactive Mode (Recommended)
```bash
python main.py
```

This starts an interactive shell where you can run commands:

```
kalshi> search bitcoin
kalshi> analyze KXBTC-25JAN31
kalshi> list
kalshi> quit
```

### Command Line Mode

**Analyze a specific market:**
```bash
python main.py analyze KXBTC-25JAN31
```

**Search for markets:**
```bash
python main.py search "bitcoin"
python main.py search "trump"
python main.py search "fed rate"
```

**List active markets:**
```bash
python main.py list
python main.py list politics
```

## How It Works

### 1. Data Collection
- Fetches market details (price, volume, open interest)
- Retrieves historical price data (candlesticks)
- Gathers relevant news articles based on market keywords

### 2. Analysis Pipeline

**Sentiment Analysis:**
- Extracts keywords from market title/description
- Fetches news from multiple sources
- Analyzes sentiment polarity (-1 to +1)
- Counts positive/negative/neutral articles

**Trend Analysis:**
- Calculates price momentum
- Identifies support/resistance levels
- Measures volatility
- Tracks volume trends

**Market Structure:**
- Analyzes implied probability
- Evaluates bid-ask spread
- Assesses liquidity

### 3. Signal Generation

The bot combines signals into a recommendation:

| Signal | Description |
|--------|-------------|
| STRONG_YES | Multiple strong indicators favor YES |
| LEAN_YES | Weak positive signals |
| NEUTRAL | No clear edge |
| LEAN_NO | Weak negative signals |
| STRONG_NO | Multiple strong indicators favor NO |

### 4. Confidence Levels

- **HIGH**: Strong evidence from multiple sources
- **MEDIUM**: Moderate evidence
- **LOW**: Limited data or conflicting signals

## Example Output

```
╭────────────────── KXBTC-25JAN31 ──────────────────╮
│ Will Bitcoin be at or above $100,000 on Jan 31?  │
│                                                   │
│ 📊 Current Prices:                               │
│ • YES: 65¢ (implied probability: 65.0%)          │
│ • NO: 35¢                                        │
│                                                   │
│ 📈 Market Stats:                                 │
│ • 24h Volume: 12,345 contracts                   │
│ • Open Interest: 45,678 contracts                │
╰───────────────────────────────────────────────────╯

📊 Signal: LEAN_YES
🎯 Confidence: MEDIUM

📝 Analysis Reasoning:
• News sentiment: POSITIVE (polarity: 0.24) based on 12 articles
• Price trend: UP with strong momentum
• Market strongly favors YES (65% implied probability)

💡 Recommendation:
Slight edge toward YES at 65¢
📊 MEDIUM CONFIDENCE: Weak positive signals
• News sentiment is positive
• Price has been trending up

⚠️ This is NOT financial advice. Always do your own research.
```

## Project Structure

```
KalshiBot/
├── main.py           # Entry point and CLI interface
├── config.py         # Configuration management
├── kalshi_client.py  # Kalshi API client
├── news_fetcher.py   # News aggregation
├── analyzer.py       # Analysis and decision engine
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Limitations

- **Not Financial Advice**: This bot provides analysis for educational purposes only
- **Data Quality**: Results depend on available news and API data
- **Market Efficiency**: Prediction markets are often efficient; easy edges are rare
- **API Limits**: Free tier APIs have rate limits

## Future Improvements

- [ ] Add support for more news sources
- [ ] Implement machine learning models for sentiment
- [ ] Add backtesting capabilities
- [ ] Create a web dashboard
- [ ] Add alerts for market movements
- [ ] Support for portfolio tracking

## License

MIT License - See LICENSE file for details.

## Disclaimer

⚠️ **This software is for educational and informational purposes only.**

- This is NOT financial advice
- Past performance does not guarantee future results
- Prediction markets involve risk of loss
- Always do your own research before placing any bets
- The authors are not responsible for any financial losses
