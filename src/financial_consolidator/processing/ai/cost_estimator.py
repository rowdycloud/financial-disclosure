"""Token and cost estimation for AI categorization."""

from dataclasses import dataclass

from financial_consolidator.processing.ai.models import CostEstimate
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


# Model pricing (per 1M tokens) - Updated for 2025 pricing
# https://www.anthropic.com/pricing
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,   # $3.00 per 1M input tokens
        "output": 15.00,  # $15.00 per 1M output tokens
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
    },
    "claude-3-5-haiku-20241022": {
        "input": 0.80,
        "output": 4.00,
    },
    "claude-3-haiku-20240307": {
        "input": 0.25,
        "output": 1.25,
    },
}

# Average token counts based on typical categorization prompts
AVG_TOKENS_PER_CATEGORY = 15  # "- dining: Dining and Restaurants"
AVG_TOKENS_PER_TRANSACTION = 25  # description + amount + account
AVG_SYSTEM_PROMPT_TOKENS = 200
AVG_OUTPUT_TOKENS_SINGLE = 50  # JSON response for single transaction
AVG_OUTPUT_TOKENS_BATCH_ITEM = 30  # JSON per item in batch (for cost estimation)

# Max tokens buffer per batch item (for API max_tokens parameter)
# Higher than AVG to prevent truncation with verbose reasoning
MAX_TOKENS_PER_BATCH_ITEM = 120
MAX_TOKENS_BUFFER = 100
MAX_OUTPUT_TOKENS_LIMIT = 4096  # Conservative limit that works across all Claude models


@dataclass
class CostEstimator:
    """Estimates tokens and costs for AI categorization operations.

    Attributes:
        model: The model being used for estimation.
        budget_limit: Maximum budget in USD (None for unlimited).
        current_spend: Current accumulated spend in USD.
    """

    model: str = "claude-sonnet-4-5-20250929"
    budget_limit: float | None = None
    current_spend: float = 0.0

    def get_pricing(self) -> dict[str, float]:
        """Get pricing for the configured model."""
        if self.model in MODEL_PRICING:
            return MODEL_PRICING[self.model]
        # Default to sonnet pricing if unknown model
        logger.warning(f"Unknown model {self.model}, using default pricing")
        return MODEL_PRICING["claude-sonnet-4-5-20250929"]

    def estimate_tokens(
        self,
        num_transactions: int,
        num_categories: int,
        is_batch: bool = False,
        batch_size: int = 20,
    ) -> tuple[int, int]:
        """Estimate input and output tokens for categorization.

        Args:
            num_transactions: Number of transactions to categorize.
            num_categories: Number of available categories.
            is_batch: Whether using batch mode.
            batch_size: Transactions per batch if batching.

        Returns:
            Tuple of (input_tokens, output_tokens).
        """
        category_tokens = num_categories * AVG_TOKENS_PER_CATEGORY

        if is_batch:
            num_batches = (num_transactions + batch_size - 1) // batch_size
            # Each batch has system prompt + categories + N transactions
            input_per_batch = (
                AVG_SYSTEM_PROMPT_TOKENS
                + category_tokens
                + (batch_size * AVG_TOKENS_PER_TRANSACTION)
            )
            output_per_batch = batch_size * AVG_OUTPUT_TOKENS_BATCH_ITEM

            input_tokens = num_batches * input_per_batch
            output_tokens = num_batches * output_per_batch
        else:
            # Single transaction mode
            input_per_txn = (
                AVG_SYSTEM_PROMPT_TOKENS
                + category_tokens
                + AVG_TOKENS_PER_TRANSACTION
            )
            input_tokens = num_transactions * input_per_txn
            output_tokens = num_transactions * AVG_OUTPUT_TOKENS_SINGLE

        return input_tokens, output_tokens

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost for given token counts.

        Args:
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        pricing = self.get_pricing()
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def estimate_categorization(
        self,
        num_transactions: int,
        num_categories: int,
        is_batch: bool = True,
        batch_size: int = 20,
    ) -> CostEstimate:
        """Estimate cost for categorizing transactions.

        Args:
            num_transactions: Number of transactions to categorize.
            num_categories: Number of available categories.
            is_batch: Whether to use batch mode.
            batch_size: Transactions per batch.

        Returns:
            CostEstimate with token and cost projections.
        """
        input_tokens, output_tokens = self.estimate_tokens(
            num_transactions, num_categories, is_batch, batch_size
        )
        cost = self.estimate_cost(input_tokens, output_tokens)

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost=cost,
            transaction_count=num_transactions,
        )

    def estimate_validation(
        self,
        num_transactions: int,
        num_categories: int,
    ) -> CostEstimate:
        """Estimate cost for validating categorizations.

        Validation uses slightly less tokens than categorization
        since it's checking rather than discovering.

        Args:
            num_transactions: Number of transactions to validate.
            num_categories: Number of available categories.

        Returns:
            CostEstimate with token and cost projections.
        """
        # Validation prompts are slightly smaller
        input_tokens = num_transactions * (
            AVG_SYSTEM_PROMPT_TOKENS
            + (num_categories * AVG_TOKENS_PER_CATEGORY)
            + AVG_TOKENS_PER_TRANSACTION
            + 20  # Current category info
        )
        output_tokens = num_transactions * AVG_OUTPUT_TOKENS_SINGLE

        cost = self.estimate_cost(input_tokens, output_tokens)

        return CostEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_cost=cost,
            transaction_count=num_transactions,
        )

    def check_budget(self, estimated_cost: float) -> tuple[bool, str]:
        """Check if estimated cost is within budget.

        Args:
            estimated_cost: The estimated cost to check.

        Returns:
            Tuple of (is_within_budget, message).
        """
        if self.budget_limit is None:
            return True, "No budget limit set"

        remaining = self.budget_limit - self.current_spend
        if estimated_cost > remaining:
            return False, (
                f"Estimated cost ${estimated_cost:.4f} exceeds remaining budget "
                f"${remaining:.4f} (limit: ${self.budget_limit:.2f}, "
                f"spent: ${self.current_spend:.4f})"
            )

        return True, f"Within budget (${remaining:.4f} remaining)"

    def record_spend(self, amount: float) -> None:
        """Record actual spend.

        Note: This operation is not thread-safe. Budget check and spend
        recording are not atomic, so concurrent usage could exceed the
        budget limit. This is acceptable for the current single-threaded
        CLI usage pattern.

        Args:
            amount: Amount spent in USD.
        """
        self.current_spend += amount
        logger.debug(f"Recorded spend: ${amount:.4f}, total: ${self.current_spend:.4f}")

    def format_estimate(self, estimate: CostEstimate) -> str:
        """Format a cost estimate for display.

        Args:
            estimate: The estimate to format.

        Returns:
            Human-readable string.
        """
        return (
            f"Estimated cost: ${estimate.estimated_cost:.4f}\n"
            f"  Transactions: {estimate.transaction_count}\n"
            f"  Input tokens: ~{estimate.input_tokens:,}\n"
            f"  Output tokens: ~{estimate.output_tokens:,}\n"
            f"  Cost per transaction: ${estimate.cost_per_transaction:.6f}"
        )
