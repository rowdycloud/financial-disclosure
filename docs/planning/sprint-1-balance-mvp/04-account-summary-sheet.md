# Task: Add Account Summary Sheet to Excel Output

## Objective
Add a new "Account Summary" sheet showing balance overview per account.

## Location
[excel_writer.py](src/financial_consolidator/output/excel_writer.py)

## Sheet Design
| Account | Opening Balance | Total Credits | Total Debits | Closing Balance |
|---------|-----------------|---------------|--------------|-----------------|
| Chase Checking | $5,234.56 | $12,500.00 | -$8,750.00 | $8,984.56 |
| Chase Freedom | $0.00 | $2,500.00 | -$3,200.00 | -$700.00 |

## Implementation

### Add New Method to ExcelWriter Class
Find the `ExcelWriter` class and add a new method:

```python
def _write_account_summary_sheet(
    self,
    workbook: Workbook,
    transactions: list[Transaction],
    config: Config,
) -> None:
    """Write Account Summary sheet showing balance overview."""
    from collections import defaultdict
    from decimal import Decimal
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    sheet = workbook.create_sheet("Account Summary")

    # Headers with styling
    headers = ["Account", "Opening Balance", "Total Credits", "Total Debits", "Closing Balance"]
    sheet.append(headers)

    # Style header row
    header_font = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="E0E0E0")
    for col, cell in enumerate(sheet[1], 1):
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Group transactions by account
    by_account: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        by_account[txn.account_id].append(txn)

    # Calculate per account (sorted by account display_order, then name)
    sorted_accounts = sorted(
        config.accounts.items(),
        key=lambda x: (x[1].display_order, x[1].name)
    )

    for account_id, account in sorted_accounts:
        txns = by_account.get(account_id, [])
        opening = account.opening_balance or Decimal("0")
        credits = sum(t.amount for t in txns if t.amount > 0)
        debits = sum(t.amount for t in txns if t.amount < 0)
        closing = opening + credits + debits

        sheet.append([
            account.name,
            float(opening),
            float(credits),
            float(debits),
            float(closing),
        ])

    # Format currency columns (B through E)
    for row in sheet.iter_rows(min_row=2, min_col=2, max_col=5):
        for cell in row:
            cell.number_format = '$#,##0.00'
            cell.alignment = Alignment(horizontal="right")

    # Set column widths
    sheet.column_dimensions['A'].width = 25  # Account name
    for col in ['B', 'C', 'D', 'E']:
        sheet.column_dimensions[col].width = 18

    # Add totals row
    last_row = sheet.max_row + 1
    sheet.cell(row=last_row, column=1, value="TOTAL").font = Font(bold=True)

    for col in range(2, 6):
        # Sum formula for each column
        col_letter = get_column_letter(col)
        formula = f"=SUM({col_letter}2:{col_letter}{last_row-1})"
        cell = sheet.cell(row=last_row, column=col, value=formula)
        cell.number_format = '$#,##0.00'
        cell.font = Font(bold=True)
```

### Call the Method in write_workbook()
Find `write_workbook()` method and add call after existing sheets:

```python
# Add Account Summary sheet
self._write_account_summary_sheet(workbook, transactions, config)
```

### Update Method Signature if Needed
If `write_workbook()` doesn't have access to `config`, add it as a parameter.

## Key Files
- [excel_writer.py](src/financial_consolidator/output/excel_writer.py) - Add new sheet method
- [config.py](src/financial_consolidator/config.py) - Config class with accounts

## Dependencies
Ensure openpyxl imports are available:
```python
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
```

## Verification
1. Run with multiple accounts that have transactions
2. Open generated Excel file
3. Verify "Account Summary" sheet exists (check sheet tabs)
4. Verify all accounts are listed
5. Verify calculations are correct:
   - Opening Balance matches accounts.yaml
   - Credits = sum of positive amounts
   - Debits = sum of negative amounts
   - Closing = Opening + Credits + Debits
6. Verify currency formatting ($X,XXX.XX)
7. Verify totals row at bottom
8. Run existing tests: all 37 tests pass
