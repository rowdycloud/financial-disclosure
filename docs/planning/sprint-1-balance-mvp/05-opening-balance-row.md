# Task: Add Opening Balance Row to Per-Account Sheets

> **Status:** 🔲 Pending
> **Prerequisite:** Task 04 complete - Account Summary sheet implemented

## Objective

Add a first row showing opening balance before transaction data in per-account Excel sheets.

## Location

[excel_writer.py](src/financial_consolidator/output/excel_writer.py) in `_create_account_sheets()` method (lines 692-750)

## Current Sheet Structure

The per-account sheets have 5 columns in this order:
| Date | Description | Category | Amount | Balance |
|------|-------------|----------|--------|---------|
| 2024-01-02 | Deposit | Income | $500.00 | $5,734.56 |
| 2024-01-03 | Grocery Store | Groceries | -$75.00 | $5,659.56 |

## Design

Add opening balance as first data row (after header):
| Date | Description | Category | Amount | Balance |
|------|-------------|----------|--------|---------|
| 2024-01-01 | [Opening Balance] | - | - | $5,234.56 |
| 2024-01-02 | Deposit | Income | $500.00 | $5,734.56 |
| 2024-01-03 | Grocery Store | Groceries | -$75.00 | $5,659.56 |

## Implementation

### Step 1: Pass Config to _create_account_sheets()

The method currently doesn't have access to config. Modify the method signature:

```python
def _create_account_sheets(
    self,
    workbook: Workbook,
    transactions: list[Transaction],
    config: Config,  # Add this parameter
) -> None:
```

Update the call site in `write_workbook()` to pass config.

### Step 2: Build Account Lookup by Name

The method groups transactions by `txn.account_name`, not account_id. Create a lookup:

```python
# Build lookup: account_name -> Account object
account_by_name: dict[str, Account] = {}
for account in config.accounts.values():
    account_by_name[account.name] = account
```

### Step 3: Add Opening Balance Row

After creating headers and before adding transactions, insert opening balance row:

```python
from openpyxl.styles import Font, PatternFill

# After: sheet.append(headers)
# Before: for txn in sorted_txns:

# Add opening balance row if available
account = account_by_name.get(account_name)
if account and account.opening_balance is not None:
    opening_row = [
        account.opening_balance_date.isoformat() if account.opening_balance_date else "",
        "[Opening Balance]",
        "",  # No category
        "",  # No amount
        float(account.opening_balance),
    ]
    sheet.append(opening_row)

    # Style the opening balance row
    row_num = sheet.max_row
    for cell in sheet[row_num]:
        cell.font = Font(italic=True, color="666666")
        cell.fill = PatternFill("solid", fgColor="F5F5F5")

    # Format balance cell as currency
    sheet.cell(row=row_num, column=5).number_format = '$#,##0.00'
```

### Step 4: Verify Running Balance Alignment

The existing running balance calculation uses `balance_calculator.py`. Verify that:
1. Opening balance row shows the opening balance in column E
2. First transaction row's balance = opening_balance + first_amount
3. The balance column already comes from `txn.running_balance` (set by balance_calculator)

If running_balance is already computed with opening_balance, no changes needed to balance logic.

## Key Files

- [excel_writer.py:692-750](src/financial_consolidator/output/excel_writer.py) - `_create_account_sheets()` method
- [balance_calculator.py](src/financial_consolidator/processing/balance_calculator.py) - Already uses opening_balance in calculations

## Styling Guidelines

- Italic font with muted gray color (666666)
- Light gray background (F5F5F5)
- Description: "[Opening Balance]" (with brackets)
- Category and Amount columns: empty
- Balance column: opening balance amount with currency format

## Verification

1. Set opening balance: `--set-balance chase_checking --balance 5234.56 --balance-date 2024-01-01`
2. Run export to generate Excel
3. Open per-account sheet (e.g., "Chase Checking" tab)
4. Verify first data row (row 2) shows:
   - Date: 2024-01-01
   - Description: [Opening Balance]
   - Category: (empty)
   - Amount: (empty)
   - Balance: $5,234.56
5. Verify styling: italic text, gray background
6. Verify next row (first transaction) has correct running balance
7. Run existing tests: all 52 tests pass
