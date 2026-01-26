"""
Kalshi API Client for fetching market data
"""
import time
import base64
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

import httpx
from config import config


@dataclass
class Market:
    """Represents a Kalshi market"""
    ticker: str
    title: str
    subtitle: str
    category: str
    status: str
    yes_price: float  # Current YES price (0-100 cents)
    no_price: float   # Current NO price (0-100 cents)
    volume: int       # Total contracts traded
    volume_24h: int   # 24h volume
    open_interest: int
    yes_ask: float
    yes_bid: float
    close_time: Optional[datetime]
    result: Optional[str]
    
    @property
    def implied_probability(self) -> float:
        """Returns the implied probability of YES outcome (0-1)"""
        return self.yes_price / 100
    
    @property
    def spread(self) -> float:
        """Returns the bid-ask spread"""
        return self.yes_ask - self.yes_bid
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "title": self.title,
            "subtitle": self.subtitle,
            "category": self.category,
            "status": self.status,
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "implied_probability": f"{self.implied_probability:.1%}",
            "volume": self.volume,
            "volume_24h": self.volume_24h,
            "open_interest": self.open_interest,
            "spread": self.spread,
            "close_time": self.close_time.isoformat() if self.close_time else None,
        }


@dataclass
class PriceHistory:
    """Historical price data point"""
    timestamp: datetime
    yes_price: float
    volume: int


