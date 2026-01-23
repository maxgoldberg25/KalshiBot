"""
News fetching and aggregation module
"""
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

import httpx
import feedparser
from bs4 import BeautifulSoup

from config import config


@dataclass
class NewsArticle:
    """Represents a news article"""
    title: str
    description: str
    url: str
    source: str
    published_at: Optional[datetime]
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


class NewsFetcher:
    """Fetches news from various sources"""
    
    # RSS feeds for different topics
    RSS_FEEDS = {
        "general": [
            "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://feeds.bbci.co.uk/news/rss.xml",
        ],
        "politics": [
            "https://news.google.com/rss/topics/CAAqIggKIhxDQkFTRHdvSkwyMHZNRFZ4ZERBU0FtVnVLQUFQAQ?hl=en-US&gl=US&ceid=US:en",
            "https://rss.politico.com/politics-news.xml",
            "https://feeds.washingtonpost.com/rss/politics",
        ],
        "economics": [
            "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.ft.com/rss/home",
        ],
        "technology": [
            "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
            "https://feeds.arstechnica.com/arstechnica/technology-lab",
        ],
        "sports": [
            "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en",
            "https://www.espn.com/espn/rss/news",
        ],
        "weather": [
            "https://news.google.com/rss/search?q=weather+forecast&hl=en-US&gl=US&ceid=US:en",
        ],
    }
    
    def __init__(self):
        self.client = httpx.Client(timeout=15.0, follow_redirects=True)
        self.news_api_key = config.NEWS_API_KEY
        
    def fetch_news(
        self, 
        keywords: list[str], 
        category: Optional[str] = None,
        days: int = 7,
        limit: int = 20
    ) -> list[NewsArticle]:
        """
        Fetch news articles matching the given keywords
        
        Args:
            keywords: List of search terms
            category: Optional category filter
            days: Number of days to look back
            limit: Maximum number of articles to return
        """
        articles = []
        
        # Try NewsAPI first if key is available
        if self.news_api_key:
            articles.extend(self._fetch_from_newsapi(keywords, days, limit))
        
        # Always supplement with RSS feeds
        articles.extend(self._fetch_from_rss(keywords, category, limit))
        
        # Also try Google News search
        articles.extend(self._fetch_from_google_news(keywords, limit))
        
        # Deduplicate by title similarity
        unique_articles = self._deduplicate(articles)
        
        # Sort by date (newest first)
        unique_articles.sort(
            key=lambda x: x.published_at or datetime.min, 
            reverse=True
        )
        
        return unique_articles[:limit]
    
    def _fetch_from_newsapi(
        self, 
        keywords: list[str], 
        days: int,
        limit: int
    ) -> list[NewsArticle]:
        """Fetch from NewsAPI.org"""
        try:
            query = " OR ".join(keywords)
            from_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            response = self.client.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": from_date,
                    "sortBy": "relevancy",
                    "pageSize": limit,
                    "apiKey": self.news_api_key,
                    "language": "en",
                }
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            articles = []
            
            for article in data.get("articles", []):
                published = None
                if article.get("publishedAt"):
                    try:
                        published = datetime.fromisoformat(
                            article["publishedAt"].replace("Z", "+00:00")
                        )
                    except ValueError:
                        pass
                
                articles.append(NewsArticle(
                    title=article.get("title", ""),
                    description=article.get("description", ""),
                    url=article.get("url", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    published_at=published,
                ))
            
            return articles
            
        except Exception as e:
            print(f"NewsAPI error: {e}")
            return []
    
    def _fetch_from_rss(
        self, 
        keywords: list[str], 
        category: Optional[str],
        limit: int
    ) -> list[NewsArticle]:
        """Fetch from RSS feeds"""
        articles = []
        
        # Select feeds based on category
        feeds = self.RSS_FEEDS.get(category, []) if category else []
        feeds.extend(self.RSS_FEEDS.get("general", []))
        
        for feed_url in feeds[:5]:  # Limit number of feeds to check
            try:
                response = self.client.get(feed_url)
                if response.status_code != 200:
                    continue
                    
                feed = feedparser.parse(response.text)
                
                for entry in feed.entries[:limit]:
                    title = entry.get("title", "")
                    description = entry.get("summary", entry.get("description", ""))
                    
                    # Check if any keyword matches
                    text = f"{title} {description}".lower()
                    if not any(kw.lower() in text for kw in keywords):
                        continue
                    
                    # Parse date
                    published = None
                    if entry.get("published_parsed"):
                        try:
                            published = datetime(*entry.published_parsed[:6])
                        except (TypeError, ValueError):
                            pass
                    
                    articles.append(NewsArticle(
                        title=title,
                        description=self._clean_html(description),
                        url=entry.get("link", ""),
                        source=feed.feed.get("title", "RSS Feed"),
                        published_at=published,
                    ))
                    
            except Exception as e:
                print(f"RSS fetch error for {feed_url}: {e}")
                continue
        
        return articles
    
    def _fetch_from_google_news(
        self, 
        keywords: list[str], 
        limit: int
    ) -> list[NewsArticle]:
        """Fetch from Google News RSS search"""
        articles = []
        
        try:
            query = "+".join(keywords)
            feed_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            
            response = self.client.get(feed_url)
            if response.status_code != 200:
                return []
            
            feed = feedparser.parse(response.text)
            
            for entry in feed.entries[:limit]:
                published = None
                if entry.get("published_parsed"):
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except (TypeError, ValueError):
                        pass
                
                # Extract source from title (Google News format: "Title - Source")
                title = entry.get("title", "")
                source = "Google News"
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        title = parts[0]
                        source = parts[1]
                
                articles.append(NewsArticle(
                    title=title,
                    description=self._clean_html(entry.get("summary", "")),
                    url=entry.get("link", ""),
                    source=source,
                    published_at=published,
                ))
                
        except Exception as e:
            print(f"Google News fetch error: {e}")
        
        return articles
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        if not text:
            return ""
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    
    def _deduplicate(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """Remove duplicate articles based on title similarity"""
        seen_titles = set()
        unique = []
        
        for article in articles:
            # Normalize title for comparison
            normalized = re.sub(r'[^\w\s]', '', article.title.lower())
            normalized = ' '.join(normalized.split()[:8])  # First 8 words
            
            if normalized not in seen_titles and article.title:
                seen_titles.add(normalized)
                unique.append(article)
        
        return unique
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
