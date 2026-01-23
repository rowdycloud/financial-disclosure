# Task: Add Opening Balance Row to Per-Account Sheets

## Objective
Add a first row showing opening balance before transaction data in per-account Excel sheets.

## Location
[excel_writer.py](src/financial_consolidator/output/excel_writer.py) in per-account sheet generation

## Design
First data row (after header):
| Date | Description | Amount | Category | Balance |
|------|-------------|--------|----------|---------|
| 2024-01-01 | [Opening Balance] | - | - | $5,234.56 |
| 2024-01-02 | Deposit | $500.00 | Income | $5,734.56 |
| 2024-01-03 | Grocery Store | -$75.00 | Groceries | $5,659.56 |

## Implementation

### Find Per-Account Sheet Generation
Look in `excel_writer.py` for where per-account sheets are created. This might be in a method like `_write_account_sheet()` or similar.

### Add Opening Balance Row Before Transactions
After creating the header row, before appending transactions:

```python
from openpyxl.styles import Font, PatternFill

# Add opening balance row if available
account = config.accounts.get(account_id)
if account and account.opening_balance is not None:
    # Create opening balance row
    # Adjust columns based on your sheet structure
    opening_row = [
        account.opening_balance_date.isoformat() if account.opening_balance_date else "",
        "[Opening Balance]",
        "",  # No transaction amount
        "",  # No category
        float(account.opening_balance),  # Balance column
    ]
    sheet.append(opening_row)

    # Style the opening balance row differently
    row_num = sheet.max_row
    for cell in sheet[row_num]:
        cell.font = Font(italic=True, color="666666")
        cell.fill = PatternFill("solid", fgColor="F5F5F5")

    # Format balance as currency
    balance_cell = sheet.cell(row=row_num, column=5)  # Adjust column index
    balance_cell.number_format = '$#,##0.00'
```

### Alternative: If Sheet Structure Differs
Check the actual column order in the existing per-account sheets. Common structures:

**Structure A (Date first):**
```python
opening_row = [
    account.opening_balance_date,  # Date
    "[Opening Balance]",           # Description
    "",                            # Amount
    float(account.opening_balance) # Balance
]
```

**Structure B (With more columns):**
```python
opening_row = [
    account.opening_balance_date,  # Date
    "[Opening Balance]",           # Description
    "",                            # Amount
    "",                            # Category
    "",                            # Account
    float(account.opening_balance) # Running Balance
]
```

### Ensure Running Balance Calculation Starts Correctly
If the sheet includes running balance calculations, verify that:
1. Opening balance row shows the opening balance in the Balance column
2. First transaction row's balance = opening_balance + first_amount
3. Subsequent rows continue the running balance correctly

## Key Files
- [excel_writer.py](src/financial_consolidator/output/excel_writer.py) - Modify per-account sheet generation
- [balance_calculator.py](src/financial_consolidator/processing/balance_calculator.py) - Reference for balance logic

## Styling Guidelines
- Use italic font to distinguish from regular transactions
- Use light gray background (F5F5F5)
- Use slightly muted text color (666666)
- Description should be "[Opening Balance]" (with brackets)
- Amount column should be empty (no debit/credit for opening)
- Balance column shows the opening balance amount

## Verification
1. Set opening balance for an account: `--set-balance chase_checking --balance 5234.56 --balance-date 2024-01-01`
2. Run export to generate Excel
3. Open the per-account sheet (e.g., "Chase Checking" sheet)
4. Verify first data row (row 2) shows:
   - Date: 2024-01-01
   - Description: [Opening Balance]
   - Amount: (empty)
   - Balance: $5,234.56
5. Verify styling is italic with gray background
6. Verify transaction rows follow with correct running balances
7. Run existing tests: all 37 tests pass
