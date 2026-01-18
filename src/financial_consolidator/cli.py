"""Command-line interface for the financial consolidator."""

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from financial_consolidator import __version__
from financial_consolidator.config import Config, load_config, save_accounts
from financial_consolidator.models.account import Account, AccountType
from financial_consolidator.utils.logging_config import setup_logging, get_logger

console = Console()
logger = get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="financial-consolidator",
        description="Consolidate financial transactions from multiple file formats for forensic analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input-dir ./downloads --output analysis.xlsx
  %(prog)s -i ./downloads -o analysis.xlsx --start-date 2024-01-01
  %(prog)s -i ./downloads -o analysis.xlsx --csv --config ./my_config/settings.yaml
  %(prog)s -i ./downloads -o output.xlsx --no-interactive --strict
        """,
    )

    # Version
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Required arguments (unless --validate-only is used)
    parser.add_argument(
        "-i", "--input-dir",
        type=Path,
        default=None,
        help="Directory containing transaction files",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output Excel file path (e.g., ./financial_analysis.xlsx)",
    )

    # Optional arguments
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to settings.yaml (default: config/settings.yaml)",
    )

    parser.add_argument(
        "--categories",
        type=Path,
        default=None,
        help="Path to categories.yaml (default: config/categories.yaml)",
    )

    parser.add_argument(
        "--accounts",
        type=Path,
        default=None,
        help="Path to accounts.yaml (default: config/accounts.yaml)",
    )

    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("config"),
        help="Base config directory (default: ./config)",
    )

    # Date filtering
    parser.add_argument(
        "--start-date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Start date for filtering (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--end-date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="End date for filtering (YYYY-MM-DD)",
    )

    # Output options
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also export CSV files (one per sheet) for Google Sheets import",
    )

    # Processing options
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Non-interactive mode: skip unmapped files instead of prompting",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: abort on first parse error instead of skipping",
    )

    parser.add_argument(
        "--large-transaction-threshold",
        type=float,
        default=None,
        help="Override threshold for large transaction alerts",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (-v, -vv, -vvv)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files but do not generate output",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate configuration files only",
    )

    return parser


def get_log_level(verbosity: int) -> str:
    """Convert verbosity count to log level.

    Args:
        verbosity: Number of -v flags.

    Returns:
        Log level string.
    """
    if verbosity >= 2:
        return "DEBUG"
    elif verbosity >= 1:
        return "INFO"
    else:
        return "WARNING"


def prompt_for_account(filename: str, config: Config) -> Optional[Account]:
    """Prompt user to map a file to an account.

    Args:
        filename: The filename that needs mapping.
        config: Current configuration.

    Returns:
        Account if user provides mapping, None if skipped.
    """
    console.print(f"\n[yellow]File '{filename}' not mapped to any account.[/yellow]")

    # Show existing accounts
    if config.accounts:
        console.print("\nExisting accounts:")
        for i, (account_id, account) in enumerate(config.accounts.items(), 1):
            console.print(f"  {i}. {account.name} ({account_id})")

    console.print("\nOptions:")
    console.print("  - Enter a number to select an existing account")
    console.print("  - Enter a new account name to create one")
    console.print("  - Enter 'skip' to skip this file")

    while True:
        response = console.input("\n[bold]Your choice:[/bold] ").strip()

        if response.lower() == "skip":
            return None

        # Check if it's a number selecting existing account
        try:
            idx = int(response)
            accounts_list = list(config.accounts.values())
            if 1 <= idx <= len(accounts_list):
                account = accounts_list[idx - 1]
                config.add_file_mapping(filename, account.id)
                console.print(f"[green]Mapped '{filename}' to {account.name}[/green]")
                return account
            else:
                console.print("[red]Invalid number. Try again.[/red]")
                continue
        except ValueError:
            pass

        # Create new account
        account_name = response
        account_id = account_name.lower().replace(" ", "_").replace("-", "_")

        # Check for duplicate ID
        if account_id in config.accounts:
            console.print(f"[red]Account ID '{account_id}' already exists. Try a different name.[/red]")
            continue

        # Prompt for account type
        console.print("\nAccount types:")
        for i, atype in enumerate(AccountType, 1):
            console.print(f"  {i}. {atype.value}")

        while True:
            type_response = console.input("[bold]Select account type (number):[/bold] ").strip()
            try:
                type_idx = int(type_response)
                account_types = list(AccountType)
                if 1 <= type_idx <= len(account_types):
                    account_type = account_types[type_idx - 1]
                    break
                else:
                    console.print("[red]Invalid number. Try again.[/red]")
            except ValueError:
                console.print("[red]Please enter a number.[/red]")

        # Create account
        account = Account(
            id=account_id,
            name=account_name,
            account_type=account_type,
        )
        config.accounts[account_id] = account
        config.add_file_mapping(filename, account_id)

        console.print(f"[green]Created account '{account_name}' and mapped '{filename}'[/green]")
        return account


def validate_config(args: argparse.Namespace) -> int:
    """Validate configuration files.

    Args:
        args: Parsed command-line arguments.

    Returns:
        0 if valid, 1 if errors found.
    """
    console.print("[bold]Validating configuration files...[/bold]\n")

    errors = []
    warnings = []

    # Check config directory
    config_dir = args.config_dir
    if not config_dir.exists():
        warnings.append(f"Config directory not found: {config_dir}")

    # Check settings
    settings_path = args.config or (config_dir / "settings.yaml")
    if settings_path.exists():
        console.print(f"[green]✓[/green] Settings: {settings_path}")
    else:
        warnings.append(f"Settings file not found: {settings_path}")

    # Check accounts
    accounts_path = args.accounts or (config_dir / "accounts.yaml")
    if accounts_path.exists():
        console.print(f"[green]✓[/green] Accounts: {accounts_path}")
    else:
        warnings.append(f"Accounts file not found: {accounts_path}")

    # Check categories
    categories_path = args.categories or (config_dir / "categories.yaml")
    if categories_path.exists():
        console.print(f"[green]✓[/green] Categories: {categories_path}")
    else:
        warnings.append(f"Categories file not found: {categories_path}")

    # Try to load config
    try:
        config = load_config(
            settings_path=args.config,
            accounts_path=args.accounts,
            categories_path=args.categories,
            config_dir=config_dir,
        )
        console.print(f"\n[green]✓[/green] Configuration loaded successfully")
        console.print(f"  - {len(config.accounts)} accounts")
        console.print(f"  - {len(config.categories)} categories")
        console.print(f"  - {len(config.category_rules)} rules")
        console.print(f"  - {len(config.manual_overrides)} manual overrides")
    except Exception as e:
        errors.append(f"Failed to load configuration: {e}")

    # Report results
    if warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in warnings:
            console.print(f"  - {w}")

    if errors:
        console.print("\n[red]Errors:[/red]")
        for e in errors:
            console.print(f"  - {e}")
        return 1

    console.print("\n[green]Configuration is valid.[/green]")
    return 0


def display_summary(
    total_files: int,
    parsed_files: int,
    total_transactions: int,
    categorized: int,
    uncategorized: int,
    duplicates: int,
    anomalies: int,
    skipped_files: list[str],
    errors: list[str],
) -> None:
    """Display processing summary.

    Args:
        total_files: Total files found.
        parsed_files: Files successfully parsed.
        total_transactions: Total transactions processed.
        categorized: Transactions with categories.
        uncategorized: Transactions without categories.
        duplicates: Duplicate transactions found.
        anomalies: Anomalies detected.
        skipped_files: List of skipped files.
        errors: List of error messages.
    """
    console.print("\n[bold]Processing Summary[/bold]")
    console.print(f"  Files found: {total_files}")
    console.print(f"  Files parsed: {parsed_files}")
    console.print(f"  Total transactions: {total_transactions}")
    console.print(f"  Categorized: {categorized}")
    console.print(f"  Uncategorized: {uncategorized}")
    console.print(f"  Duplicates flagged: {duplicates}")
    console.print(f"  Anomalies detected: {anomalies}")

    if skipped_files:
        console.print(f"\n[yellow]Skipped files ({len(skipped_files)}):[/yellow]")
        for f in skipped_files[:10]:
            console.print(f"  - {f}")
        if len(skipped_files) > 10:
            console.print(f"  ... and {len(skipped_files) - 10} more")

    if errors:
        console.print(f"\n[red]Errors ({len(errors)}):[/red]")
        for e in errors[:10]:
            console.print(f"  - {e}")
        if len(errors) > 10:
            console.print(f"  ... and {len(errors) - 10} more")


def create_progress() -> Progress:
    """Create a progress display.

    Returns:
        Rich Progress instance.
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    )


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    log_level = get_log_level(args.verbose)
    setup_logging(level=log_level, console_output=args.verbose > 0)

    # Validate only mode
    if args.validate_only:
        return validate_config(args)

    # Validate required arguments for processing mode
    if args.input_dir is None:
        console.print("[red]Error: --input-dir is required[/red]")
        parser.print_usage()
        return 1

    if args.output is None:
        console.print("[red]Error: --output is required[/red]")
        parser.print_usage()
        return 1

    # Validate input directory
    if not args.input_dir.exists():
        console.print(f"[red]Error: Input directory not found: {args.input_dir}[/red]")
        return 1

    if not args.input_dir.is_dir():
        console.print(f"[red]Error: Not a directory: {args.input_dir}[/red]")
        return 1

    # Load configuration
    try:
        config = load_config(
            settings_path=args.config,
            accounts_path=args.accounts,
            categories_path=args.categories,
            config_dir=args.config_dir,
        )
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("Run with --validate-only to check configuration files.")
        return 1

    # Apply CLI overrides
    if args.start_date:
        config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    if args.large_transaction_threshold:
        from decimal import Decimal
        config.anomaly.large_transaction_threshold = Decimal(str(args.large_transaction_threshold))

    # Display startup info
    console.print(f"[bold]Financial Transaction Consolidator v{__version__}[/bold]\n")
    console.print(f"Input directory: {args.input_dir}")
    console.print(f"Output file: {args.output}")
    if config.start_date:
        console.print(f"Date range: {config.start_date} to {config.end_date or 'present'}")

    # Import processing and output modules
    from financial_consolidator.parsers import FileDetector, ParseError
    from financial_consolidator.processing import (
        Normalizer,
        Categorizer,
        Deduplicator,
        BalanceCalculator,
        AnomalyDetector,
    )
    from financial_consolidator.output import ExcelWriter, CSVExporter
    from financial_consolidator.models.transaction import Transaction

    # Initialize components
    detector = FileDetector(strict=args.strict)
    normalizer = Normalizer(config)
    categorizer = Categorizer(config)
    deduplicator = Deduplicator(config)
    balance_calculator = BalanceCalculator(config)
    anomaly_detector = AnomalyDetector(config)

    # Track statistics
    total_files = 0
    parsed_files = 0
    skipped_files: list[str] = []
    error_list: list[str] = []
    all_transactions: list[Transaction] = []

    # Discover files
    with console.status("[bold green]Discovering files..."):
        files = detector.discover_files(args.input_dir)
        total_files = len(files)

    console.print(f"\nFound {total_files} files to process")

    if total_files == 0:
        console.print("[yellow]No supported files found in input directory.[/yellow]")
        return 0

    # Parse files
    with create_progress() as progress:
        task = progress.add_task("Parsing files...", total=total_files)

        for file_path in files:
            progress.update(task, advance=1, description=f"Parsing {file_path.name}...")

            # Get account mapping
            account = config.get_account_for_file(file_path.name)

            if account is None:
                if args.no_interactive:
                    skipped_files.append(f"{file_path.name}: No account mapping")
                    continue
                else:
                    # Interactive mode: prompt for account
                    account = prompt_for_account(file_path.name, config)
                    if account is None:
                        skipped_files.append(f"{file_path.name}: Skipped by user")
                        continue

            # Parse file
            try:
                raw_transactions = detector.parse_file(file_path)

                # Normalize transactions
                transactions = normalizer.normalize(raw_transactions, account)
                all_transactions.extend(transactions)
                parsed_files += 1

            except ParseError as e:
                error_msg = f"{file_path.name}: {e}"
                if args.strict:
                    console.print(f"[red]Error: {error_msg}[/red]")
                    return 1
                error_list.append(error_msg)
                logger.warning(error_msg)
            except Exception as e:
                error_msg = f"{file_path.name}: Unexpected error: {e}"
                if args.strict:
                    console.print(f"[red]Error: {error_msg}[/red]")
                    return 1
                error_list.append(error_msg)
                logger.error(error_msg)

    console.print(f"Parsed {len(all_transactions)} transactions from {parsed_files} files")

    if not all_transactions:
        console.print("[yellow]No transactions found.[/yellow]")
        return 0

    # Process transactions
    with console.status("[bold green]Categorizing transactions..."):
        categorizer.categorize(all_transactions)

    with console.status("[bold green]Detecting duplicates..."):
        deduplicator.find_duplicates(all_transactions)

    with console.status("[bold green]Calculating balances..."):
        balance_calculator.calculate_balances(all_transactions)

    with console.status("[bold green]Detecting anomalies..."):
        anomaly_detector.detect_anomalies(all_transactions)
        date_gaps = anomaly_detector.get_date_gaps(all_transactions)

    # Calculate statistics
    categorized = sum(1 for t in all_transactions if not t.is_uncategorized)
    uncategorized = sum(1 for t in all_transactions if t.is_uncategorized)
    duplicates = sum(1 for t in all_transactions if t.is_duplicate)
    anomalies = sum(1 for t in all_transactions if t.is_anomaly)

    # Generate output (unless dry run)
    if not args.dry_run:
        with create_progress() as progress:
            # Write Excel
            task = progress.add_task("Writing Excel output...", total=None)
            excel_writer = ExcelWriter(config)
            excel_writer.write(args.output, all_transactions, date_gaps)
            progress.update(task, completed=True)

            # Write CSV if requested
            if args.csv:
                task = progress.add_task("Writing CSV files...", total=None)
                csv_exporter = CSVExporter(config)
                csv_exporter.export(args.output, all_transactions, date_gaps)
                progress.update(task, completed=True)

        console.print(f"\n[green]Output written to {args.output}[/green]")
        if args.csv:
            console.print(f"[green]CSV files written to {args.output.parent}[/green]")
    else:
        console.print("\n[yellow]Dry run - no output generated[/yellow]")

    # Display summary
    display_summary(
        total_files=total_files,
        parsed_files=parsed_files,
        total_transactions=len(all_transactions),
        categorized=categorized,
        uncategorized=uncategorized,
        duplicates=duplicates,
        anomalies=anomalies,
        skipped_files=skipped_files,
        errors=error_list,
    )

    # Save any account mappings if interactive mode was used
    if not args.no_interactive and config.accounts:
        accounts_path = args.accounts or (args.config_dir / "accounts.yaml")
        save_accounts(accounts_path, config)

    return 0


if __name__ == "__main__":
    sys.exit(main())
