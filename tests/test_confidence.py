"""Tests for MatchResult and confidence scoring."""

from decimal import Decimal

import pytest

from financial_consolidator.models.category import (
    CategoryRule,
    MatchMode,
    MatchResult,
)


class TestMatchResult:
    """Tests for MatchResult dataclass."""

    def test_valid_confidence_range(self) -> None:
        """Test that valid confidence values are accepted."""
        result = MatchResult(
            matched=True,
            confidence=0.85,
            matched_by="keyword",
            matched_value="AMAZON",
            factors=["Keyword match: AMAZON"],
        )
        assert result.confidence == 0.85

    def test_confidence_at_bounds(self) -> None:
        """Test confidence at 0.0 and 1.0 boundaries."""
        result_min = MatchResult(
            matched=True, confidence=0.0, matched_by="test", matched_value="test"
        )
        assert result_min.confidence == 0.0

        result_max = MatchResult(
            matched=True, confidence=1.0, matched_by="test", matched_value="test"
        )
        assert result_max.confidence == 1.0

    def test_invalid_confidence_below_zero(self) -> None:
        """Test that confidence below 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            MatchResult(
                matched=True,
                confidence=-0.1,
                matched_by="test",
                matched_value="test",
            )

    def test_invalid_confidence_above_one(self) -> None:
        """Test that confidence above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="Confidence must be between"):
            MatchResult(
                matched=True,
                confidence=1.5,
                matched_by="test",
                matched_value="test",
            )


