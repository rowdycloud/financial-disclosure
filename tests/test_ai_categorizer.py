"""Tests for AI categorization module."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from financial_consolidator.models.transaction import Transaction
from financial_consolidator.processing.ai.client import AIClient, AIClientConfig
from financial_consolidator.processing.ai.cost_estimator import CostEstimator
from financial_consolidator.processing.ai.models import (
    AICategorizationResult,
    AIUsageStats,
    BatchResult,
    CostEstimate,
    ValidationStatus,
)


class TestCostEstimator:
    """Tests for CostEstimator."""

    def test_estimate_tokens_single_mode(self) -> None:
        """Test token estimation in single transaction mode."""
        estimator = CostEstimator(model="claude-sonnet-4-5-20250929")
        input_tokens, output_tokens = estimator.estimate_tokens(
            num_transactions=10,
            num_categories=20,
            is_batch=False,
        )
        # Each transaction needs system prompt + categories + transaction
        assert input_tokens > 0
        assert output_tokens > 0
        # Single mode should have more input tokens per transaction
        assert input_tokens > output_tokens

    def test_estimate_tokens_batch_mode(self) -> None:
        """Test token estimation in batch mode."""
        estimator = CostEstimator(model="claude-sonnet-4-5-20250929")
        input_single, output_single = estimator.estimate_tokens(
            num_transactions=100,
            num_categories=20,
            is_batch=False,
        )
        input_batch, output_batch = estimator.estimate_tokens(
            num_transactions=100,
            num_categories=20,
            is_batch=True,
            batch_size=20,
        )
        # Batch mode should use fewer total input tokens
        # (system prompt and categories shared across batch)
        assert input_batch < input_single

    def test_estimate_cost_calculation(self) -> None:
        """Test cost calculation from tokens."""
        estimator = CostEstimator(model="claude-sonnet-4-5-20250929")
        # 1M input tokens = $3.00, 1M output tokens = $15.00
        cost = estimator.estimate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        assert cost == pytest.approx(18.00, rel=0.01)

    def test_budget_check_within_limit(self) -> None:
        """Test budget check when within limit."""
        estimator = CostEstimator(
            model="claude-sonnet-4-5-20250929",
            budget_limit=10.00,
            current_spend=5.00,
        )
        within, msg = estimator.check_budget(4.00)
        assert within is True
        assert "Within budget" in msg

    def test_budget_check_exceeds_limit(self) -> None:
        """Test budget check when exceeding limit."""
        estimator = CostEstimator(
            model="claude-sonnet-4-5-20250929",
            budget_limit=10.00,
            current_spend=8.00,
        )
        within, msg = estimator.check_budget(5.00)
        assert within is False
        assert "exceeds" in msg.lower()

    def test_budget_check_no_limit(self) -> None:
        """Test budget check when no limit set."""
        estimator = CostEstimator(
            model="claude-sonnet-4-5-20250929",
            budget_limit=None,
        )
        within, msg = estimator.check_budget(1000.00)
        assert within is True
        assert "No budget limit" in msg

    def test_record_spend(self) -> None:
        """Test spend recording."""
        estimator = CostEstimator(model="claude-sonnet-4-5-20250929")
        estimator.record_spend(1.50)
        assert estimator.current_spend == 1.50
        estimator.record_spend(0.50)
        assert estimator.current_spend == 2.00


class TestAIClient:
    """Tests for AIClient."""

    def test_client_not_available_without_api_key(self) -> None:
        """Test that client is not available without API key."""
        with patch.dict("os.environ", {}, clear=True):
            config = AIClientConfig(
                api_key_env="ANTHROPIC_API_KEY",
                model="claude-sonnet-4-5-20250929",
            )
            client = AIClient(config=config)
            assert client.is_available is False

    def test_parse_json_response_valid_dict(self) -> None:
        """Test parsing valid JSON dict response."""
        config = AIClientConfig(
            api_key_env="ANTHROPIC_API_KEY",
            model="claude-sonnet-4-5-20250929",
        )
        client = AIClient(config=config)
        result = client.parse_json_response('{"category_id": "dining", "confidence": 0.9}')
        assert result == {"category_id": "dining", "confidence": 0.9}

    def test_parse_json_response_valid_list(self) -> None:
        """Test parsing valid JSON list response."""
        config = AIClientConfig(
            api_key_env="ANTHROPIC_API_KEY",
            model="claude-sonnet-4-5-20250929",
        )
        client = AIClient(config=config)
        result = client.parse_json_response('[{"index": 1, "category_id": "dining"}]')
        assert result == [{"index": 1, "category_id": "dining"}]

    def test_parse_json_response_with_extra_text(self) -> None:
        """Test parsing JSON with surrounding text."""
        config = AIClientConfig(
            api_key_env="ANTHROPIC_API_KEY",
            model="claude-sonnet-4-5-20250929",
        )
        client = AIClient(config=config)
        response = 'Here is the result: {"category_id": "shopping"} I hope this helps!'
        result = client.parse_json_response(response)
        assert result == {"category_id": "shopping"}

    def test_parse_json_response_invalid(self) -> None:
        """Test parsing invalid JSON raises ValueError."""
        config = AIClientConfig(
            api_key_env="ANTHROPIC_API_KEY",
            model="claude-sonnet-4-5-20250929",
        )
        client = AIClient(config=config)
        with pytest.raises(ValueError, match="No JSON found"):
            client.parse_json_response("This is not JSON at all")


class TestAICategorizationResult:
    """Tests for AICategorizationResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating a categorization result."""
        result = AICategorizationResult(
            category_id="dining",
            confidence=0.95,
            reasoning="Restaurant name detected",
            tokens_used=150,
            cost=0.001,
        )
        assert result.category_id == "dining"
        assert result.confidence == 0.95
        assert result.reasoning == "Restaurant name detected"

    def test_result_with_subcategory(self) -> None:
        """Test result with subcategory."""
        result = AICategorizationResult(
            category_id="entertainment",
            confidence=0.85,
            reasoning="Streaming service",
            subcategory_id="streaming",
        )
        assert result.subcategory_id == "streaming"


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_empty_batch_result(self) -> None:
        """Test empty batch result initialization."""
        result = BatchResult()
        assert result.results == []
        assert result.total_tokens == 0
        assert result.total_cost == 0.0
        assert result.succeeded == 0
        assert result.failed == 0
        assert result.errors == []

    def test_batch_result_accumulation(self) -> None:
        """Test accumulating results."""
        result = BatchResult()
        result.succeeded = 5
        result.failed = 2
        result.total_tokens = 1000
        result.total_cost = 0.05
        result.errors.append("Error 1")

        assert result.succeeded == 5
        assert result.failed == 2
        assert len(result.errors) == 1


class TestCostEstimate:
    """Tests for CostEstimate dataclass."""

    def test_cost_per_transaction(self) -> None:
        """Test cost per transaction calculation."""
        estimate = CostEstimate(
            input_tokens=10000,
            output_tokens=5000,
            total_tokens=15000,
            estimated_cost=0.50,
            transaction_count=100,
        )
        assert estimate.cost_per_transaction == pytest.approx(0.005)

    def test_cost_per_transaction_zero_count(self) -> None:
        """Test cost per transaction with zero transactions."""
        estimate = CostEstimate(
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            estimated_cost=0.0,
            transaction_count=0,
        )
        assert estimate.cost_per_transaction == 0.0


class TestAIUsageStats:
    """Tests for AIUsageStats dataclass."""

    def test_add_request(self) -> None:
        """Test adding request stats."""
        stats = AIUsageStats()
        stats.add_request(input_tokens=100, output_tokens=50, cost=0.001)
        assert stats.total_requests == 1
        assert stats.total_input_tokens == 100
        assert stats.total_output_tokens == 50
        assert stats.total_cost == pytest.approx(0.001)

        stats.add_request(input_tokens=200, output_tokens=100, cost=0.002)
        assert stats.total_requests == 2
        assert stats.total_input_tokens == 300
        assert stats.total_output_tokens == 150
        assert stats.total_cost == pytest.approx(0.003)


class TestValidationStatus:
    """Tests for ValidationStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert ValidationStatus.VALIDATED.value == "validated"
        assert ValidationStatus.CORRECTED.value == "corrected"
        assert ValidationStatus.UNCERTAIN.value == "uncertain"
        assert ValidationStatus.PENDING.value == "pending"
        assert ValidationStatus.SKIPPED.value == "skipped"
