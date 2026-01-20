"""Excel workbook writer for financial consolidation output."""

from pathlib import Path

from financial_consolidator.config import Config
from financial_consolidator.models.report import PLSummary
from financial_consolidator.models.transaction import Transaction
from financial_consolidator.utils.logging_config import get_logger
from financial_consolidator.utils.sanitize import sanitize_for_csv

logger = get_logger(__name__)

# Import openpyxl
try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.utils.dataframe import dataframe_to_rows

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    Workbook = None  # type: ignore


class ExcelWriter:
    """Writes financial data to a multi-sheet Excel workbook.

    Generates sheets:
    - P&L Summary
    - All Transactions (Master List)
    - Per-account transaction history
    - Category Analysis
    - Anomalies
    """

    def __init__(self, config: Config):
        """Initialize Excel writer.

        Args:
            config: Application configuration.
        """
        if not OPENPYXL_AVAILABLE:
            raise ImportError("openpyxl library not installed")

        self.config = config
        self.output_config = config.output

        # Style definitions
        self.header_font = Font(bold=True, color="FFFFFF")
        self.header_fill = PatternFill(
            start_color="4472C4", end_color="4472C4", fill_type="solid"
        )
        self.money_positive = Font(color="006600")  # Dark green
        self.money_negative = Font(color="CC0000")  # Dark red
        self.centered = Alignment(horizontal="center")
        self.right_aligned = Alignment(horizontal="right")
        self.thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )

    def write(
        self,
        output_path: Path,
        transactions: list[Transaction],
        date_gaps: list[dict[str, object]] | None,
        pl_summary: PLSummary,
    ) -> None:
        """Write all data to an Excel workbook.

        Args:
            output_path: Path for output file.
            transactions: List of processed transactions.
            date_gaps: Optional list of date gap anomalies.
            pl_summary: Pre-computed P&L summary data.
        """
        logger.info(f"Writing Excel workbook to {output_path}")

        wb = Workbook()
        # Remove default sheet
        if wb.active:
            wb.remove(wb.active)

        # Create sheets
        self._create_pl_summary(wb, pl_summary)
        self._create_master_list(wb, transactions)
        self._create_account_sheets(wb, transactions)
        self._create_category_analysis(wb, transactions)
        self._create_anomalies_sheet(wb, transactions, date_gaps or [])

        # Save workbook
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        logger.info(f"Excel workbook saved: {output_path}")

    def _create_pl_summary(
        self, wb: "Workbook", pl_summary: PLSummary
    ) -> None:
        """Create P&L Summary sheet.

        Args:
            wb: Workbook to add sheet to.
            pl_summary: Pre-computed P&L summary data.
        """
        ws = wb.create_sheet("P&L Summary")

        row = 1

        # Report metadata header
        ws.cell(row=row, column=1, value="REPORT SUMMARY")
        ws.cell(row=row, column=1).font = Font(bold=True, size=14)
        row += 1
        ws.cell(row=row, column=1, value="Period")
        ws.cell(row=row, column=2, value=pl_summary.period_display)
        row += 1
        ws.cell(row=row, column=1, value="Accounts")
        ws.cell(row=row, column=2, value=pl_summary.accounts_display)
        row += 2

        # Income section
        ws.cell(row=row, column=1, value="INCOME")
        ws.cell(row=row, column=1).font = Font(bold=True)
        row += 1

        for cat, amount in sorted(pl_summary.income_by_category.items()):
            ws.cell(row=row, column=1, value=sanitize_for_csv(cat))
            ws.cell(row=row, column=2, value=float(amount))
            ws.cell(row=row, column=2).number_format = self._money_format()
            row += 1

        ws.cell(row=row, column=1, value="Total Income")
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2, value=float(pl_summary.total_income))
        ws.cell(row=row, column=2).font = Font(bold=True)
        ws.cell(row=row, column=2).number_format = self._money_format()
        row += 2

        # Expense section
        ws.cell(row=row, column=1, value="EXPENSES")
        ws.cell(row=row, column=1).font = Font(bold=True)
        row += 1

        for cat, amount in sorted(pl_summary.expense_by_category.items()):
            ws.cell(row=row, column=1, value=sanitize_for_csv(cat))
            ws.cell(row=row, column=2, value=float(amount))
            ws.cell(row=row, column=2).number_format = self._money_format()
            row += 1

        ws.cell(row=row, column=1, value="Total Expenses")
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=2, value=float(pl_summary.total_expenses))
        ws.cell(row=row, column=2).font = Font(bold=True)
        ws.cell(row=row, column=2).number_format = self._money_format()
        row += 2

        # Net income
        ws.cell(row=row, column=1, value="NET INCOME")
        ws.cell(row=row, column=1).font = Font(bold=True, size=12)
        ws.cell(row=row, column=2, value=float(pl_summary.net_income))
        ws.cell(row=row, column=2).font = Font(bold=True, size=12)
        ws.cell(row=row, column=2).number_format = self._money_format()
        row += 3

        # Transfers memo section (excluded from P&L)
        ws.cell(row=row, column=1, value="TRANSFERS")
        ws.cell(row=row, column=1).font = Font(bold=True, italic=True)
        row += 1
        ws.cell(row=row, column=1, value="(Money moved between accounts - not counted as income or expense)")
        ws.cell(row=row, column=1).font = Font(italic=True, color="666666")
        row += 1

        for cat, amount in sorted(pl_summary.transfer_by_category.items()):
            ws.cell(row=row, column=1, value=sanitize_for_csv(cat))
            ws.cell(row=row, column=2, value=float(amount))
            ws.cell(row=row, column=2).number_format = self._money_format()
            row += 1

        ws.cell(row=row, column=1, value="Total Transfers")
        ws.cell(row=row, column=2, value=float(pl_summary.total_transfers))
        ws.cell(row=row, column=2).number_format = self._money_format()

        # Adjust column widths
        ws.column_dimensions["A"].width = 60
        ws.column_dimensions["B"].width = 15

    def _create_master_list(
        self, wb: "Workbook", transactions: list[Transaction]
    ) -> None:
        """Create Master List (All Transactions) sheet.

        Args:
            wb: Workbook to add sheet to.
            transactions: Transaction data.
        """
        ws = wb.create_sheet("All Transactions")

        # Headers with confidence scoring columns
        headers = [
            "Date", "Account", "Description", "Category", "Sub-category",
            "Amount", "Balance", "Source File", "Duplicate Flag", "Uncategorized Flag",
            "Confidence", "Matched Pattern", "Category Source", "Confidence Factors"
        ]

        # Write headers
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.alignment = self.centered

        # Sort transactions by date, then account
        sorted_txns = sorted(
            transactions, key=lambda t: (t.date, t.account_name, t.description)
        )

        # Conditional formatting colors for confidence
        low_conf_fill = PatternFill(start_color="FFCCCC", end_color="FFCCCC", fill_type="solid")  # Red
        med_conf_fill = PatternFill(start_color="FFFFCC", end_color="FFFFCC", fill_type="solid")  # Yellow
        high_conf_fill = PatternFill(start_color="CCFFCC", end_color="CCFFCC", fill_type="solid")  # Green

        # Write data
        for row, txn in enumerate(sorted_txns, 2):
            ws.cell(row=row, column=1, value=txn.date)
            ws.cell(row=row, column=2, value=sanitize_for_csv(txn.account_name))
            ws.cell(row=row, column=3, value=sanitize_for_csv(txn.description))
            ws.cell(row=row, column=4, value=sanitize_for_csv(self._get_category_name(txn.category)))
            ws.cell(row=row, column=5, value=sanitize_for_csv(self._get_category_name(txn.subcategory)))

            amount_cell = ws.cell(row=row, column=6, value=float(txn.amount))
            amount_cell.number_format = self._money_format()
            if txn.amount < 0:
                amount_cell.font = self.money_negative
            else:
                amount_cell.font = self.money_positive

            if txn.running_balance is not None:
                balance_cell = ws.cell(row=row, column=7, value=float(txn.running_balance))
                balance_cell.number_format = self._money_format()

            ws.cell(row=row, column=8, value=sanitize_for_csv(txn.source_file))
            ws.cell(row=row, column=9, value="Yes" if txn.is_duplicate else "")
            ws.cell(row=row, column=10, value="Yes" if txn.is_uncategorized else "")

            # Confidence scoring columns
            if not txn.is_uncategorized:
                conf_cell = ws.cell(row=row, column=11, value=txn.confidence_score)
                conf_cell.number_format = "0.00"

                # Apply conditional formatting based on confidence
                if txn.confidence_score < 0.6:
                    conf_cell.fill = low_conf_fill
                elif txn.confidence_score < 0.8:
                    conf_cell.fill = med_conf_fill
                else:
                    conf_cell.fill = high_conf_fill

            ws.cell(row=row, column=12, value=sanitize_for_csv(txn.matched_pattern or ""))
            ws.cell(row=row, column=13, value=sanitize_for_csv(txn.category_source))

            # Format confidence factors as semicolon-separated list
            factors_str = "; ".join(txn.confidence_factors) if txn.confidence_factors else ""
            ws.cell(row=row, column=14, value=sanitize_for_csv(factors_str))

        # Adjust column widths
        widths = [12, 25, 40, 20, 20, 12, 12, 25, 12, 15, 10, 20, 12, 40]
        for i, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = width

        # Freeze header row
        ws.freeze_panes = "A2"

    def _create_account_sheets(
        self, wb: "Workbook", transactions: list[Transaction]
    ) -> None:
        """Create per-account transaction sheets.

        Args:
            wb: Workbook to add sheets to.
            transactions: Transaction data.
        """
        # Group by account
        by_account: dict[str, list[Transaction]] = {}
        for txn in transactions:
            if txn.account_name not in by_account:
                by_account[txn.account_name] = []
            by_account[txn.account_name].append(txn)

        for account_name, account_txns in sorted(by_account.items()):
            # Sanitize and truncate sheet name (Excel limit is 31 chars)
            # Excel doesn't allow: * ? / \ [ ] in sheet names
            sheet_name = account_name
            for char in ['*', '?', '/', '\\', '[', ']', ':']:
                sheet_name = sheet_name.replace(char, '')
            sheet_name = sheet_name[:31]
            ws = wb.create_sheet(sheet_name)

            headers = ["Date", "Description", "Category", "Amount", "Balance"]

            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = self.header_font
                cell.fill = self.header_fill

            # Sort by date
            sorted_txns = sorted(account_txns, key=lambda t: (t.date, t.description))

            for row, txn in enumerate(sorted_txns, 2):
                ws.cell(row=row, column=1, value=txn.date)
                ws.cell(row=row, column=2, value=sanitize_for_csv(txn.description))
                ws.cell(row=row, column=3, value=sanitize_for_csv(self._get_category_name(txn.category)))

                amount_cell = ws.cell(row=row, column=4, value=float(txn.amount))
                amount_cell.number_format = self._money_format()
                if txn.amount < 0:
                    amount_cell.font = self.money_negative
                else:
                    amount_cell.font = self.money_positive

                if txn.running_balance is not None:
                    balance_cell = ws.cell(row=row, column=5, value=float(txn.running_balance))
                    balance_cell.number_format = self._money_format()

            # Adjust widths
            ws.column_dimensions["A"].width = 12
            ws.column_dimensions["B"].width = 40
            ws.column_dimensions["C"].width = 20
            ws.column_dimensions["D"].width = 12
            ws.column_dimensions["E"].width = 12

            ws.freeze_panes = "A2"

    def _create_category_analysis(
        self, wb: "Workbook", transactions: list[Transaction]
    ) -> None:
        """Create Category Analysis sheet.

        Args:
            wb: Workbook to add sheet to.
            transactions: Transaction data.
        """
        ws = wb.create_sheet("Category Analysis")

        # Calculate spending by category
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
        all_months = sorted({
            month for cat_months in by_category.values() for month in cat_months
        })

        if not all_months:
            ws.cell(row=1, column=1, value="No transaction data")
            return

        # Write headers
        ws.cell(row=1, column=1, value="Category")
        ws.cell(row=1, column=1).font = self.header_font
        ws.cell(row=1, column=1).fill = self.header_fill

        for col, month in enumerate(all_months, 2):
            cell = ws.cell(row=1, column=col, value=month)
            cell.font = self.header_font
            cell.fill = self.header_fill

        # Total column
        total_col = len(all_months) + 2
        ws.cell(row=1, column=total_col, value="Total")
        ws.cell(row=1, column=total_col).font = self.header_font
        ws.cell(row=1, column=total_col).fill = self.header_fill

        # Write data
        for row, (cat_name, months) in enumerate(sorted(by_category.items()), 2):
            ws.cell(row=row, column=1, value=sanitize_for_csv(cat_name))

            cat_total = 0.0
            for col, month in enumerate(all_months, 2):
                amount = months.get(month, 0)
                cat_total += amount
                if amount != 0:
                    cell = ws.cell(row=row, column=col, value=amount)
                    cell.number_format = self._money_format()

            # Total for category
            cell = ws.cell(row=row, column=total_col, value=cat_total)
            cell.number_format = self._money_format()
            cell.font = Font(bold=True)

        # Adjust widths
        ws.column_dimensions["A"].width = 25
        for i in range(len(all_months) + 1):
            ws.column_dimensions[get_column_letter(i + 2)].width = 12  # +2 because starting at column B

        ws.freeze_panes = "B2"

    def _create_anomalies_sheet(
        self,
        wb: "Workbook",
        transactions: list[Transaction],
        date_gaps: list[dict[str, object]],
    ) -> None:
        """Create Anomalies sheet.

        Args:
            wb: Workbook to add sheet to.
            transactions: Transaction data.
            date_gaps: Date gap anomalies.
        """
        ws = wb.create_sheet("Anomalies")

        # Transaction anomalies
        ws.cell(row=1, column=1, value="Transaction Anomalies")
        ws.cell(row=1, column=1).font = Font(bold=True, size=12)

        headers = ["Date", "Account", "Description", "Amount", "Reason"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill

        row = 3
        anomaly_txns = [t for t in transactions if t.is_anomaly]
        for txn in sorted(anomaly_txns, key=lambda t: t.date):
            ws.cell(row=row, column=1, value=txn.date)
            ws.cell(row=row, column=2, value=sanitize_for_csv(txn.account_name))
            ws.cell(row=row, column=3, value=sanitize_for_csv(txn.description))

            amount_cell = ws.cell(row=row, column=4, value=float(txn.amount))
            amount_cell.number_format = self._money_format()

            ws.cell(row=row, column=5, value=sanitize_for_csv("; ".join(txn.anomaly_reasons)))
            row += 1

        # Date gap anomalies
        row += 2
        ws.cell(row=row, column=1, value="Date Gap Anomalies")
        ws.cell(row=row, column=1).font = Font(bold=True, size=12)
        row += 1

        gap_headers = ["Account", "Start Date", "End Date", "Gap (Days)", "Severity"]
        for col, header in enumerate(gap_headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = self.header_font
            cell.fill = self.header_fill
        row += 1

        for gap in date_gaps:
            ws.cell(row=row, column=1, value=str(gap.get("account_id", "")))
            ws.cell(row=row, column=2, value=gap.get("start_date"))
            ws.cell(row=row, column=3, value=gap.get("end_date"))
            ws.cell(row=row, column=4, value=gap.get("gap_days"))
            ws.cell(row=row, column=5, value=str(gap.get("severity", "")))
            row += 1

        # Adjust widths
        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 40
        ws.column_dimensions["D"].width = 12
        ws.column_dimensions["E"].width = 40

    def _get_category_type(self, category_id: str | None) -> str | None:
        """Get the type (income/expense/transfer) for a category.

        Args:
            category_id: Category ID.

        Returns:
            Category type or None.
        """
        if not category_id:
            return None

        category = self.config.categories.get(category_id)
        if category:
            return category.category_type.value if category.category_type else None

        return None

    def _get_category_name(self, category_id: str | None) -> str | None:
        """Get display name for a category.

        Args:
            category_id: Category ID.

        Returns:
            Category name or None.
        """
        if not category_id:
            return None

        category = self.config.categories.get(category_id)
        if category:
            return category.name

        return category_id

    def _money_format(self) -> str:
        """Get number format for money values.

        Returns:
            Excel number format string.
        """
        symbol = self.output_config.currency_symbol
        return f'{symbol}#,##0.00_);[Red]({symbol}#,##0.00)'
