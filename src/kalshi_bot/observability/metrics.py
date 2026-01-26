"""
Performance metrics and reporting.

Generates daily reports with:
- Trade statistics
- P&L breakdown
- Win rate and other KPIs
- Risk metrics
"""

from datetime import datetime
from typing import Optional

import structlog

from kalshi_bot.models.position import DailyPnL

logger = structlog.get_logger()


def generate_daily_report(
    summary: dict,
    daily_pnl: DailyPnL,
) -> str:
    """
    Generate a formatted daily report.
    
    Args:
        summary: Run summary from TradingRunner
        daily_pnl: Daily P&L record
        
    Returns:
        Formatted report string
    """
    date_str = daily_pnl.date.strftime("%Y-%m-%d")
    
    report_lines = [
        "=" * 60,
        f"KALSHI BOT DAILY REPORT - {date_str}",
        "=" * 60,
        "",
        "📊 TRADING SUMMARY",
        "-" * 40,
        f"Mode: {summary.get('mode', 'unknown')}",
        f"Markets Discovered: {summary.get('markets_discovered', 0)}",
        f"Markets Tradeable: {summary.get('markets_tradeable', 0)}",
        f"Signals Generated: {summary.get('signals_generated', 0)}",
        f"Signals Valid: {summary.get('signals_valid', 0)}",
        f"Orders Placed: {summary.get('orders_placed', 0)}",
        f"Orders Filled: {summary.get('orders_filled', 0)}",
        "",
        "💰 P&L BREAKDOWN",
        "-" * 40,
        f"Realized P&L: ${daily_pnl.realized_pnl:+.2f}",
        f"Unrealized P&L: ${daily_pnl.unrealized_pnl:+.2f}",
        f"Fees: ${daily_pnl.fees:.2f}",
        f"Total P&L: ${daily_pnl.total_pnl:+.2f}",
        "",
        "📈 PERFORMANCE METRICS",
        "-" * 40,
        f"Trades Placed: {daily_pnl.trades_placed}",
        f"Trades Filled: {daily_pnl.trades_filled}",
        f"Trades Won: {daily_pnl.trades_won}",
        f"Trades Lost: {daily_pnl.trades_lost}",
        f"Win Rate: {daily_pnl.win_rate:.1%}" if daily_pnl.win_rate else "Win Rate: N/A",
        "",
        "⚠️ RISK METRICS",
        "-" * 40,
        f"Peak Exposure: ${daily_pnl.peak_exposure:.2f}",
        f"Ending Exposure: ${daily_pnl.ending_exposure:.2f}",
        f"Markets Traded: {', '.join(daily_pnl.markets_traded) or 'None'}",
        "",
    ]
    
    # Add errors if any
    errors = summary.get("errors", [])
    if errors:
        report_lines.extend([
            "❌ ERRORS",
            "-" * 40,
        ])
        for error in errors:
            report_lines.append(f"  • {error}")
        report_lines.append("")
    
    # Add timing info
    if summary.get("start_time") and summary.get("end_time"):
        report_lines.extend([
            "⏱️ TIMING",
            "-" * 40,
            f"Start: {summary.get('start_time')}",
            f"End: {summary.get('end_time')}",
            f"Duration: {summary.get('duration_seconds', 0):.1f}s",
            "",
        ])
    
    report_lines.append("=" * 60)
    
    report = "\n".join(report_lines)
    
    # Log the report
    logger.info(
        "daily_report_generated",
        date=date_str,
        total_pnl=daily_pnl.total_pnl,
        win_rate=daily_pnl.win_rate,
    )
    
    return report


def calculate_sharpe_ratio(
    returns: list[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> Optional[float]:
    """
    Calculate annualized Sharpe ratio.
    
    Args:
        returns: List of period returns
        risk_free_rate: Risk-free rate (annualized)
        periods_per_year: Trading periods per year
        
    Returns:
        Annualized Sharpe ratio or None if insufficient data
    """
    import numpy as np
    
    if len(returns) < 2:
        return None
    
    returns_arr = np.array(returns)
    excess_returns = returns_arr - (risk_free_rate / periods_per_year)
    
    if np.std(excess_returns) == 0:
        return None
    
    sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(periods_per_year)
    return float(sharpe)


def calculate_max_drawdown(equity_curve: list[float]) -> float:
    """
    Calculate maximum drawdown from equity curve.
    
    Args:
        equity_curve: List of cumulative returns/equity values
        
    Returns:
        Maximum drawdown as a fraction (0.1 = 10% drawdown)
    """
    import numpy as np
    
    if len(equity_curve) < 2:
        return 0.0
    
    arr = np.array(equity_curve)
    peak = np.maximum.accumulate(arr)
    drawdown = (peak - arr) / np.where(peak > 0, peak, 1)
    
    return float(np.max(drawdown))