class KalshiClient:
    """Client for interacting with the Kalshi API"""
    
    def __init__(self):
        self.base_url = config.KALSHI_API_BASE_URL
        self.api_key = config.KALSHI_API_KEY
        self.client = httpx.Client(timeout=30.0)
        self._token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
    def _get_headers(self) -> dict:
        """Get headers for API requests"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        return headers
    
    def search_markets(self, query: str, limit: int = 10) -> list[Market]:
        """Search for markets by keyword - searches both events and markets"""
        markets = []
        
        # First, search events for better results
        try:
            events = self._search_events(query, limit=20)
            for event in events:
                event_markets = self._get_markets_for_event(event["event_ticker"])
                markets.extend(event_markets[:3])  # Get top 3 markets per event
                
                if len(markets) >= limit:
                    break
        except Exception as e:
            print(f"Event search error: {e}")
        
        # If we didn't find enough via events, search markets directly
        if len(markets) < limit:
            try:
                response = self.client.get(
                    f"{self.base_url}/markets",
                    params={"limit": 200},
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("markets", []):
                        title = m.get("title", "").lower()
                        subtitle = m.get("subtitle", "").lower()
                        event_ticker = m.get("event_ticker", "").lower()
                        
                        if query.lower() in title or query.lower() in subtitle or query.lower() in event_ticker:
                            market = self._parse_market(m)
                            # Avoid duplicates
                            if not any(existing.ticker == market.ticker for existing in markets):
                                markets.append(market)
                                
            except Exception as e:
                print(f"Market search error: {e}")
        
        return markets[:limit]
    
    def _search_events(self, query: str, limit: int = 20) -> list[dict]:
        """Search for events by keyword"""
        try:
            response = self.client.get(
                f"{self.base_url}/events",
                params={"limit": 200},
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            matching = []
            query_lower = query.lower()
            
            # Common aliases for search terms
            aliases = {
                "bitcoin": ["btc", "bitcoin"],
                "btc": ["btc", "bitcoin"],
                "ethereum": ["eth", "ethereum"],
                "eth": ["eth", "ethereum"],
                "federal reserve": ["fed", "federal reserve"],
                "fed": ["fed", "federal reserve"],
                "president": ["pres", "president", "potus"],
                "election": ["elect", "election", "vote"],
            }
            
            search_terms = [query_lower]
            if query_lower in aliases:
                search_terms = aliases[query_lower]
            
            for event in data.get("events", []):
                title = event.get("title", "").lower()
                ticker = event.get("event_ticker", "").lower()
                category = event.get("category", "").lower()
                
                # Check if any search term matches
                for term in search_terms:
                    if term in title or term in ticker or term in category:
                        matching.append(event)
                        break
                    
                if len(matching) >= limit:
                    break
            
            return matching
            
        except Exception as e:
            print(f"Error searching events: {e}")
            return []
    
    def _get_markets_for_event(self, event_ticker: str) -> list[Market]:
        """Get all markets for a specific event"""
        try:
            response = self.client.get(
                f"{self.base_url}/markets",
                params={"event_ticker": event_ticker, "limit": 50},
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return [self._parse_market(m) for m in data.get("markets", [])]
            
        except Exception as e:
            print(f"Error getting markets for event {event_ticker}: {e}")
            return []
    
    def get_market(self, ticker: str) -> Optional[Market]:
        """Get detailed information about a specific market"""
        try:
            response = self.client.get(
                f"{self.base_url}/markets/{ticker}",
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                print(f"API Error: {response.status_code} - {response.text}")
                return None
                
            data = response.json()
            return self._parse_market(data.get("market", {}))
            
        except Exception as e:
            print(f"Error fetching market {ticker}: {e}")
            return None
    
    def get_market_history(
        self, 
        ticker: str, 
        days: int = 7,
        resolution: str = "1h"
    ) -> list[PriceHistory]:
        """Get historical price data for a market"""
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)
            
            # Map resolution to minutes
            resolution_map = {
                "1m": 1,
                "5m": 5,
                "15m": 15,
                "1h": 60,
                "4h": 240,
                "1d": 1440,
            }
            
            response = self.client.get(
                f"{self.base_url}/markets/{ticker}/candlesticks",
                params={
                    "start_ts": int(start_time.timestamp()),
                    "end_ts": int(end_time.timestamp()),
                    "period_interval": resolution_map.get(resolution, 60),
                },
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            history = []
            
            for candle in data.get("candlesticks", []):
                history.append(PriceHistory(
                    timestamp=datetime.fromtimestamp(candle.get("end_period_ts", 0)),
                    yes_price=candle.get("price", {}).get("close", 0) / 100,
                    volume=candle.get("volume", 0)
                ))
            
            return history
            
        except Exception as e:
            print(f"Error fetching history for {ticker}: {e}")
            return []
    
    def get_orderbook(self, ticker: str) -> dict:
        """Get the current orderbook for a market"""
        try:
            response = self.client.get(
                f"{self.base_url}/markets/{ticker}/orderbook",
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                return {"yes": [], "no": []}
            
            data = response.json()
            return {
                "yes": data.get("orderbook", {}).get("yes", []),
                "no": data.get("orderbook", {}).get("no", []),
            }
            
        except Exception as e:
            print(f"Error fetching orderbook for {ticker}: {e}")
            return {"yes": [], "no": []}
    
    def list_active_markets(self, category: Optional[str] = None, limit: int = 20) -> list[Market]:
        """List active markets, optionally filtered by category"""
        markets = []
        
        # Get events first for more interesting listings
        try:
            response = self.client.get(
                f"{self.base_url}/events",
                params={"limit": 50},
                headers=self._get_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                for event in data.get("events", []):
                    # Filter by category if specified
                    if category:
                        event_cat = event.get("category", "").lower()
                        event_ticker = event.get("event_ticker", "").lower()
                        if category.lower() not in event_cat and category.lower() not in event_ticker:
                            continue
                    
                    # Get markets for this event
                    event_markets = self._get_markets_for_event(event["event_ticker"])
                    if event_markets:
                        # Add the first (main) market from each event
                        markets.append(event_markets[0])
                    
                    if len(markets) >= limit:
                        break
                        
        except Exception as e:
            print(f"Error listing events: {e}")
        
        # Fallback to direct market listing if needed
        if len(markets) < limit:
            try:
                params = {"limit": min(limit * 2, 200)}
                if category:
                    params["series_ticker"] = category
                
                response = self.client.get(
                    f"{self.base_url}/markets",
                    params=params,
                    headers=self._get_headers()
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for m in data.get("markets", []):
                        market = self._parse_market(m)
                        if not any(existing.ticker == market.ticker for existing in markets):
                            markets.append(market)
                            if len(markets) >= limit:
                                break
                                
            except Exception as e:
                print(f"Error listing markets: {e}")
        
        return markets[:limit]
    
    def list_events(self, limit: int = 20) -> list[dict]:
        """List available events/categories"""
        try:
            response = self.client.get(
                f"{self.base_url}/events",
                params={"limit": limit},
                headers=self._get_headers()
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return [
                {
                    "ticker": e.get("event_ticker"),
                    "title": e.get("title"),
                    "category": e.get("category"),
                    "market_count": e.get("mutually_exclusive", False),
                }
                for e in data.get("events", [])
            ]
            
        except Exception as e:
            print(f"Error listing events: {e}")
            return []
    
    def _parse_market(self, data: dict) -> Market:
        """Parse API response into Market dataclass"""
        close_time = None
        if data.get("close_time"):
            try:
                close_time = datetime.fromisoformat(data["close_time"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        
        # Get yes price - Kalshi returns price in cents (0-100)
        # last_price is in cents, last_price_dollars is in dollars
        yes_price = data.get("last_price", 0)
        if yes_price == 0 and data.get("last_price_dollars"):
            try:
                yes_price = float(data["last_price_dollars"]) * 100
            except (ValueError, TypeError):
                yes_price = 50  # Default to 50 if unknown
        
        # Ensure yes_price is reasonable (0-100)
        yes_price = max(1, min(99, yes_price)) if yes_price > 0 else 50
        
        return Market(
            ticker=data.get("ticker", ""),
            title=data.get("title", data.get("event_ticker", "")),
            subtitle=data.get("subtitle", ""),
            category=data.get("category", data.get("event_ticker", "").split("-")[0] if data.get("event_ticker") else ""),
            status="active" if not data.get("result") else "settled",
            yes_price=yes_price,
            no_price=100 - yes_price,
            volume=data.get("volume", 0),
            volume_24h=data.get("volume_24h", 0),
            open_interest=data.get("open_interest", 0),
            yes_ask=data.get("yes_ask", yes_price + 2),
            yes_bid=data.get("yes_bid", max(1, yes_price - 2)),
            close_time=close_time,
            result=data.get("result"),
        )
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
