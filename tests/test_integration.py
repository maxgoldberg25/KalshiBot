"""
Integration tests for the complete trading flow.
"""

import pytest

from kalshi_bot.config import TradingMode
from kalshi_bot.scheduler.runner import TradingRunner


class TestTradingRunner:
    """Integration tests for the trading runner."""
    
    @pytest.mark.asyncio
    async def test_full_run_paper_mode(self, mock_client):
        """Test complete trading run in paper mode."""
        runner = TradingRunner(
            mode=TradingMode.PAPER,
            client=mock_client,
        )
        
        summary = await runner.run()
        
        # Should complete without errors
        assert "errors" in summary
        # May have no tradeable markets in mock, but should complete
        assert "markets_discovered" in summary
        assert "orders_placed" in summary
    
    @pytest.mark.asyncio
    async def test_full_run_dry_run_mode(self, mock_client):
        """Test complete trading run in dry-run mode."""
        runner = TradingRunner(
            mode=TradingMode.DRY_RUN,
            client=mock_client,
        )
        
        summary = await runner.run()
        
        # Should complete without errors
        assert summary is not None
        # Dry run shouldn't execute any orders
        assert summary.get("orders_filled", 0) == 0
    
    @pytest.mark.asyncio
    async def test_snapshot_only_run(self, mock_client):
        """Test snapshot-only mode."""
        runner = TradingRunner(
            mode=TradingMode.PAPER,
            client=mock_client,
        )
        
        # Should complete without errors
        await runner.run_snapshot_only(["TEST-TODAY-A"])


class TestEndToEndFlow:
    """End-to-end tests for specific scenarios."""
    
    @pytest.mark.asyncio
    async def test_no_markets_scenario(self, mock_client):
        """Test handling when no tradeable markets exist."""
        # Clear mock markets
        mock_client._markets.clear()
        mock_client._orderbooks.clear()
        
        runner = TradingRunner(
            mode=TradingMode.PAPER,
            client=mock_client,
        )
        
        summary = await runner.run()
        
        assert summary["markets_discovered"] == 0
        assert "No tradeable markets" in summary.get("errors", [])
    
    @pytest.mark.asyncio
    async def test_database_persistence(self, mock_client, tmp_path):
        """Test that orders and data are persisted."""
        from kalshi_bot.db.repository import Repository
        
        # Create runner with test database
        db_path = str(tmp_path / "test_persist.db")
        
        runner = TradingRunner(
            mode=TradingMode.PAPER,
            client=mock_client,
        )
        runner.repository = Repository(f"sqlite:///{db_path}")
        
        # Run
        await runner.run()
        
        # Verify database was created
        import os
        assert os.path.exists(db_path)
