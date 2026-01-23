# Task: Add --set-balance CLI Command

## Objective
Add a CLI command to set opening balance for accounts in accounts.yaml.

## Usage
```bash
financial-consolidator --set-balance ACCOUNT_ID --balance AMOUNT --balance-date DATE
```

## Implementation

### 1. Add Arguments to create_parser()
Location: [cli.py](src/financial_consolidator/cli.py) in `create_parser()` after line 260

Add new argument group:
```python
# Balance management
balance_group = parser.add_argument_group("Balance Management")
balance_group.add_argument(
    "--set-balance",
    metavar="ACCOUNT_ID",
    help="Set opening balance for an account (use with --balance and optionally --balance-date)",
)
balance_group.add_argument(
    "--balance",
    type=str,
    metavar="AMOUNT",
    help="Balance amount in decimal format (e.g., 5234.56). Use with --set-balance.",
)
balance_group.add_argument(
    "--balance-date",
    type=lambda s: date.fromisoformat(s),
    metavar="DATE",
    help="Balance date in YYYY-MM-DD format. Use with --set-balance. Defaults to today.",
)
```

### 2. Create set_balance_command() Function
Add after `clear_corrections_command()` (~line 584):

```python
def set_balance_command(
    account_id: str,
    balance_amount: str,
    balance_date: date | None,
    accounts_path: Path,
    config_dir: Path,
) -> int:
    """Set the opening balance for an account."""
    from decimal import Decimal, InvalidOperation

    console.print(f"[bold]Setting opening balance for {account_id}[/bold]\n")

    # Parse the balance amount
    try:
        opening_balance = Decimal(balance_amount)
    except InvalidOperation:
        console.print(f"[red]Error: Invalid balance amount: {balance_amount}[/red]")
        console.print("[dim]Balance must be a valid decimal number (e.g., 5234.56)[/dim]")
        return 1

    # Use today's date if not specified
    if balance_date is None:
        balance_date = date.today()

    # Load config to get accounts
    try:
        config = load_config(
            accounts_path=accounts_path,
            config_dir=config_dir,
        )
    except FileNotFoundError as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return 1

    # Find the account
    account = config.accounts.get(account_id)
    if account is None:
        console.print(f"[red]Error: Account not found: {account_id}[/red]")
        console.print("\n[dim]Available accounts:[/dim]")
        for acc_id in sorted(config.accounts.keys()):
            console.print(f"  - {acc_id}")
        return 1

    # Update the account
    account.opening_balance = opening_balance
    account.opening_balance_date = balance_date

    # Determine the accounts file path
    actual_accounts_path = accounts_path or (config_dir / "accounts.yaml")

    # Save the updated accounts
    try:
        save_accounts(actual_accounts_path, config)
    except OSError as e:
        console.print(f"[red]Error saving accounts: {e}[/red]")
        return 1

    # Format the balance for display
    formatted_balance = f"${opening_balance:,.2f}"
    console.print(
        f"[green]Set opening balance for {account_id}: "
        f"{formatted_balance} as of {balance_date.isoformat()}[/green]"
    )
    console.print(f"[dim]Saved to: {actual_accounts_path}[/dim]")

    return 0
```

### 3. Add Command Handler in main()
Location: After `import_corrections` handler (~line 1013), before input-dir validation:

```python
# Handle balance management commands (no input-dir required)
if args.set_balance:
    if args.balance is None:
        console.print("[red]Error: --balance is required when using --set-balance[/red]")
        console.print(
            "[dim]Example: --set-balance chase_checking --balance 5234.56 --balance-date 2024-01-01[/dim]"
        )
        return 1
    return set_balance_command(
        account_id=args.set_balance,
        balance_amount=args.balance,
        balance_date=args.balance_date,
        accounts_path=args.accounts,
        config_dir=args.config_dir,
    )
```

## Key Files
- [cli.py](src/financial_consolidator/cli.py) - Add arguments, handler, command
- [config.py](src/financial_consolidator/config.py) - Uses existing `save_accounts()` at line 710

## Verification
1. `--help` shows Balance Management group
2. Valid: `--set-balance chase_checking --balance 5234.56 --balance-date 2024-01-01`
3. Error: Missing --balance shows helpful message
4. Error: Invalid account shows available accounts
5. Error: Non-numeric balance shows format help
6. accounts.yaml contains opening_balance and opening_balance_date after command
7. Run existing tests: `python3 -m pytest tests/ -v` - all 37 tests pass
