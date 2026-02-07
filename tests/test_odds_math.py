"""Tests for odds conversion and vig removal math."""

import pytest

from kalshi_odds.core.odds_math import (
    american_to_prob,
    decimal_to_prob,
    prob_to_american,
    prob_to_decimal,
    no_vig_two_way,
    get_overround,
    get_vig_pct,
)


class TestAmericanOdds:
    """Test American odds conversions."""

    def test_favorite_odds(self):
        # -110 implies ~52.38%
        assert american_to_prob(-110) == pytest.approx(0.5238, abs=0.001)
        # -200 implies 66.67%
        assert american_to_prob(-200) == pytest.approx(0.6667, abs=0.001)

    def test_underdog_odds(self):
        # +150 implies 40%
        assert american_to_prob(+150) == pytest.approx(0.4, abs=0.001)
        # +200 implies 33.33%
        assert american_to_prob(+200) == pytest.approx(0.3333, abs=0.001)

    def test_even_odds(self):
        # +100 (even money) implies 50%
        assert american_to_prob(+100) == pytest.approx(0.5)

    def test_prob_to_american(self):
        # 50% → ±100 (both valid for even odds)
        assert abs(prob_to_american(0.5)) == pytest.approx(100.0, abs=1)
        # 60% (favorite) → negative
        assert prob_to_american(0.6) < 0
        # 40% (underdog) → positive
        assert prob_to_american(0.4) > 0

    def test_roundtrip(self):
        for prob in [0.3, 0.4, 0.5, 0.6, 0.7]:
            american = prob_to_american(prob)
            recovered = american_to_prob(american)
            assert recovered == pytest.approx(prob, abs=0.001)


class TestDecimalOdds:
    """Test decimal odds conversions."""

    def test_decimal_to_prob(self):
        # 2.00 implies 50%
        assert decimal_to_prob(2.00) == pytest.approx(0.5)
        # 1.50 implies 66.67%
        assert decimal_to_prob(1.50) == pytest.approx(0.6667, abs=0.001)
        # 3.00 implies 33.33%
        assert decimal_to_prob(3.00) == pytest.approx(0.3333, abs=0.001)

    def test_prob_to_decimal(self):
        # 50% → 2.00
        assert prob_to_decimal(0.5) == pytest.approx(2.0)
        # 33.33% → 3.00
        assert prob_to_decimal(0.3333) == pytest.approx(3.0, abs=0.01)

    def test_roundtrip(self):
        for prob in [0.2, 0.33, 0.5, 0.667, 0.8]:
            decimal = prob_to_decimal(prob)
            recovered = decimal_to_prob(decimal)
            assert recovered == pytest.approx(prob, abs=0.001)


class TestVigRemoval:
    """Test vig removal mathematics."""

    def test_no_vig_two_way_fair(self):
        # Fair odds (50/50, no vig)
        p_a, p_b = no_vig_two_way(0.5, 0.5)
        assert p_a == pytest.approx(0.5)
        assert p_b == pytest.approx(0.5)

    def test_no_vig_two_way_with_vig(self):
        # Both -110 (52.38% each, overround=1.0476)
        p_a_raw = american_to_prob(-110)
        p_b_raw = american_to_prob(-110)
        
        p_a_nv, p_b_nv = no_vig_two_way(p_a_raw, p_b_raw)
        
        # After vig removal, should be 50/50
        assert p_a_nv == pytest.approx(0.5, abs=0.001)
        assert p_b_nv == pytest.approx(0.5, abs=0.001)
        
        # Sum should be 1.0
        assert p_a_nv + p_b_nv == pytest.approx(1.0)

    def test_no_vig_asymmetric(self):
        # -200 (66.67%) vs +150 (40%) → overround = 1.0667
        p_fav = american_to_prob(-200)
        p_dog = american_to_prob(+150)
        
        p_fav_nv, p_dog_nv = no_vig_two_way(p_fav, p_dog)
        
        # Should normalize to sum = 1.0
        assert p_fav_nv + p_dog_nv == pytest.approx(1.0)
        
        # Favorite should still be > 50%
        assert p_fav_nv > 0.5
        assert p_dog_nv < 0.5

    def test_overround(self):
        # Both -110
        p1 = american_to_prob(-110)
        p2 = american_to_prob(-110)
        overround = get_overround([p1, p2])
        
        # Overround ≈ 1.0476
        assert overround == pytest.approx(1.0476, abs=0.001)

    def test_vig_pct(self):
        # 4.76% vig from -110/-110 market
        overround = 1.0476
        vig_pct = get_vig_pct(overround)
        
        assert vig_pct == pytest.approx(4.76, abs=0.01)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_decimal_odds_zero(self):
        with pytest.raises(ValueError):
            decimal_to_prob(0.0)

    def test_prob_out_of_range(self):
        with pytest.raises(ValueError):
            prob_to_american(0.0)
        
        with pytest.raises(ValueError):
            prob_to_american(1.0)
        
        with pytest.raises(ValueError):
            prob_to_decimal(1.5)
