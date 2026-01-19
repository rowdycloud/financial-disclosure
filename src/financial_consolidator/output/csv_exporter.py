"""CSV exporter for Google Sheets compatibility."""

import csv
import re
from pathlib import Path
from typing import Optional

from financial_consolidator.config import Config
from financial_consolidator.models.report import PLSummary
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.date_utils import date_to_iso
from financial_consolidator.utils.logging_config import get_logger
from financial_consolidator.utils.sanitize import sanitize_for_csv

logger = get_logger(__name__)

# Characters that are unsafe for filenames across platforms (Windows, macOS, Linux)
# Includes: < > : " / \ | ? * and control characters
_UNSAFE_FILENAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use in filenames.

    Replaces unsafe characters with underscores and handles whitespace.

    Args:
        name: String to sanitize.

    Returns:
        Safe filename component.
    """
    # Replace unsafe characters with underscore
    safe = _UNSAFE_FILENAME_PATTERN.sub("_", name)
    # Replace whitespace with underscore
    safe = re.sub(r'\s+', "_", safe)
    # Remove leading/trailing underscores and collapse multiple underscores
    safe = re.sub(r'_+', "_", safe).strip("_")
    return safe or "unknown"


class CSVExporter:
    """Exports financial data to CSV files for Google Sheets import.

    Creates separate CSV files for each sheet type in the output directory:
    - pl_summary.csv
    - all_transactions.csv
    - account_{name}.csv (one per account)
    - category_analysis.csv
    - anomalies.csv
    """

    def __init__(self, config: Config):
        """Initialize CSV exporter.

        Args:
            config: Application configuration.
        """
        self.config = config
        self.output_config = config.output

    def export(
        self,
        base_path: Path,
        transactions: list[Transaction],
        date_gaps: Optional[list[dict[str, object]]],
        pl_summary: PLSummary,
    ) -> list[Path]:
        """Export all data to CSV files.

        Args:
            base_path: Base path for output (e.g., ./output/analysis.xlsx).
                       CSV files will use this base with different suffixes.
            transactions: List of processed transactions.
            date_gaps: Optional list of date gap anomalies.
            pl_summary: Pre-computed P&L summary data.

        Returns:
            List of paths to created CSV files.
        """
        base_dir = base_path.parent
        base_dir.mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []

        # Export each sheet type
        files = [
            self._export_pl_summary(base_dir, pl_summary),
            self._export_all_transactions(base_dir, transactions),
            self._export_category_analysis(base_dir, transactions),
            self._export_anomalies(base_dir, transactions, date_gaps or []),
        ]
        created_files.extend(f for f in files if f)

        # Export per-account files
        account_files = self._export_account_sheets(base_dir, transactions)
        created_files.extend(account_files)

        logger.info(f"Exported {len(created_files)} CSV files")
        return created_files

    def _export_pl_summary(
        self,
        base_dir: Path,
        pl_summary: PLSummary,
    ) -> Path:
        """Export P&L Summary to CSV.

        Args:
            base_dir: Output directory.
            pl_summary: Pre-computed P&L summary data.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "pl_summary.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Report metadata header
            writer.writerow(["REPORT SUMMARY", ""])
            writer.writerow(["Period", pl_summary.period_display])
            writer.writerow(["Accounts", pl_summary.accounts_display])
            writer.writerow([])

            # Income section
            writer.writerow(["INCOME", ""])
            for cat, amount in sorted(pl_summary.income_by_category.items()):
                writer.writerow([sanitize_for_csv(cat), f"{float(amount):.2f}"])
            writer.writerow(["Total Income", f"{float(pl_summary.total_income):.2f}"])
            writer.writerow([])

            # Expense section
            writer.writerow(["EXPENSES", ""])
            for cat, amount in sorted(pl_summary.expense_by_category.items()):
                writer.writerow([sanitize_for_csv(cat), f"{float(amount):.2f}"])
            writer.writerow(["Total Expenses", f"{float(pl_summary.total_expenses):.2f}"])
            writer.writerow([])

            # Net income
            writer.writerow(["NET INCOME", f"{float(pl_summary.net_income):.2f}"])
            writer.writerow([])

            # Transfers memo
            writer.writerow(["TRANSFERS", ""])
            writer.writerow(["(Money moved between accounts - not counted as income or expense)", ""])
            for cat, amount in sorted(pl_summary.transfer_by_category.items()):
                writer.writerow([sanitize_for_csv(cat), f"{float(amount):.2f}"])
            writer.writerow(["Total Transfers", f"{float(pl_summary.total_transfers):.2f}"])

        logger.info(f"Exported P&L Summary to {output_path}")
        return output_path

    def _export_all_transactions(
        self,
        base_dir: Path,
        transactions: list[Transaction],
    ) -> Path:
        """Export Master List to CSV.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "all_transactions.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Headers as specified
            writer.writerow([
                "Date", "Account", "Description", "Category", "Sub-category",
                "Amount", "Balance", "Source File", "Duplicate Flag", "Uncategorized Flag"
            ])

            # Sort and write data
            sorted_txns = sorted(
                transactions, key=lambda t: (t.date, t.account_name, t.description)
            )

            for txn in sorted_txns:
                writer.writerow([
                    date_to_iso(txn.date),
                    sanitize_for_csv(txn.account_name),
                    sanitize_for_csv(txn.description),
                    sanitize_for_csv(self._get_category_name(txn.category) or ""),
                    sanitize_for_csv(self._get_category_name(txn.subcategory) or ""),
                    f"{txn.amount:.2f}",
                    f"{txn.running_balance:.2f}" if txn.running_balance else "",
                    sanitize_for_csv(txn.source_file),
                    "Yes" if txn.is_duplicate else "",
                    "Yes" if txn.is_uncategorized else "",
                ])

        logger.info(f"Exported {len(transactions)} transactions to {output_path}")
        return output_path

    def _export_account_sheets(
        self,
        base_dir: Path,
        transactions: list[Transaction],
    ) -> list[Path]:
        """Export per-account transaction sheets.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.

        Returns:
            List of paths to created files.
        """
        # Group by account
        by_account: dict[str, list[Transaction]] = {}
        for txn in transactions:
            account_key = txn.account_id  # Use ID for filename
            if account_key not in by_account:
                by_account[account_key] = []
            by_account[account_key].append(txn)

        created_files: list[Path] = []

        for account_id, account_txns in sorted(by_account.items()):
            # Sanitize account ID for filename (handles all platform-unsafe characters)
            safe_id = _sanitize_filename(account_id)
            output_path = base_dir / f"account_{safe_id}.csv"

            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Date", "Description", "Category", "Amount", "Balance"])

                sorted_txns = sorted(account_txns, key=lambda t: (t.date, t.description))
                for txn in sorted_txns:
                    writer.writerow([
                        date_to_iso(txn.date),
                        sanitize_for_csv(txn.description),
                        sanitize_for_csv(self._get_category_name(txn.category) or ""),
                        f"{txn.amount:.2f}",
                        f"{txn.running_balance:.2f}" if txn.running_balance else "",
                    ])

            created_files.append(output_path)
            logger.debug(f"Exported account {account_id} to {output_path}")

        return created_files

    def _export_category_analysis(
        self,
        base_dir: Path,
        transactions: list[Transaction],
    ) -> Path:
        """Export Category Analysis to CSV.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "category_analysis.csv"

        # Calculate by category and month
        by_category: dict[str, dict[str, float]] = {}
        for txn in transactions:
            cat_name = self._get_category_name(txn.category) or "Uncategorized"
            month_key = txn.date.strftime("%Y-%m")

            if cat_name not in by_category:
                by_category[cat_name] = {}
            by_category[cat_name][month_key] = (
                by_category[cat_name].get(month_key, 0) + float(txn.amount)
            )

        # Get all months
        all_months = sorted(set(
            month for cat_months in by_category.values() for month in cat_months
        ))

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(["Category"] + all_months + ["Total"])

            # Data
            for cat_name, months in sorted(by_category.items()):
                row = [sanitize_for_csv(cat_name)]
                total = 0.0
                for month in all_months:
                    amount = months.get(month, 0)
                    total += amount
                    row.append(f"{amount:.2f}" if amount != 0 else "")
                row.append(f"{total:.2f}")
                writer.writerow(row)

        logger.info(f"Exported category analysis to {output_path}")
        return output_path

    def _export_anomalies(
        self,
        base_dir: Path,
        transactions: list[Transaction],
        date_gaps: list[dict[str, object]],
    ) -> Path:
        """Export Anomalies to CSV.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.
            date_gaps: Date gap anomalies.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "anomalies.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Transaction anomalies
            writer.writerow(["Transaction Anomalies"])
            writer.writerow(["Date", "Account", "Description", "Amount", "Reason"])

            anomaly_txns = [t for t in transactions if t.is_anomaly]
            for txn in sorted(anomaly_txns, key=lambda t: t.date):
                writer.writerow([
                    date_to_iso(txn.date),
                    sanitize_for_csv(txn.account_name),
                    sanitize_for_csv(txn.description),
                    f"{txn.amount:.2f}",
                    sanitize_for_csv("; ".join(txn.anomaly_reasons)),
                ])

            writer.writerow([])

            # Date gap anomalies
            writer.writerow(["Date Gap Anomalies"])
            writer.writerow(["Account", "Start Date", "End Date", "Gap (Days)", "Severity"])

            for gap in date_gaps:
                start = gap.get("start_date")
                end = gap.get("end_date")
                writer.writerow([
                    str(gap.get("account_id", "")),
                    date_to_iso(start) if start else "",
                    date_to_iso(end) if end else "",
                    str(gap.get("gap_days", "")),
                    str(gap.get("severity", "")),
                ])

        logger.info(f"Exported anomalies to {output_path}")
        return output_path

    def _get_category_type(self, category_id: Optional[str]) -> Optional[str]:
        """Get category type."""
        if not category_id:
            return None
        category = self.config.categories.get(category_id)
        return category.category_type.value if category and category.category_type else None

    def _get_category_name(self, category_id: Optional[str]) -> Optional[str]:
        """Get category display name."""
        if not category_id:
            return None
        category = self.config.categories.get(category_id)
        return category.name if category else category_id
