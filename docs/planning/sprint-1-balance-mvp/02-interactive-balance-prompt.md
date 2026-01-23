# Task: Add Interactive Balance Prompt (Stage A)

## Objective
During interactive account creation, prompt user for opening balance.

## Location
[cli.py](src/financial_consolidator/cli.py) in `prompt_for_account()` lines 327-411

## Implementation

### Add Balance Prompt After Account Type Selection
After line ~395 (account type selection complete), before creating Account:

```python
# Prompt for opening balance
console.print("\n[bold]Opening Balance[/bold]")
console.print("[dim]Enter the balance as of the first transaction date.[/dim]")
console.print("[dim]Leave blank to auto-detect from transaction data, or enter 0 to start fresh.[/dim]")
balance_input = console.input("Opening balance: $").strip()

opening_balance: Decimal | None = None
opening_balance_date: date | None = None

if balance_input:
    from decimal import InvalidOperation
    try:
        opening_balance = Decimal(balance_input)
        # Also prompt for date
        date_input = console.input("Balance date (YYYY-MM-DD, blank for today): ").strip()
        if date_input:
            try:
                opening_balance_date = date.fromisoformat(date_input)
            except ValueError:
                console.print("[yellow]Invalid date format, using today[/yellow]")
                opening_balance_date = date.today()
        else:
            opening_balance_date = date.today()
    except InvalidOperation:
        console.print("[yellow]Invalid input, will auto-detect later[/yellow]")
        opening_balance = None
        opening_balance_date = None
```

### Pass to Account Constructor
Modify the Account() creation to include the new fields:

```python
account = Account(
    id=account_id,
    name=name,
    account_type=account_type,
    institution=institution,
    opening_balance=opening_balance,
    opening_balance_date=opening_balance_date,
)
```

## Key Behavior
- User enters value → saved immediately to account
- User enters blank → opening_balance = None (inference signal for Stage B)
- User enters 0 → opening_balance = Decimal("0") (explicit zero, no inference)

## Important Note
File parsing hasn't happened yet at this stage. The interactive prompts occur in Phase 1 of cli.py (lines 1108-1124), while file parsing happens in Phase 2 (lines 1126-1180). This is why we cannot infer from transaction data here - that happens in Stage B (task 03).

## Key Files
- [cli.py](src/financial_consolidator/cli.py) - Modify `prompt_for_account()`

## Verification
1. Run with unmapped file: `PYTHONPATH=src python -c "from financial_consolidator.cli import main; main()" -i ./test_data`
2. See balance prompt appear after account type selection
3. Enter a value (e.g., "5234.56") → confirm opening_balance saved to accounts.yaml
4. Enter blank → confirm opening_balance field is NOT in accounts.yaml (None)
5. Enter "0" → confirm opening_balance: '0' appears in accounts.yaml
6. Run existing tests: all 37 tests pass
