"""
Configuration management for KalshiBot
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Application configuration"""
    
    # Kalshi API
    KALSHI_API_KEY: str = os.getenv("KALSHI_API_KEY", "")
    KALSHI_PRIVATE_KEY_PATH: str = os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
    KALSHI_API_BASE_URL: str = "https://api.elections.kalshi.com/trade-api/v2"
    
    # News API
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    
    # OpenAI (optional, for enhanced analysis)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Analysis settings
    NEWS_LOOKBACK_DAYS: int = 7
    MIN_ARTICLES_FOR_SENTIMENT: int = 3
    
    # Confidence thresholds
    HIGH_CONFIDENCE_THRESHOLD: float = 0.7
    MEDIUM_CONFIDENCE_THRESHOLD: float = 0.5
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate configuration and return list of warnings"""
        warnings = []
        
        if not cls.KALSHI_API_KEY:
            warnings.append("KALSHI_API_KEY not set - will use demo mode with limited data")
        
        if not cls.NEWS_API_KEY:
            warnings.append("NEWS_API_KEY not set - using free RSS feeds for news")
            
        return warnings


config = Config()
