"""CSV exporter for Google Sheets compatibility."""

import csv
import re
from datetime import date
from pathlib import Path

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
    - deposits.csv
    - transfers.csv
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
        date_gaps: list[dict[str, object]] | None,
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
            self._export_deposits(base_dir, transactions),
            self._export_transfers(base_dir, transactions),
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
        """Export P&L Summary to CSV with year-by-year breakdown.

        Args:
            base_dir: Output directory.
            pl_summary: Pre-computed P&L summary data.

        Returns:
            Path to created file.
        """
        from decimal import Decimal

        output_path = base_dir / "pl_summary.csv"
        years = pl_summary.years

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Report metadata header
            writer.writerow(["REPORT SUMMARY"])
            writer.writerow(["Period", pl_summary.period_display])
            writer.writerow(["Accounts", pl_summary.accounts_display])
            writer.writerow([])

            # Income section with year columns
            writer.writerow(["INCOME"] + [str(y) for y in years] + ["Total"])

            for cat in pl_summary.all_income_categories:
                row = [sanitize_for_csv(cat)]
                total = Decimal("0")
                for year in years:
                    amount = pl_summary.income_by_year.get(year, {}).get(cat, Decimal("0"))
                    row.append(f"{float(amount):.2f}")
                    total += amount
                row.append(f"{float(total):.2f}")
                writer.writerow(row)

            # Total Income row
            row = ["Total Income"]
            for year in years:
                row.append(f"{float(pl_summary.income_for_year(year)):.2f}")
            row.append(f"{float(pl_summary.total_income):.2f}")
            writer.writerow(row)
            writer.writerow([])

            # Expense section with year columns
            writer.writerow(["EXPENSES"] + [str(y) for y in years] + ["Total"])

            for cat in pl_summary.all_expense_categories:
                row = [sanitize_for_csv(cat)]
                total = Decimal("0")
                for year in years:
                    amount = pl_summary.expense_by_year.get(year, {}).get(cat, Decimal("0"))
                    row.append(f"{float(amount):.2f}")
                    total += amount
                row.append(f"{float(total):.2f}")
                writer.writerow(row)

            # Total Expenses row
            row = ["Total Expenses"]
            for year in years:
                row.append(f"{float(pl_summary.expenses_for_year(year)):.2f}")
            row.append(f"{float(pl_summary.total_expenses):.2f}")
            writer.writerow(row)
            writer.writerow([])

            # Net income row with year columns
            row = ["NET INCOME"]
            for year in years:
                row.append(f"{float(pl_summary.net_income_for_year(year)):.2f}")
            row.append(f"{float(pl_summary.net_income):.2f}")
            writer.writerow(row)
            writer.writerow([])

            # Transfers section with year columns
            writer.writerow(["TRANSFERS"] + [str(y) for y in years] + ["Total"])
            transfer_note = "(Money moved between accounts - not counted as income or expense)"
            writer.writerow([transfer_note] + [""] * (len(years) + 1))

            for cat in pl_summary.all_transfer_categories:
                row = [sanitize_for_csv(cat)]
                total = Decimal("0")
                for year in years:
                    amount = pl_summary.transfer_by_year.get(year, {}).get(cat, Decimal("0"))
                    row.append(f"{float(amount):.2f}")
                    total += amount
                row.append(f"{float(total):.2f}")
                writer.writerow(row)

            # Total Transfers row
            row = ["Total Transfers"]
            for year in years:
                row.append(f"{float(pl_summary.transfers_for_year(year)):.2f}")
            row.append(f"{float(pl_summary.total_transfers):.2f}")
            writer.writerow(row)

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

            # Headers with confidence scoring columns and fingerprint
            writer.writerow([
                "Date", "Account", "Description", "Category", "Sub-category",
                "Amount", "Balance", "Source File", "Duplicate Flag", "Uncategorized Flag",
                "Confidence", "Matched Pattern", "Category Source", "Confidence Factors",
                "Fingerprint"
            ])

            # Sort and write data
            sorted_txns = sorted(
                transactions, key=lambda t: (t.date, t.account_name, t.description)
            )

            for txn in sorted_txns:
                # Format confidence factors as semicolon-separated list
                factors_str = "; ".join(txn.confidence_factors) if txn.confidence_factors else ""

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
                    f"{txn.confidence_score:.2f}" if not txn.is_uncategorized else "",
                    sanitize_for_csv(txn.matched_pattern or ""),
                    sanitize_for_csv(txn.category_source),
                    sanitize_for_csv(factors_str),
                    txn.fingerprint,
                ])

        logger.info(f"Exported {len(transactions)} transactions to {output_path}")
        return output_path

    def _export_deposits(
        self,
        base_dir: Path,
        transactions: list[Transaction],
    ) -> Path:
        """Export deposits (positive amount transactions) to CSV.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "deposits.csv"

        # Filter to deposits only (amount > 0, excludes zero and negative)
        deposits = [txn for txn in transactions if txn.amount > 0]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Headers
            writer.writerow([
                "Date", "Account", "Description", "Category", "Sub-category",
                "Amount", "Balance", "Source File"
            ])

            # Sort by date, then account, then description
            sorted_deposits = sorted(
                deposits, key=lambda t: (t.date, t.account_name, t.description)
            )

            for txn in sorted_deposits:
                writer.writerow([
                    date_to_iso(txn.date),
                    sanitize_for_csv(txn.account_name),
                    sanitize_for_csv(txn.description),
                    sanitize_for_csv(self._get_category_name(txn.category) or ""),
                    sanitize_for_csv(self._get_category_name(txn.subcategory) or ""),
                    f"{txn.amount:.2f}",
                    f"{txn.running_balance:.2f}" if txn.running_balance else "",
                    sanitize_for_csv(txn.source_file),
                ])

        logger.info(f"Exported {len(deposits)} deposits to {output_path}")
        return output_path

    def _export_transfers(
        self,
        base_dir: Path,
        transactions: list[Transaction],
    ) -> Path:
        """Export transfers (transactions with category type 'transfer') to CSV.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "transfers.csv"

        # Filter to transfers only (category type == "transfer")
        transfers = [
            txn for txn in transactions
            if self._get_category_type(txn.category) == "transfer"
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Headers
            writer.writerow([
                "Date", "Account", "Description", "Category", "Sub-category",
                "Amount", "Balance", "Source File"
            ])

            # Sort by date, then account, then description
            sorted_transfers = sorted(
                transfers, key=lambda t: (t.date, t.account_name, t.description)
            )

            for txn in sorted_transfers:
                writer.writerow([
                    date_to_iso(txn.date),
                    sanitize_for_csv(txn.account_name),
                    sanitize_for_csv(txn.description),
                    sanitize_for_csv(self._get_category_name(txn.category) or ""),
                    sanitize_for_csv(self._get_category_name(txn.subcategory) or ""),
                    f"{txn.amount:.2f}",
                    f"{txn.running_balance:.2f}" if txn.running_balance else "",
                    sanitize_for_csv(txn.source_file),
                ])

        logger.info(f"Exported {len(transfers)} transfers to {output_path}")
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

        # Calculate by category and month (aligned with P&L logic)
        by_category: dict[str, dict[str, float]] = {}
        for txn in transactions:
            # Skip uncategorized transactions (match P&L behavior)
            if not txn.category:
                continue

            cat = self.config.categories.get(txn.category)
            if not cat:
                continue

            cat_name = cat.name
            cat_type = cat.category_type.value if cat.category_type else None
            month_key = txn.date.strftime("%Y-%m")

            # Use abs() for expenses (match P&L behavior)
            if cat_type == "expense":
                amount = abs(float(txn.amount))
            else:
                amount = float(txn.amount)

            if cat_name not in by_category:
                by_category[cat_name] = {}
            by_category[cat_name][month_key] = (
                by_category[cat_name].get(month_key, 0) + amount
            )

        # Get all months
        all_months = sorted({
            month for cat_months in by_category.values() for month in cat_months
        })

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
                    date_to_iso(start) if isinstance(start, date) else "",
                    date_to_iso(end) if isinstance(end, date) else "",
                    str(gap.get("gap_days", "")),
                    str(gap.get("severity", "")),
                ])

        logger.info(f"Exported anomalies to {output_path}")
        return output_path

    def _get_category_type(self, category_id: str | None) -> str | None:
        """Get category type."""
        if not category_id:
            return None
        category = self.config.categories.get(category_id)
        return category.category_type.value if category and category.category_type else None

    def _get_category_name(self, category_id: str | None) -> str | None:
        """Get category display name."""
        if not category_id:
            return None
        category = self.config.categories.get(category_id)
        return category.name if category else category_id

    def export_uncategorized_for_review(
        self,
        base_dir: Path,
        transactions: list[Transaction],
    ) -> Path:
        """Export uncategorized transactions grouped by merchant for review.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "uncategorized_for_review.csv"

        # Filter uncategorized transactions
        uncategorized = [t for t in transactions if t.is_uncategorized]

        # Group by description (merchant pattern)
        by_merchant: dict[str, list[Transaction]] = {}
        for txn in uncategorized:
            # Normalize description for grouping (strip numbers, etc.)
            key = self._normalize_merchant(txn.description)
            if key not in by_merchant:
                by_merchant[key] = []
            by_merchant[key].append(txn)

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Merchant Pattern", "Frequency", "Total Amount",
                    "Avg Amount", "Example Description"
                ])

                # Sort by frequency (most common first)
                sorted_merchants = sorted(
                    by_merchant.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )

                for pattern, txns in sorted_merchants:
                    total = sum(float(t.amount) for t in txns)
                    avg = total / len(txns) if txns else 0
                    example = txns[0].description if txns else ""

                    writer.writerow([
                        sanitize_for_csv(pattern),
                        len(txns),
                        f"{total:.2f}",
                        f"{avg:.2f}",
                        sanitize_for_csv(example),
                    ])

            logger.info(f"Exported {len(by_merchant)} uncategorized patterns to {output_path}")
        except OSError as e:
            logger.error(f"Failed to write uncategorized review file {output_path}: {e}")
            raise OSError(f"Failed to export uncategorized transactions: {e}") from e
        return output_path

    def _normalize_merchant(self, description: str) -> str:
        """Normalize merchant description for grouping.

        Removes numbers, excess whitespace, and common suffixes.
        """
        # Remove trailing numbers (store IDs, reference numbers)
        normalized = re.sub(r'\s*#?\d+$', '', description)
        # Remove common suffixes
        normalized = re.sub(r'\s*(INC|LLC|CORP|CO)\.?$', '', normalized, flags=re.IGNORECASE)
        # Collapse whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized or description

    def export_categorization_summary(
        self,
        base_dir: Path,
        transactions: list[Transaction],
        ai_stats: dict[str, object] | None = None,
    ) -> Path:
        """Export categorization summary statistics.

        Args:
            base_dir: Output directory.
            transactions: Transaction data.
            ai_stats: Optional AI usage statistics.

        Returns:
            Path to created file.
        """
        output_path = base_dir / "categorization_summary.csv"

        total = len(transactions)
        rule_based = sum(1 for t in transactions if t.category_source == "rule")
        manual = sum(1 for t in transactions if t.category_source == "manual")
        ai_categorized = sum(1 for t in transactions if t.category_source == "ai")
        ai_corrected = sum(1 for t in transactions if t.category_source == "ai_correction")
        uncategorized = sum(1 for t in transactions if t.is_uncategorized)
        categorized = total - uncategorized

        # Confidence distribution
        high_conf = sum(1 for t in transactions if t.confidence_score >= 0.8)
        med_conf = sum(1 for t in transactions if 0.6 <= t.confidence_score < 0.8)
        low_conf = sum(1 for t in transactions if 0.0 < t.confidence_score < 0.6)

        try:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                writer.writerow(["CATEGORIZATION SUMMARY", ""])
                writer.writerow([])

                writer.writerow(["Transaction Counts", ""])
                writer.writerow(["Total Transactions", total])
                writer.writerow(["Categorized", categorized])
                writer.writerow(["Uncategorized", uncategorized])
                writer.writerow([
                    "Categorization Rate",
                    f"{(categorized / total * 100):.1f}%" if total > 0 else "N/A"
                ])
                writer.writerow([])

                writer.writerow(["Categorization Sources", ""])
                writer.writerow(["Rule-Based", rule_based])
                writer.writerow(["Manual Override", manual])
                writer.writerow(["AI Categorized", ai_categorized])
                writer.writerow(["AI Corrected", ai_corrected])
                writer.writerow([])

                writer.writerow(["Confidence Distribution", ""])
                writer.writerow(["High (>=80%)", high_conf])
                writer.writerow(["Medium (60-80%)", med_conf])
                writer.writerow(["Low (<60%)", low_conf])
                writer.writerow([])

                if ai_stats:
                    writer.writerow(["AI Usage Statistics", ""])
                    writer.writerow(["Total API Requests", ai_stats.get("total_requests", 0)])
                    writer.writerow(["Total Tokens Used", ai_stats.get("total_tokens", 0)])
                    writer.writerow(["Total AI Cost", f"${ai_stats.get('total_cost', 0):.4f}"])

            logger.info(f"Exported categorization summary to {output_path}")
        except OSError as e:
            logger.error(f"Failed to write categorization summary file {output_path}: {e}")
            raise OSError(f"Failed to export categorization summary: {e}") from e
        return output_path
