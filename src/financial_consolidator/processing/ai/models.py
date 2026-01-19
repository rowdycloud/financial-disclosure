"""AI-specific data models for categorization."""

from dataclasses import dataclass, field
from enum import Enum


class ValidationStatus(Enum):
    """Status of AI validation."""

    VALIDATED = "validated"
    CORRECTED = "corrected"
    UNCERTAIN = "uncertain"
    PENDING = "pending"
    SKIPPED = "skipped"


@dataclass
class AICategorizationResult:
    """Result of AI categorization for a single transaction.

    Attributes:
        category_id: The suggested category ID.
        subcategory_id: Optional subcategory ID.
        confidence: AI's confidence in the categorization (0.0-1.0).
        reasoning: Brief explanation of why this category was chosen.
        tokens_used: Number of tokens used for this request.
        cost: Estimated cost in USD.
    """

    category_id: str
    confidence: float
    reasoning: str
    tokens_used: int = 0
    cost: float = 0.0
    subcategory_id: str | None = None


@dataclass
class AIValidationResult:
    """Result of AI validation of a rule-based categorization.

    Attributes:
        status: Whether AI validated, corrected, or was uncertain.
        original_category_id: The category assigned by rules.
        suggested_category_id: AI's suggested category (may match original).
        confidence: AI's confidence in its assessment.
        reasoning: Explanation of the validation decision.
        tokens_used: Number of tokens used for this request.
        cost: Estimated cost in USD.
    """

    status: ValidationStatus
    original_category_id: str
    suggested_category_id: str
    confidence: float
    reasoning: str
    tokens_used: int = 0
    cost: float = 0.0


@dataclass
class CostEstimate:
    """Estimated cost for an AI operation.

    Attributes:
        input_tokens: Estimated input tokens.
        output_tokens: Estimated output tokens.
        total_tokens: Total estimated tokens.
        estimated_cost: Estimated cost in USD.
        transaction_count: Number of transactions in estimate.
    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: float
    transaction_count: int

    @property
    def cost_per_transaction(self) -> float:
        """Average cost per transaction."""
        if self.transaction_count == 0:
            return 0.0
        return self.estimated_cost / self.transaction_count


@dataclass
class BatchResult:
    """Result of batch AI categorization.

    Attributes:
        results: List of categorization results, positionally corresponding to
            input transactions. May contain None for transactions that failed
            to get AI responses.
        total_tokens: Total tokens used.
        total_cost: Total cost in USD.
        succeeded: Number of successful categorizations.
        failed: Number of failed categorizations.
        errors: List of error messages for failures.
    """

    results: list[AICategorizationResult | None] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    succeeded: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class AIUsageStats:
    """Cumulative AI usage statistics for a session.

    Attributes:
        total_requests: Total API requests made.
        total_input_tokens: Total input tokens used.
        total_output_tokens: Total output tokens used.
        total_cost: Total cost in USD.
        validations_performed: Number of validations.
        categorizations_performed: Number of categorizations.
        validations_agreed: Number of validations where AI agreed.
        validations_corrected: Number of validations where AI suggested correction.
    """

    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    validations_performed: int = 0
    categorizations_performed: int = 0
    validations_agreed: int = 0
    validations_corrected: int = 0

    def add_request(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        """Record a completed request."""
        self.total_requests += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
