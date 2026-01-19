"""AI-powered transaction categorization module.

This module provides AI-assisted categorization and validation
of financial transactions using Claude API.

Example usage:
    from financial_consolidator.processing.ai import AICategorizer

    # Create categorizer
    categorizer = AICategorizer.create(config, budget_limit=5.00)

    # Check if AI is available
    if categorizer.is_available:
        # Estimate cost
        estimate = categorizer.estimate_categorization_cost(transactions)
        print(f"Estimated cost: ${estimate.estimated_cost:.2f}")

        # Categorize uncategorized transactions
        result = categorizer.categorize_uncategorized(transactions)
        print(f"Categorized {result.succeeded} transactions for ${result.total_cost:.2f}")
"""

from financial_consolidator.processing.ai.categorizer import AICategorizer
from financial_consolidator.processing.ai.client import (
    AIClient,
    AIClientConfig,
    AIClientError,
    APIKeyNotFoundError,
    BudgetExceededError,
    RateLimitError,
)
from financial_consolidator.processing.ai.cost_estimator import CostEstimator
from financial_consolidator.processing.ai.models import (
    AICategorizationResult,
    AIUsageStats,
    AIValidationResult,
    BatchResult,
    CostEstimate,
    ValidationStatus,
)

__all__ = [
    # Main categorizer
    "AICategorizer",
    # Client
    "AIClient",
    "AIClientConfig",
    # Errors
    "AIClientError",
    "APIKeyNotFoundError",
    "BudgetExceededError",
    "RateLimitError",
    # Cost estimation
    "CostEstimator",
    "CostEstimate",
    # Result models
    "AICategorizationResult",
    "AIValidationResult",
    "BatchResult",
    "ValidationStatus",
    "AIUsageStats",
]
