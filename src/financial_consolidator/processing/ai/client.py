"""Anthropic API client wrapper with rate limiting and retries."""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from financial_consolidator.processing.ai.cost_estimator import CostEstimator
from financial_consolidator.processing.ai.models import AIUsageStats
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)
_console = Console(stderr=True)  # Use stderr to avoid conflicts with Progress bar on stdout


class AIClientError(Exception):
    """Base exception for AI client errors."""

    pass


class APIKeyNotFoundError(AIClientError):
    """Raised when API key is not found."""

    pass


class RateLimitError(AIClientError):
    """Raised when rate limit is exceeded."""

    pass


class BudgetExceededError(AIClientError):
    """Raised when budget limit is exceeded."""

    pass


@dataclass
class AIClientConfig:
    """Configuration for the AI client.

    Attributes:
        api_key_env: Environment variable name for API key.
        model: Model to use for requests.
        max_tokens: Maximum tokens for response.
        requests_per_minute: Rate limit.
        retry_attempts: Number of retry attempts.
        retry_delay: Initial delay between retries (exponential backoff).
        budget_limit: Maximum spend in USD (None for unlimited).
    """

    api_key_env: str = "ANTHROPIC_API_KEY"
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 150
    requests_per_minute: int = 20
    retry_attempts: int = 3
    retry_delay: float = 1.0
    budget_limit: float | None = 5.00


