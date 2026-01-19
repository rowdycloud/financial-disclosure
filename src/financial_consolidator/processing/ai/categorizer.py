"""AI-powered transaction categorizer."""

from dataclasses import dataclass

from financial_consolidator.config import Config
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.processing.ai.client import AIClient, AIClientConfig
from financial_consolidator.processing.ai.models import (
    AICategorizationResult,
    AIValidationResult,
    BatchResult,
    CostEstimate,
    ValidationStatus,
)
from financial_consolidator.processing.ai.prompts import (
    CATEGORIZATION_SYSTEM_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
    build_batch_categorization_prompt,
    build_categorization_prompt,
    build_validation_prompt,
)
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class AICategorizer:
    """AI-powered categorizer for financial transactions.

    This categorizer can:
    1. Categorize uncategorized transactions
    2. Validate low-confidence rule-based categorizations
    3. Provide cost estimates before making API calls

    Attributes:
        config: Application configuration.
        client: AI API client.
        validation_threshold: Confidence threshold below which to validate.
        correction_threshold: AI confidence threshold for accepting corrections.
    """

    config: Config
    client: AIClient
    validation_threshold: float = 0.7
    correction_threshold: float = 0.9

    @classmethod
    def create(
        cls,
        config: Config,
        api_key_env: str = "ANTHROPIC_API_KEY",
        model: str = "claude-sonnet-4-5-20250929",
        budget_limit: float | None = 5.00,
        validation_threshold: float = 0.7,
    ) -> "AICategorizer":
        """Create an AI categorizer with default settings.

        Args:
            config: Application configuration.
            api_key_env: Environment variable for API key.
            model: Model to use.
            budget_limit: Maximum budget in USD.
            validation_threshold: Confidence threshold for validation.

        Returns:
            Configured AICategorizer instance.
        """
        client_config = AIClientConfig(
            api_key_env=api_key_env,
            model=model,
            budget_limit=budget_limit,
        )
        client = AIClient(config=client_config)

        return cls(
            config=config,
            client=client,
            validation_threshold=validation_threshold,
        )

    @property
    def is_available(self) -> bool:
        """Check if AI categorization is available."""
        return self.client.is_available

    def _get_category_list(self) -> list[dict[str, str]]:
        """Get list of categories for prompts."""
        return [
            {"id": cat.id, "name": cat.name}
            for cat in self.config.categories.values()
            if cat.category_type is not None  # Skip internal categories
        ]

    def estimate_categorization_cost(
        self,
        transactions: list[Transaction],
        use_batch: bool = True,
    ) -> CostEstimate:
        """Estimate cost to categorize transactions.

        Args:
            transactions: Transactions to categorize.
            use_batch: Whether to use batch mode.

        Returns:
            Cost estimate.
        """
        return self.client.cost_estimator.estimate_categorization(
            num_transactions=len(transactions),
            num_categories=len(self.config.categories),
            is_batch=use_batch,
        )

    def estimate_validation_cost(
        self,
        transactions: list[Transaction],
    ) -> CostEstimate:
        """Estimate cost to validate transactions.

        Args:
            transactions: Transactions to validate.

        Returns:
            Cost estimate.
        """
        return self.client.cost_estimator.estimate_validation(
            num_transactions=len(transactions),
            num_categories=len(self.config.categories),
        )

    def categorize_transaction(
        self,
        transaction: Transaction,
    ) -> AICategorizationResult:
        """Categorize a single transaction using AI.

        Args:
            transaction: The transaction to categorize.

        Returns:
            AICategorizationResult with category and confidence.
        """
        categories = self._get_category_list()
        prompt = build_categorization_prompt(
            description=transaction.description,
            amount=float(transaction.amount),
            account_name=transaction.account_name,
            categories=categories,
        )

        response, input_tokens, output_tokens = self.client.send_message(
            CATEGORIZATION_SYSTEM_PROMPT, prompt
        )

        cost = self.client.cost_estimator.estimate_cost(input_tokens, output_tokens)

        try:
            data = self.client.parse_json_response(response)
            if not isinstance(data, dict):
                raise ValueError("Expected dict response from AI")
            # Clamp confidence to valid 0.0-1.0 range
            raw_confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, raw_confidence))
            result = AICategorizationResult(
                category_id=data.get("category_id", "uncategorized"),
                confidence=confidence,
                reasoning=data.get("reasoning", ""),
                tokens_used=input_tokens + output_tokens,
                cost=cost,
            )
            self.client.usage_stats.categorizations_performed += 1
            return result

        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return AICategorizationResult(
                category_id="uncategorized",
                confidence=0.0,
                reasoning=f"Parse error: {e}",
                tokens_used=input_tokens + output_tokens,
                cost=cost,
            )

    def validate_categorization(
        self,
        transaction: Transaction,
    ) -> AIValidationResult:
        """Validate a rule-based categorization using AI.

        Args:
            transaction: The categorized transaction to validate.

        Returns:
            AIValidationResult with validation decision.
        """
        if not transaction.category:
            return AIValidationResult(
                status=ValidationStatus.SKIPPED,
                original_category_id="",
                suggested_category_id="",
                confidence=0.0,
                reasoning="Transaction has no category to validate",
            )

        current_category = self.config.categories.get(transaction.category)
        current_name = current_category.name if current_category else transaction.category

        categories = self._get_category_list()
        prompt = build_validation_prompt(
            description=transaction.description,
            amount=float(transaction.amount),
            current_category=transaction.category,
            current_category_name=current_name,
            categories=categories,
        )

        response, input_tokens, output_tokens = self.client.send_message(
            VALIDATION_SYSTEM_PROMPT, prompt
        )

        cost = self.client.cost_estimator.estimate_cost(input_tokens, output_tokens)
        self.client.usage_stats.validations_performed += 1

        try:
            data = self.client.parse_json_response(response)
            if not isinstance(data, dict):
                raise ValueError("Expected dict response from AI")
            validated = data.get("validated", False)
            suggested = data.get("suggested_category_id", transaction.category)
            # Clamp confidence to valid 0.0-1.0 range
            raw_confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, raw_confidence))
            reasoning = data.get("reasoning", "")

            if validated is True:
                status = ValidationStatus.VALIDATED
                self.client.usage_stats.validations_agreed += 1
            elif confidence >= self.correction_threshold:
                status = ValidationStatus.CORRECTED
                self.client.usage_stats.validations_corrected += 1
            else:
                status = ValidationStatus.UNCERTAIN

            return AIValidationResult(
                status=status,
                original_category_id=transaction.category,
                suggested_category_id=suggested,
                confidence=confidence,
                reasoning=reasoning,
                tokens_used=input_tokens + output_tokens,
                cost=cost,
            )

        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse validation response: {e}")
            return AIValidationResult(
                status=ValidationStatus.UNCERTAIN,
                original_category_id=transaction.category,
                suggested_category_id=transaction.category,
                confidence=0.0,
                reasoning=f"Parse error: {e}",
                tokens_used=input_tokens + output_tokens,
                cost=cost,
            )

    def categorize_batch(
        self,
        transactions: list[Transaction],
        batch_size: int = 20,
        apply_results: bool = True,
    ) -> BatchResult:
        """Categorize multiple transactions in batches.

        Args:
            transactions: Transactions to categorize.
            batch_size: Transactions per batch.
            apply_results: Whether to apply results to transactions.

        Returns:
            BatchResult with all results and statistics.
        """
        result = BatchResult()
        categories = self._get_category_list()

        # Pre-allocate results list to maintain transaction order
        result.results = [None] * len(transactions)  # type: ignore[list-item]

        for batch_start in range(0, len(transactions), batch_size):
            batch = transactions[batch_start : batch_start + batch_size]

            # Build batch data
            txn_data = [
                {
                    "description": t.description,
                    "amount": float(t.amount),
                    "account": t.account_name,
                }
                for t in batch
            ]

            prompt = build_batch_categorization_prompt(txn_data, categories)

            try:
                response, input_tokens, output_tokens = self.client.send_message(
                    CATEGORIZATION_SYSTEM_PROMPT, prompt
                )
                cost = self.client.cost_estimator.estimate_cost(input_tokens, output_tokens)
                result.total_tokens += input_tokens + output_tokens
                result.total_cost += cost

                # Parse batch response
                data = self.client.parse_json_response(response)

                if isinstance(data, list):
                    # Track processed indices to prevent double-counting from duplicate AI responses
                    processed_indices: set[int] = set()

                    for item in data:
                        # Get index from AI response (1-based) and convert to 0-based
                        raw_idx = item.get("index")
                        if raw_idx is None:
                            logger.warning("AI response missing index field")
                            continue
                        try:
                            local_idx = int(raw_idx) - 1
                        except (ValueError, TypeError):
                            logger.warning(f"AI returned non-numeric index: {raw_idx}")
                            result.failed += 1
                            result.errors.append(f"AI returned non-numeric index: {raw_idx}")
                            continue

                        # Validate index is >= 1 (1-based indexing from prompt)
                        if local_idx < 0:
                            logger.warning(f"AI returned invalid index {raw_idx} (must be >= 1)")
                            result.failed += 1
                            result.errors.append(f"AI returned invalid index {raw_idx}")
                            continue

                        if local_idx < len(batch):
                            # Skip duplicate indices to prevent double-counting
                            if local_idx in processed_indices:
                                logger.warning(f"AI returned duplicate index {raw_idx}, skipping")
                                continue
                            processed_indices.add(local_idx)

                            # Clamp confidence to valid 0.0-1.0 range
                            raw_conf = float(item.get("confidence", 0.5))
                            conf = max(0.0, min(1.0, raw_conf))
                            cat_result = AICategorizationResult(
                                category_id=item.get("category_id", "uncategorized"),
                                confidence=conf,
                                reasoning=item.get("reasoning", ""),
                                tokens_used=0,  # Tracked at batch level
                                cost=0,
                            )
                            # Store at correct global position
                            global_idx = batch_start + local_idx
                            result.results[global_idx] = cat_result

                            # Apply to transaction (matches single mode semantics)
                            if cat_result.category_id != "uncategorized":
                                result.succeeded += 1
                            else:
                                result.failed += 1

                            if apply_results and cat_result.category_id != "uncategorized":
                                txn = batch[local_idx]
                                txn.assign_category(
                                    category_id=cat_result.category_id,
                                    source="ai",
                                    confidence=cat_result.confidence,
                                    confidence_factors=[f"AI: {cat_result.reasoning}"],
                                )
                                self.client.usage_stats.categorizations_performed += 1
                        else:
                            logger.warning(f"AI returned invalid index {raw_idx}")
                            result.failed += 1
                            result.errors.append(f"AI returned invalid index {raw_idx}")
                else:
                    batch_num = batch_start // batch_size
                    result.errors.append(f"Unexpected response format for batch {batch_num}")
                    result.failed += len(batch)

            except Exception as e:
                logger.error(f"Batch categorization failed: {e}")
                result.errors.append(str(e))
                result.failed += len(batch)

        # Count transactions that didn't get results (None entries)
        # Note: None entries are preserved to maintain positional correspondence
        # with the input transaction list, so callers can use zip(transactions, results)
        none_count = sum(1 for r in result.results if r is None)
        if none_count > 0:
            # Identify which transactions didn't get results for debugging
            missing_indices = [i for i, r in enumerate(result.results) if r is None]
            # Log up to 10 missing indices to avoid spam
            indices_display = missing_indices[:10]
            suffix = f"... and {len(missing_indices) - 10} more" if len(missing_indices) > 10 else ""
            logger.warning(
                f"{none_count} transactions received no AI response "
                f"(indices: {indices_display}{suffix})"
            )
            result.failed += none_count

        return result

    def validate_low_confidence(
        self,
        transactions: list[Transaction],
        apply_corrections: bool = True,
    ) -> list[AIValidationResult]:
        """Validate all transactions below the confidence threshold.

        Args:
            transactions: All transactions (will filter for low confidence).
            apply_corrections: Whether to apply AI corrections.

        Returns:
            List of validation results.
        """
        results = []

        # Filter for categorized transactions with low confidence
        to_validate = [
            t for t in transactions
            if t.category
            and not t.is_uncategorized
            and t.confidence_score < self.validation_threshold
        ]

        logger.info(f"Validating {len(to_validate)} low-confidence categorizations")

        for txn in to_validate:
            result = self.validate_categorization(txn)
            results.append(result)

            # Apply correction if confident
            if (
                apply_corrections
                and result.status == ValidationStatus.CORRECTED
                and result.suggested_category_id != txn.category
            ):
                txn.assign_category(
                    category_id=result.suggested_category_id,
                    source="ai_correction",
                    confidence=result.confidence,
                    confidence_factors=[f"AI correction: {result.reasoning}"],
                )
                logger.info(
                    f"Corrected '{txn.description[:40]}' from {result.original_category_id} "
                    f"to {result.suggested_category_id}"
                )

        return results

    def categorize_uncategorized(
        self,
        transactions: list[Transaction],
        use_batch: bool = True,
        batch_size: int = 20,
    ) -> BatchResult:
        """Categorize all uncategorized transactions.

        Args:
            transactions: All transactions (will filter for uncategorized).
            use_batch: Whether to use batch mode.
            batch_size: Transactions per batch if batching.

        Returns:
            BatchResult with results and statistics.
        """
        # Filter for uncategorized
        uncategorized = [t for t in transactions if t.is_uncategorized]

        logger.info(f"Categorizing {len(uncategorized)} uncategorized transactions")

        if not uncategorized:
            return BatchResult()

        if use_batch:
            return self.categorize_batch(uncategorized, batch_size)
        else:
            # Single transaction mode
            result = BatchResult()
            for txn in uncategorized:
                try:
                    cat_result = self.categorize_transaction(txn)
                    result.results.append(cat_result)
                    result.total_tokens += cat_result.tokens_used
                    result.total_cost += cat_result.cost

                    if cat_result.category_id != "uncategorized":
                        txn.assign_category(
                            category_id=cat_result.category_id,
                            source="ai",
                            confidence=cat_result.confidence,
                            confidence_factors=[f"AI: {cat_result.reasoning}"],
                        )
                        result.succeeded += 1
                    else:
                        result.failed += 1

                except Exception as e:
                    logger.error(f"Categorization failed for '{txn.description}': {e}")
                    result.errors.append(str(e))
                    result.failed += 1

            return result

    def get_usage_summary(self) -> str:
        """Get AI usage summary."""
        return self.client.get_usage_summary()
