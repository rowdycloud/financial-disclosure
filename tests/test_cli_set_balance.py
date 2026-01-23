"""Tests for set_balance_command CLI function."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from financial_consolidator.cli import set_balance_command
from financial_consolidator.models.account import Account, AccountType


class TestSetBalanceCommand:
    """Tests for set_balance_command function."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock config with test accounts."""
        config = MagicMock()
        config.accounts = {
            "checking": Account(
                id="checking",
                name="Test Checking",
                account_type=AccountType.CHECKING,
            ),
            "savings": Account(
                id="savings",
                name="Test Savings",
                account_type=AccountType.SAVINGS,
            ),
        }
        return config

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create a temporary config directory."""
        return tmp_path

    def test_valid_balance_with_date(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test setting a valid balance with an explicit date."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts") as mock_save,
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="1234.56",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            assert mock_config.accounts["checking"].opening_balance == Decimal("1234.56")
            assert mock_config.accounts["checking"].opening_balance_date == date(2024, 1, 15)
            mock_save.assert_called_once()

    def test_valid_balance_defaults_to_today(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that balance date defaults to today when not specified."""
        fixed_today = date(2024, 6, 15)
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts"),
            patch("financial_consolidator.cli.date") as mock_date,
        ):
            mock_date.today.return_value = fixed_today
            mock_date.side_effect = lambda *args, **kwargs: date(*args, **kwargs)
            result = set_balance_command(
                account_id="checking",
                balance_amount="500.00",
                balance_date=None,
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            assert mock_config.accounts["checking"].opening_balance_date == fixed_today

    def test_invalid_balance_non_numeric(self, temp_config_dir: Path) -> None:
        """Test that non-numeric balance amounts are rejected."""
        result = set_balance_command(
            account_id="checking",
            balance_amount="not-a-number",
            balance_date=date(2024, 1, 15),
            accounts_path=None,
            config_dir=temp_config_dir,
        )

        assert result == 1

    def test_invalid_balance_infinity(self, temp_config_dir: Path) -> None:
        """Test that infinity is rejected."""
        result = set_balance_command(
            account_id="checking",
            balance_amount="inf",
            balance_date=date(2024, 1, 15),
            accounts_path=None,
            config_dir=temp_config_dir,
        )

        assert result == 1

    def test_invalid_balance_nan(self, temp_config_dir: Path) -> None:
        """Test that NaN is rejected."""
        result = set_balance_command(
            account_id="checking",
            balance_amount="nan",
            balance_date=date(2024, 1, 15),
            accounts_path=None,
            config_dir=temp_config_dir,
        )

        assert result == 1

    def test_future_date_rejected(self, temp_config_dir: Path) -> None:
        """Test that future dates are rejected."""
        future_date = date.today() + timedelta(days=1)
        result = set_balance_command(
            account_id="checking",
            balance_amount="100.00",
            balance_date=future_date,
            accounts_path=None,
            config_dir=temp_config_dir,
        )

        assert result == 1

    def test_date_before_1970_rejected(self, temp_config_dir: Path) -> None:
        """Test that dates before Unix epoch (1970) are rejected."""
        result = set_balance_command(
            account_id="checking",
            balance_amount="100.00",
            balance_date=date(1969, 12, 31),
            accounts_path=None,
            config_dir=temp_config_dir,
        )

        assert result == 1

    def test_date_at_1970_boundary_accepted(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that exactly 1970-01-01 is accepted."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts"),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="100.00",
                balance_date=date(1970, 1, 1),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            assert mock_config.accounts["checking"].opening_balance_date == date(1970, 1, 1)

    def test_account_not_found(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test error when account doesn't exist."""
        with patch("financial_consolidator.cli.load_config", return_value=mock_config):
            result = set_balance_command(
                account_id="nonexistent",
                balance_amount="100.00",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 1

    def test_config_file_not_found(self, temp_config_dir: Path) -> None:
        """Test error when config file doesn't exist."""
        with patch(
            "financial_consolidator.cli.load_config",
            side_effect=FileNotFoundError("Config not found"),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="100.00",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 1

    def test_negative_balance_accepted(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that negative balances are accepted (for credit cards)."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts"),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="-500.00",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            assert mock_config.accounts["checking"].opening_balance == Decimal("-500.00")

    def test_balance_rounded_to_two_decimals(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that balances with more than 2 decimals are rounded."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts"),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="100.999",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            # 100.999 rounds to 101.00 (third decimal 9 >= 5, so second decimal rounds up)
            assert mock_config.accounts["checking"].opening_balance == Decimal("101.00")

    def test_zero_balance_accepted(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that zero balance is accepted."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts"),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="0",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            assert mock_config.accounts["checking"].opening_balance == Decimal("0.00")

    def test_save_error_handled(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that save errors are handled gracefully."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch(
                "financial_consolidator.cli.save_accounts",
                side_effect=OSError("Permission denied"),
            ),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="100.00",
                balance_date=date(2024, 1, 15),
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 1

    def test_leap_year_date_accepted(
        self, mock_config: MagicMock, temp_config_dir: Path
    ) -> None:
        """Test that leap year dates are handled correctly."""
        with (
            patch("financial_consolidator.cli.load_config", return_value=mock_config),
            patch("financial_consolidator.cli.save_accounts"),
        ):
            result = set_balance_command(
                account_id="checking",
                balance_amount="100.00",
                balance_date=date(2024, 2, 29),  # 2024 is a leap year
                accounts_path=None,
                config_dir=temp_config_dir,
            )

            assert result == 0
            assert mock_config.accounts["checking"].opening_balance_date == date(2024, 2, 29)
