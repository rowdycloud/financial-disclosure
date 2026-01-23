# Task: Add Post-Parsing Balance Inference (Stage B)

> **Status:** ✅ Complete (PR #8)
> **Prerequisite:** Task 02 complete (PR #7) - `opening_balance: Decimal | None` type now in place

## Objective

After file parsing, infer opening balance for accounts where it wasn't set during interactive prompts.

## Location
[cli.py](src/financial_consolidator/cli.py) after Phase 2 parsing loop (~line 1180)

## Background
- Account prompting (Phase 1) happens BEFORE file parsing (Phase 2)
- If user left opening_balance blank during prompts, `account.opening_balance = None`
- After parsing, we have transaction data including `balance` field from CSVs
- We can now calculate: `opening_balance = first_balance - first_amount`

## Implementation

### Step 1: Preserve Raw Balance During Normalization
First, modify [normalizer.py](src/financial_consolidator/processing/normalizer.py) to preserve the balance field from raw transactions.

Find the `normalize()` method and where Transaction objects are created. Add:

```python
# Preserve raw balance for inference (if available)
raw_balance = getattr(raw_txn, 'balance', None)
if raw_balance is not None:
    transaction._raw_balance = raw_balance
```

Or add `_raw_balance` as an optional field on Transaction model in [transaction.py](src/financial_consolidator/models/transaction.py):

```python
# Internal field for balance inference (not serialized)
_raw_balance: Decimal | None = field(default=None, repr=False)
```

### Step 2: Add Inference Step After Parsing
In [cli.py](src/financial_consolidator/cli.py), after the Phase 2 parsing loop completes (~line 1197), before categorization:

```python
# Phase 2.5: Infer opening balances where needed
accounts_with_transactions = {t.account_id for t in all_transactions}
accounts_needing_inference = [
    acc for acc in config.accounts.values()
    if acc.opening_balance is None and acc.id in accounts_with_transactions
]

if accounts_needing_inference:
    console.print("\n[bold]Inferring opening balances...[/bold]")

    for account in accounts_needing_inference:
        # Get transactions for this account, sorted chronologically
        account_txns = [t for t in all_transactions if t.account_id == account.id]
        account_txns.sort(key=lambda t: (t.date, t.description))

        first_txn = account_txns[0] if account_txns else None

        if first_txn and hasattr(first_txn, '_raw_balance') and first_txn._raw_balance is not None:
            # Infer: opening = first_balance - first_amount
            inferred = first_txn._raw_balance - first_txn.amount
            account.opening_balance = inferred
            account.opening_balance_date = first_txn.date
            console.print(
                f"  [dim]Inferred opening balance for {account.id}: "
                f"${inferred:,.2f} (from first transaction)[/dim]"
            )
        else:
            # Cannot infer, default to zero with warning
            account.opening_balance = Decimal("0")
            account.opening_balance_date = first_txn.date if first_txn else date.today()
            console.print(
                f"  [yellow]Could not infer balance for {account.id}, "
                f"defaulting to $0.00[/yellow]"
            )

    # Config will be saved at end of run via existing save_accounts() call
```

### Step 3: Ensure Config is Saved
Verify that `save_accounts()` is called at the end of a successful run. Check around line 1350+ in cli.py for where accounts are saved after processing.

If not present, add after all processing completes:
```python
# Save any account updates (including inferred balances)
accounts_path = args.accounts or (args.config_dir / "accounts.yaml")
save_accounts(accounts_path, config)
```

## Key Files
- [cli.py](src/financial_consolidator/cli.py) - Add inference logic after parsing
- [normalizer.py](src/financial_consolidator/processing/normalizer.py) - Preserve raw balance
- [transaction.py](src/financial_consolidator/models/transaction.py) - Optional: add _raw_balance field
- [csv_parser.py](src/financial_consolidator/parsers/csv_parser.py) - Already parses balance column (line ~200)

## Credit Card Note
Balance inference works best for asset accounts (checking/savings). For liability accounts (credit cards), the "balance" column semantics may differ by bank. If inference produces unexpected results, users should use `--set-balance` to correct.

## Verification

1. Create new account with blank balance (leave opening balance empty during prompts)
2. Ensure test CSV has a "Balance" column with values
3. Run processing: `PYTHONPATH=src python -c "from financial_consolidator.cli import main; main()" -i ./test_data -o ./output.xlsx`
4. Verify log shows "Inferred opening balance for {account}: ${amount}"
5. Verify accounts.yaml now contains opening_balance and opening_balance_date
6. Verify the math: opening_balance = first_balance - first_amount
7. Run existing tests: all 52 tests pass (updated from 37)

## Alignment Notes (from Task 02)

- Task 02 changed `opening_balance` type to `Decimal | None` - this task correctly checks `is None`
- Config serialization: None values NOT saved to YAML (on reload becomes None, triggering inference)
- **Apply same validation as Task 02**: ±$1 trillion max, dates ≥1970-01-01, not in future
- Inferred values should be rounded to 2 decimals with ROUND_HALF_UP

---

## Implementation Summary (PR #8)

### Files Modified

| File | Changes |
|------|---------|
| cli.py | Added `_apply_default_balance()` and `infer_opening_balances()` functions (+172 lines, ~line 1620) |

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| No model changes | Leveraged existing `raw_data.balance` field preserved during normalization (simpler than planned `_raw_balance` approach) |
| Consistent sorting | Uses same sort key as balance_calculator for deterministic "first transaction" |
| Documented assumption | CSV balance is assumed to be AFTER transaction (most common format) |

### Functions Added

- **`_apply_default_balance()`** - Helper that applies $0.00 default when inference fails, with user warning
- **`infer_opening_balances()`** - Main inference function:
  - Identifies accounts where `opening_balance is None`
  - Reads raw balance from `first_txn.raw_data.balance`
  - Calculates: `opening_balance = csv_balance - transaction_amount`
  - Applies same validation as Task 02
  - Falls back to $0.00 with warning if inference fails
  - Prints note for credit card/loan accounts to verify balance sign

### Integration

- Called after Phase 2 parsing (~line 1620), before categorization
- Uses existing `save_accounts()` call at end of run
- Save condition updated to save when inference occurs (even in non-interactive mode)

### Tests

- All 52 existing tests pass
- Cubic review iterated until clean