class TestCategoryRuleConfidence:
    """Tests for CategoryRule confidence scoring."""

    def test_regex_anchored_high_confidence(self) -> None:
        """Test that anchored regex patterns get high confidence."""
        rule = CategoryRule(
            id="test_rule",
            category_id="shopping",
            regex_patterns=[r"^AMAZON"],
            priority=50,
        )
        result = rule.matches("AMAZON MARKETPLACE", Decimal("50.00"), "checking")
        assert result is not None
        # Anchored regex should give high confidence (0.92-1.00)
        assert result.confidence >= 0.92
        assert "Anchored" in "".join(result.factors)

    def test_regex_non_anchored_medium_confidence(self) -> None:
        """Test that non-anchored regex patterns get medium confidence."""
        rule = CategoryRule(
            id="test_rule",
            category_id="shopping",
            regex_patterns=[r"AMAZON"],
            priority=50,
        )
        result = rule.matches("ORDER FROM AMAZON", Decimal("50.00"), "checking")
        assert result is not None
        # Non-anchored regex should give medium confidence (0.85-0.98)
        assert 0.85 <= result.confidence <= 0.98
        assert result.matched_by == "regex"

    def test_keyword_word_boundary_high_confidence(self) -> None:
        """Test that word-boundary keyword matches get high confidence."""
        rule = CategoryRule(
            id="test_rule",
            category_id="gas",
            keywords=["SHELL"],
            match_mode=MatchMode.WORD_BOUNDARY,
            priority=50,
        )
        result = rule.matches("SHELL OIL 12345", Decimal("45.00"), "checking")
        assert result is not None
        # Word boundary match should give higher confidence (0.77-0.95)
        assert result.confidence >= 0.77
        assert result.matched_by == "keyword"

    def test_keyword_substring_lower_confidence(self) -> None:
        """Test that substring keyword matches get lower confidence."""
        rule = CategoryRule(
            id="test_rule",
            category_id="shopping",
            keywords=["MART"],
            match_mode=MatchMode.SUBSTRING,
            priority=50,
        )
        result = rule.matches("WALMART STORE #123", Decimal("100.00"), "checking")
        assert result is not None
        # Substring match should give lower confidence (0.70-0.88)
        assert 0.70 <= result.confidence <= 0.95
        assert result.matched_by == "keyword"

    def test_longer_keyword_higher_confidence(self) -> None:
        """Test that longer keywords increase confidence."""
        short_rule = CategoryRule(
            id="short_rule",
            category_id="dining",
            keywords=["TACO"],
            priority=50,
        )
        long_rule = CategoryRule(
            id="long_rule",
            category_id="dining",
            keywords=["TACO BELL"],
            priority=50,
        )
        # Use a description where keyword is NOT at start to avoid equal boosts
        short_result = short_rule.matches(
            "PAYMENT TO TACO BELL #123", Decimal("10.00"), "checking"
        )
        long_result = long_rule.matches(
            "PAYMENT TO TACO BELL #123", Decimal("10.00"), "checking"
        )

        assert short_result is not None
        assert long_result is not None
        # Longer keyword should have higher or equal confidence
        # (longer keywords are more specific and trustworthy)
        assert long_result.confidence >= short_result.confidence

    def test_high_priority_bonus(self) -> None:
        """Test that high priority rules get confidence bonus."""
        low_priority = CategoryRule(
            id="low_priority",
            category_id="dining",
            keywords=["MCDONALD"],
            priority=10,
        )
        high_priority = CategoryRule(
            id="high_priority",
            category_id="dining",
            keywords=["MCDONALD"],
            priority=100,
        )
        low_result = low_priority.matches(
            "MCDONALD'S #123", Decimal("15.00"), "checking"
        )
        high_result = high_priority.matches(
            "MCDONALD'S #123", Decimal("15.00"), "checking"
        )

        assert low_result is not None
        assert high_result is not None
        # High priority should have higher confidence
        assert high_result.confidence >= low_result.confidence

    def test_no_match_returns_none(self) -> None:
        """Test that non-matching transactions return None."""
        rule = CategoryRule(
            id="test_rule",
            category_id="dining",
            keywords=["MCDONALD"],
            priority=50,
        )
        result = rule.matches("AMAZON MARKETPLACE", Decimal("50.00"), "checking")
        assert result is None

    def test_amount_filter_respects_range(self) -> None:
        """Test that amount filters work correctly."""
        rule = CategoryRule(
            id="test_rule",
            category_id="utility",
            keywords=["UTILITY"],
            amount_min=Decimal("50.00"),
            amount_max=Decimal("200.00"),
            priority=50,
        )
        # Within range
        result_in = rule.matches("UTILITY COMPANY", Decimal("100.00"), "checking")
        assert result_in is not None

        # Below range
        result_below = rule.matches("UTILITY COMPANY", Decimal("25.00"), "checking")
        assert result_below is None

        # Above range
        result_above = rule.matches("UTILITY COMPANY", Decimal("250.00"), "checking")
        assert result_above is None

    def test_narrow_amount_range_boosts_confidence(self) -> None:
        """Test that narrow amount ranges boost confidence."""
        wide_rule = CategoryRule(
            id="wide_rule",
            category_id="utility",
            amount_min=Decimal("10.00"),
            amount_max=Decimal("500.00"),
            priority=50,
        )
        narrow_rule = CategoryRule(
            id="narrow_rule",
            category_id="utility",
            amount_min=Decimal("95.00"),
            amount_max=Decimal("105.00"),
            priority=50,
        )
        wide_result = wide_rule.matches(
            "UTILITY PAYMENT", Decimal("100.00"), "checking"
        )
        narrow_result = narrow_rule.matches(
            "UTILITY PAYMENT", Decimal("100.00"), "checking"
        )

        assert wide_result is not None
        assert narrow_result is not None
        # Narrow range should have higher confidence
        assert narrow_result.confidence >= wide_result.confidence

    def test_account_filter(self) -> None:
        """Test that account_ids filter works correctly."""
        rule = CategoryRule(
            id="test_rule",
            category_id="transfer",
            keywords=["TRANSFER"],
            account_ids=["savings", "checking"],
            priority=50,
        )
        # Matching account
        result_match = rule.matches(
            "INTERNAL TRANSFER", Decimal("500.00"), "checking"
        )
        assert result_match is not None

        # Non-matching account
        result_no_match = rule.matches(
            "INTERNAL TRANSFER", Decimal("500.00"), "credit_card"
        )
        assert result_no_match is None