@dataclass
class AIClient:
    """Wrapper for Anthropic API with rate limiting and cost tracking.

    This client provides:
    - Lazy initialization (only connects when first used)
    - Rate limiting to avoid API throttling
    - Automatic retry with exponential backoff
    - Cost tracking per request
    - Budget enforcement
    """

    config: AIClientConfig = field(default_factory=AIClientConfig)
    _client: Any = field(default=None, init=False, repr=False)
    _request_count: int = field(default=0, init=False)
    _request_window_start: float = field(default=0.0, init=False)
    _initialized: bool = field(default=False, init=False)

    cost_estimator: CostEstimator = field(init=False)
    usage_stats: AIUsageStats = field(default_factory=AIUsageStats)

    def __post_init__(self) -> None:
        """Initialize cost estimator."""
        self.cost_estimator = CostEstimator(
            model=self.config.model,
            budget_limit=self.config.budget_limit,
        )

    @property
    def is_available(self) -> bool:
        """Check if AI client can be initialized (API key exists)."""
        return bool(os.environ.get(self.config.api_key_env))

    def _ensure_initialized(self) -> None:
        """Lazily initialize the Anthropic client."""
        if self._initialized:
            return

        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise APIKeyNotFoundError(
                f"API key not found in environment variable: {self.config.api_key_env}"
            )

        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
            self._initialized = True
            logger.info(f"AI client initialized with model: {self.config.model}")
        except ImportError as err:
            raise AIClientError(
                "anthropic package not installed. Run: pip install anthropic"
            ) from err

    def _wait_for_rate_limit(self) -> None:
        """Wait if necessary to respect rate limits."""
        current_time = time.time()

        # Reset window if it's been more than a minute
        if current_time - self._request_window_start > 60:
            self._request_count = 0
            self._request_window_start = current_time

        # Check if we've hit the rate limit
        if self._request_count >= self.config.requests_per_minute:
            wait_time = 60 - (current_time - self._request_window_start)
            if wait_time > 0:
                _console.print(f"[yellow]Rate limit reached, waiting {wait_time:.0f}s...[/yellow]")
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self._request_count = 0
                self._request_window_start = time.time()

    def _make_request(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, int, int]:
        """Make a single API request with retry logic.

        Args:
            system_prompt: The system prompt.
            user_prompt: The user prompt.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens).

        Raises:
            AIClientError: If request fails after all retries.
        """
        self._ensure_initialized()
        self._wait_for_rate_limit()

        last_error = None
        delay = self.config.retry_delay

        for attempt in range(self.config.retry_attempts):
            try:
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    timeout=60.0,
                )

                self._request_count += 1

                # Extract response (check both truthy and length to avoid IndexError)
                if response.content and len(response.content) > 0:
                    content = response.content[0].text
                else:
                    content = ""
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                # Track cost
                cost = self.cost_estimator.estimate_cost(input_tokens, output_tokens)
                self.cost_estimator.record_spend(cost)
                self.usage_stats.add_request(input_tokens, output_tokens, cost)

                logger.debug(
                    f"Request completed: {input_tokens} in, {output_tokens} out, ${cost:.4f}"
                )

                return content, input_tokens, output_tokens

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Check for rate limit errors
                if "rate" in error_msg or "429" in error_msg:
                    _console.print(f"[yellow]Rate limited, waiting {delay:.0f}s before retry...[/yellow]")
                    logger.warning(f"Rate limited, waiting {delay}s before retry")
                    time.sleep(delay)
                    delay *= 2
                    continue

                # Check for overloaded errors
                if "overloaded" in error_msg or "529" in error_msg:
                    _console.print(f"[yellow]API overloaded, waiting {delay:.0f}s before retry...[/yellow]")
                    logger.warning(f"API overloaded, waiting {delay}s before retry")
                    time.sleep(delay)
                    delay *= 2
                    continue

                # For other errors, retry with backoff
                if attempt < self.config.retry_attempts - 1:
                    _console.print(f"[yellow]Request failed, retrying in {delay:.0f}s...[/yellow]")
                    logger.warning(f"Request failed: {e}, retrying in {delay}s")
                    time.sleep(delay)
                    delay *= 2
                else:
                    raise AIClientError(f"Request failed after {attempt + 1} attempts: {e}") from e

        raise AIClientError(f"Request failed: {last_error}")

    def send_message(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, int, int]:
        """Send a message to the AI and get response.

        Args:
            system_prompt: The system prompt.
            user_prompt: The user prompt.

        Returns:
            Tuple of (response_text, input_tokens, output_tokens).

        Raises:
            BudgetExceededError: If budget would be exceeded.
            AIClientError: If request fails.
        """
        # Estimate cost and check budget
        estimated_tokens = len(system_prompt + user_prompt) // 4 + self.config.max_tokens
        estimated_cost = self.cost_estimator.estimate_cost(
            estimated_tokens, self.config.max_tokens
        )

        within_budget, msg = self.cost_estimator.check_budget(estimated_cost)
        if not within_budget:
            raise BudgetExceededError(msg)

        return self._make_request(system_prompt, user_prompt)

    def parse_json_response(self, response: str) -> dict[str, Any] | list[Any]:
        """Parse a JSON response from the AI.

        Handles cases where the response contains extra text around the JSON.

        Args:
            response: The response string.

        Returns:
            Parsed JSON as a dictionary or list.

        Raises:
            ValueError: If JSON cannot be parsed.
        """
        # Try direct parse first
        try:
            result = json.loads(response)
            if isinstance(result, (dict, list)):
                return result
            raise ValueError(f"JSON parsed to unexpected type: {type(result)}")
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from the response
        # Look for {...} or [...]
        start_brace = response.find("{")
        start_bracket = response.find("[")

        if start_brace == -1 and start_bracket == -1:
            raise ValueError(f"No JSON found in response: {response[:100]}")

        # Find the appropriate start (use brace if both exist and brace comes first)
        if start_brace == -1:
            start = start_bracket
        elif start_bracket == -1:
            start = start_brace
        else:
            start = min(start_brace, start_bracket)

        # Find matching end
        depth = 0
        for i, char in enumerate(response[start:], start):
            if char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        result = json.loads(response[start : i + 1])
                        if isinstance(result, (dict, list)):
                            return result
                        raise ValueError(f"JSON parsed to unexpected type: {type(result)}")
                    except json.JSONDecodeError:
                        break

        raise ValueError(f"Could not parse JSON from response: {response[:200]}")

    def get_usage_summary(self) -> str:
        """Get a summary of API usage.

        Returns:
            Human-readable usage summary.
        """
        stats = self.usage_stats
        return (
            f"AI Usage Summary:\n"
            f"  Total requests: {stats.total_requests}\n"
            f"  Input tokens: {stats.total_input_tokens:,}\n"
            f"  Output tokens: {stats.total_output_tokens:,}\n"
            f"  Total cost: ${stats.total_cost:.4f}\n"
            f"  Validations: {stats.validations_performed} "
            f"({stats.validations_agreed} agreed, {stats.validations_corrected} corrected)\n"
            f"  Categorizations: {stats.categorizations_performed}"
        )
