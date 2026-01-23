"""
Analysis module for sentiment analysis and decision making
"""
import re
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from textblob import TextBlob

from kalshi_client import Market, PriceHistory
from news_fetcher import NewsArticle
from config import config


class Signal(Enum):
    """Trading signal"""
    STRONG_YES = "STRONG_YES"
    LEAN_YES = "LEAN_YES"
    NEUTRAL = "NEUTRAL"
    LEAN_NO = "LEAN_NO"
    STRONG_NO = "STRONG_NO"


class Confidence(Enum):
    """Confidence level"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class SentimentResult:
    """Result of sentiment analysis"""
    polarity: float  # -1 to 1 (negative to positive)
    subjectivity: float  # 0 to 1 (objective to subjective)
    positive_count: int
    negative_count: int
    neutral_count: int
    key_phrases: list[str]
    
    @property
    def overall_sentiment(self) -> str:
        if self.polarity > 0.1:
            return "POSITIVE"
        elif self.polarity < -0.1:
            return "NEGATIVE"
        return "NEUTRAL"


@dataclass
class TrendAnalysis:
    """Result of price trend analysis"""
    direction: str  # "UP", "DOWN", "SIDEWAYS"
    momentum: float  # -1 to 1
    volatility: float  # Standard deviation of price changes
    support_level: float  # Recent low
    resistance_level: float  # Recent high
    volume_trend: str  # "INCREASING", "DECREASING", "STABLE"


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    market: Market
    signal: Signal
    confidence: Confidence
    sentiment: SentimentResult
    trend: Optional[TrendAnalysis]
    reasoning: list[str]
    risk_factors: list[str]
    recommendation: str
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.market.ticker,
            "title": self.market.title,
            "signal": self.signal.value,
            "confidence": self.confidence.value,
            "recommendation": self.recommendation,
            "current_price": {
                "yes": self.market.yes_price,
                "no": self.market.no_price,
                "implied_probability": f"{self.market.implied_probability:.1%}",
            },
            "sentiment": {
                "overall": self.sentiment.overall_sentiment,
                "polarity": round(self.sentiment.polarity, 3),
                "articles_analyzed": (
                    self.sentiment.positive_count + 
                    self.sentiment.negative_count + 
                    self.sentiment.neutral_count
                ),
            },
            "trend": {
                "direction": self.trend.direction if self.trend else "UNKNOWN",
                "momentum": round(self.trend.momentum, 3) if self.trend else 0,
            } if self.trend else None,
            "reasoning": self.reasoning,
            "risk_factors": self.risk_factors,
        }


class MarketAnalyzer:
    """Analyzes market data and news to generate trading signals"""
    
    # Keywords that suggest positive outcome for YES
    POSITIVE_KEYWORDS = [
        "will", "likely", "expected", "confirms", "announces", "agrees",
        "success", "wins", "passes", "approved", "certain", "definitely",
        "breakthrough", "achieves", "surges", "gains", "rises", "increases"
    ]
    
    # Keywords that suggest negative outcome (NO wins)
    NEGATIVE_KEYWORDS = [
        "won't", "unlikely", "fails", "rejects", "denies", "blocks",
        "failure", "loses", "defeated", "rejected", "uncertain", "doubt",
        "crisis", "falls", "drops", "declines", "crashes", "plunges"
    ]
    
    def analyze(
        self,
        market: Market,
        articles: list[NewsArticle],
        price_history: list[PriceHistory]
    ) -> AnalysisResult:
        """
        Perform complete analysis on a market
        
        Args:
            market: The market to analyze
            articles: Related news articles
            price_history: Historical price data
            
        Returns:
            Complete analysis with signal and reasoning
        """
        reasoning = []
        risk_factors = []
        
        # 1. Analyze news sentiment
        sentiment = self._analyze_sentiment(articles, market)
        
        # 2. Analyze price trends
        trend = self._analyze_trends(price_history) if price_history else None
        
        # 3. Analyze market structure
        market_analysis = self._analyze_market_structure(market)
        reasoning.extend(market_analysis["observations"])
        risk_factors.extend(market_analysis["risks"])
        
        # 4. Combine signals into final recommendation
        signal, confidence = self._calculate_signal(
            market, sentiment, trend, len(articles)
        )
        
        # Add sentiment reasoning
        if articles:
            reasoning.append(
                f"News sentiment: {sentiment.overall_sentiment} "
                f"(polarity: {sentiment.polarity:.2f}) based on {len(articles)} articles"
            )
            if sentiment.key_phrases:
                reasoning.append(f"Key themes: {', '.join(sentiment.key_phrases[:5])}")
        else:
            reasoning.append("Limited news coverage - relying primarily on market data")
            risk_factors.append("Low news coverage increases uncertainty")
        
        # Add trend reasoning
        if trend:
            reasoning.append(
                f"Price trend: {trend.direction} with "
                f"{'strong' if abs(trend.momentum) > 0.5 else 'weak'} momentum"
            )
            reasoning.append(
                f"Recent range: {trend.support_level:.0f}¢ - {trend.resistance_level:.0f}¢"
            )
        
        # Generate recommendation text
        recommendation = self._generate_recommendation(
            market, signal, confidence, sentiment, trend
        )
        
        return AnalysisResult(
            market=market,
            signal=signal,
            confidence=confidence,
            sentiment=sentiment,
            trend=trend,
            reasoning=reasoning,
            risk_factors=risk_factors,
            recommendation=recommendation,
        )
    
    def _analyze_sentiment(
        self, 
        articles: list[NewsArticle],
        market: Market
    ) -> SentimentResult:
        """Analyze sentiment from news articles"""
        if not articles:
            return SentimentResult(
                polarity=0,
                subjectivity=0.5,
                positive_count=0,
                negative_count=0,
                neutral_count=0,
                key_phrases=[],
            )
        
        polarities = []
        subjectivities = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        all_phrases = []
        
        for article in articles:
            text = f"{article.title}. {article.description}"
            
            # Use TextBlob for sentiment analysis
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            polarities.append(polarity)
            subjectivities.append(subjectivity)
            
            # Count sentiment categories
            if polarity > 0.1:
                positive_count += 1
            elif polarity < -0.1:
                negative_count += 1
            else:
                neutral_count += 1
            
            # Extract noun phrases as key themes
            all_phrases.extend([str(phrase) for phrase in blob.noun_phrases[:3]])
        
        # Calculate averages
        avg_polarity = sum(polarities) / len(polarities)
        avg_subjectivity = sum(subjectivities) / len(subjectivities)
        
        # Find most common phrases
        phrase_counts = {}
        for phrase in all_phrases:
            phrase_lower = phrase.lower()
            phrase_counts[phrase_lower] = phrase_counts.get(phrase_lower, 0) + 1
        
        top_phrases = sorted(
            phrase_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:10]
        
        return SentimentResult(
            polarity=avg_polarity,
            subjectivity=avg_subjectivity,
            positive_count=positive_count,
            negative_count=negative_count,
            neutral_count=neutral_count,
            key_phrases=[phrase for phrase, _ in top_phrases],
        )
    
    def _analyze_trends(self, history: list[PriceHistory]) -> Optional[TrendAnalysis]:
        """Analyze price trends from historical data"""
        if len(history) < 3:
            return None
        
        prices = [h.yes_price for h in history]
        volumes = [h.volume for h in history]
        
        # Calculate price direction and momentum
        recent_prices = prices[-min(10, len(prices)):]
        if len(recent_prices) >= 2:
            price_change = recent_prices[-1] - recent_prices[0]
            avg_price = sum(recent_prices) / len(recent_prices)
            momentum = price_change / max(avg_price, 1) if avg_price else 0
        else:
            price_change = 0
            momentum = 0
        
        # Determine direction
        if price_change > 2:
            direction = "UP"
        elif price_change < -2:
            direction = "DOWN"
        else:
            direction = "SIDEWAYS"
        
        # Calculate volatility (standard deviation)
        if len(prices) >= 2:
            mean_price = sum(prices) / len(prices)
            variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
            volatility = variance ** 0.5
        else:
            volatility = 0
        
        # Support and resistance levels
        support = min(prices)
        resistance = max(prices)
        
        # Volume trend
        if len(volumes) >= 5:
            early_vol = sum(volumes[:len(volumes)//2])
            late_vol = sum(volumes[len(volumes)//2:])
            
            if late_vol > early_vol * 1.2:
                volume_trend = "INCREASING"
            elif late_vol < early_vol * 0.8:
                volume_trend = "DECREASING"
            else:
                volume_trend = "STABLE"
        else:
            volume_trend = "UNKNOWN"
        
        return TrendAnalysis(
            direction=direction,
            momentum=max(-1, min(1, momentum)),  # Clamp to -1 to 1
            volatility=volatility,
            support_level=support * 100,  # Convert to cents
            resistance_level=resistance * 100,
            volume_trend=volume_trend,
        )
    
    def _analyze_market_structure(self, market: Market) -> dict:
        """Analyze market structure for additional insights"""
        observations = []
        risks = []
        
        # Implied probability analysis
        prob = market.implied_probability
        if prob > 0.85:
            observations.append(
                f"Market strongly favors YES ({prob:.0%} implied probability)"
            )
            risks.append("High price means limited upside, significant downside risk")
        elif prob < 0.15:
            observations.append(
                f"Market strongly favors NO ({prob:.0%} implied probability)"
            )
            risks.append("Low price means limited downside, but YES is considered unlikely")
        elif 0.4 <= prob <= 0.6:
            observations.append(
                f"Market is uncertain ({prob:.0%} implied probability)"
            )
            risks.append("High uncertainty - could go either way")
        
        # Volume analysis
        if market.volume_24h > 10000:
            observations.append(f"High trading activity ({market.volume_24h:,} contracts in 24h)")
        elif market.volume_24h < 100:
            observations.append(f"Low trading activity ({market.volume_24h:,} contracts in 24h)")
            risks.append("Low liquidity may affect ability to enter/exit positions")
        
        # Spread analysis
        if market.spread > 5:
            risks.append(f"Wide bid-ask spread ({market.spread:.0f}¢) increases transaction costs")
        
        # Open interest
        if market.open_interest > 0:
            observations.append(f"Open interest: {market.open_interest:,} contracts")
        
        return {
            "observations": observations,
            "risks": risks,
        }
    
    def _calculate_signal(
        self,
        market: Market,
        sentiment: SentimentResult,
        trend: Optional[TrendAnalysis],
        article_count: int
    ) -> tuple[Signal, Confidence]:
        """Calculate final trading signal and confidence"""
        
        # Initialize score (positive = YES, negative = NO)
        score = 0.0
        confidence_score = 0.0
        
        # Factor 1: News sentiment (-1 to 1)
        sentiment_weight = 0.4
        score += sentiment.polarity * sentiment_weight
        
        # Adjust confidence based on number of articles
        if article_count >= 10:
            confidence_score += 0.3
        elif article_count >= 5:
            confidence_score += 0.2
        elif article_count >= 3:
            confidence_score += 0.1
        
        # Factor 2: Price momentum (-1 to 1)
        if trend:
            momentum_weight = 0.3
            score += trend.momentum * momentum_weight
            
            # Higher confidence if trend is clear
            if abs(trend.momentum) > 0.3:
                confidence_score += 0.2
            
            # Lower confidence if high volatility
            if trend.volatility > 10:
                confidence_score -= 0.1
        
        # Factor 3: Market implied probability
        prob = market.implied_probability
        prob_weight = 0.3
        
        # If price is extreme, news/trend disagreement is more significant
        if prob > 0.7 and sentiment.polarity < -0.2:
            score -= 0.3  # News negative but price high = bearish signal
            confidence_score += 0.1
        elif prob < 0.3 and sentiment.polarity > 0.2:
            score += 0.3  # News positive but price low = bullish signal
            confidence_score += 0.1
        
        # Convert score to signal
        if score > 0.3:
            signal = Signal.STRONG_YES
        elif score > 0.1:
            signal = Signal.LEAN_YES
        elif score < -0.3:
            signal = Signal.STRONG_NO
        elif score < -0.1:
            signal = Signal.LEAN_NO
        else:
            signal = Signal.NEUTRAL
        
        # Determine confidence level
        confidence_score = max(0, min(1, confidence_score))
        
        if confidence_score >= config.HIGH_CONFIDENCE_THRESHOLD:
            confidence = Confidence.HIGH
        elif confidence_score >= config.MEDIUM_CONFIDENCE_THRESHOLD:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW
        
        return signal, confidence
    
    def _generate_recommendation(
        self,
        market: Market,
        signal: Signal,
        confidence: Confidence,
        sentiment: SentimentResult,
        trend: Optional[TrendAnalysis]
    ) -> str:
        """Generate human-readable recommendation"""
        
        # Base recommendation based on signal
        if signal == Signal.STRONG_YES:
            action = "Consider buying YES"
            reasoning = "Multiple indicators suggest a positive outcome"
        elif signal == Signal.LEAN_YES:
            action = "Slight edge toward YES"
            reasoning = "Weak positive signals"
        elif signal == Signal.STRONG_NO:
            action = "Consider buying NO"
            reasoning = "Multiple indicators suggest a negative outcome"
        elif signal == Signal.LEAN_NO:
            action = "Slight edge toward NO"
            reasoning = "Weak negative signals"
        else:
            action = "No clear edge"
            reasoning = "Mixed or insufficient signals"
        
        # Add confidence qualifier
        if confidence == Confidence.LOW:
            confidence_text = "⚠️ LOW CONFIDENCE"
        elif confidence == Confidence.MEDIUM:
            confidence_text = "📊 MEDIUM CONFIDENCE"
        else:
            confidence_text = "✅ HIGH CONFIDENCE"
        
        # Build recommendation
        rec = f"{action} at {market.yes_price:.0f}¢\n"
        rec += f"{confidence_text}: {reasoning}\n"
        
        # Add specific insights
        if sentiment.overall_sentiment != "NEUTRAL":
            rec += f"• News sentiment is {sentiment.overall_sentiment.lower()}\n"
        
        if trend and trend.direction != "SIDEWAYS":
            rec += f"• Price has been trending {trend.direction.lower()}\n"
        
        # Risk warning
        rec += "\n⚠️ This is NOT financial advice. Always do your own research."
        
        return rec
