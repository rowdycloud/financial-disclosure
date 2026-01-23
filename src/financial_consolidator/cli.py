"""Command-line interface for the financial consolidator."""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from financial_consolidator import __version__
from financial_consolidator.config import (
    Config,
    ConfigError,
    load_config,
    load_corrections,
    save_accounts,
    save_corrections,
)
from financial_consolidator.models.account import Account, AccountType
from financial_consolidator.processing.report_generator import generate_pl_summary
from financial_consolidator.utils.logging_config import get_logger, setup_logging

# Load environment variables from .env file (if it exists)
load_dotenv()

console = Console()
logger = get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="financial-consolidator",
        description=(
            "Consolidate financial transactions from multiple file formats "
            "for forensic analysis"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --input-dir ./downloads
  %(prog)s -i ./downloads -o my_report.csv --xlsx
  %(prog)s -i ./downloads -o report.xlsx --csv
  %(prog)s -i ./downloads --start-date 2024-01-01 --no-interactive
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
        help="Output file path (default: analysis/analysis_YYYYMMDD_HHMMSS.csv)",
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
        help="Also export CSV files (when using .xlsx output)",
    )

    parser.add_argument(
        "--xlsx",
        action="store_true",
        help="Also export Excel workbook (when using CSV output)",
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

    # AI categorization arguments
    ai_group = parser.add_argument_group("AI Categorization")
    ai_group.add_argument(
        "--ai",
        action="store_true",
        help="Enable all AI features (validation + categorization)",
    )
    ai_group.add_argument(
        "--ai-validate",
        action="store_true",
        help="Validate low-confidence rule-based categorizations with AI",
    )
    ai_group.add_argument(
        "--ai-categorize",
        action="store_true",
        help="Use AI to categorize uncategorized transactions",
    )
    ai_group.add_argument(
        "--ai-budget",
        type=float,
        default=None,
        help="Maximum AI spend per run in USD (default: from config or $5.00)",
    )
    ai_group.add_argument(
        "--ai-dry-run",
        action="store_true",
        help="Show AI cost estimates without making API calls",
    )
    ai_group.add_argument(
        "--ai-confidence",
        type=float,
        default=None,
        help="Confidence threshold for AI validation (default: 0.7)",
    )
    ai_group.add_argument(
        "--skip-ai-confirm",
        action="store_true",
        help="Skip confirmation prompts for AI spending",
    )

    # Additional export options
    parser.add_argument(
        "--export-uncategorized",
        type=Path,
        default=None,
        metavar="FILE",
        help="Export uncategorized transactions for review",
    )
    parser.add_argument(
        "--export-summary",
        type=Path,
        default=None,
        metavar="FILE",
        help="Export categorization summary statistics",
    )

    # Corrections management
    corrections_group = parser.add_argument_group("Corrections Management")
    corrections_group.add_argument(
        "--import-corrections",
        type=Path,
        default=None,
        metavar="FILE",
        help="Import category corrections from reviewed output file (XLSX or CSV)",
    )
    corrections_group.add_argument(
        "--show-corrections",
        action="store_true",
        help="Show current corrections and exit",
    )
    corrections_group.add_argument(
        "--clear-corrections",
        action="store_true",
        help="Clear all stored corrections",
    )
    corrections_group.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts (for --clear-corrections)",
    )
    corrections_group.add_argument(
        "--corrections-file",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to corrections.yaml (default: config/corrections.yaml)",
    )

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


def generate_default_output_path() -> Path:
    """Generate default output path with timestamp.

    Returns:
        Path with format analysis/YYYYMMDD_HHMMSS/analysis.csv
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(f"analysis/{timestamp}/analysis.csv")


def validate_output_path(path: Path, base_dir: Path | None = None) -> Path:
    """Validate that output path is within allowed directory.

    Prevents path traversal attacks by ensuring the resolved path
    is within the base directory (defaults to current working directory).

    Args:
        path: The path to validate.
        base_dir: Base directory to constrain paths within (default: cwd).

    Returns:
        The resolved, validated path.

    Raises:
        ValueError: If the path escapes the allowed directory.
    """
    if base_dir is None:
        base_dir = Path.cwd()

    # Resolve both paths to absolute, normalized form
    resolved_base = base_dir.resolve()
    resolved_path = (base_dir / path).resolve()

    # Check if resolved path is within base directory
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError:
        raise ValueError(
            f"Invalid path: '{path}' escapes the allowed directory. "
            f"Paths must be within '{resolved_base}'"
        ) from None

    return resolved_path


def prompt_for_account(filename: str, config: Config) -> Account | None:
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
            console.print(
                f"[red]Account ID '{account_id}' already exists. "
                "Try a different name.[/red]"
            )
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


def find_stale_mappings(config: Config, discovered_files: list[Path]) -> list[str]:
    """Find file mappings that don't correspond to any discovered files.

    Args:
        config: Current configuration with file_mappings.
        discovered_files: List of files found in input directory.

    Returns:
        List of stale filenames (mapped but not found).
    """
    discovered_names = {f.name for f in discovered_files}
    stale = [
        filename for filename in config.file_mappings
        if filename not in discovered_names
    ]
    return stale


def prompt_prune_stale_mappings(stale_filenames: list[str], config: Config) -> bool:
    """Prompt user to prune stale file mappings.

    Args:
        stale_filenames: List of stale mapping filenames.
        config: Configuration to modify.

    Returns:
        True if mappings were pruned, False otherwise.
    """
    console.print(f"\n[yellow]Found {len(stale_filenames)} stale file mapping(s):[/yellow]")
    for filename in stale_filenames[:10]:
        console.print(f"  - {filename}")
    if len(stale_filenames) > 10:
        console.print(f"  ... and {len(stale_filenames) - 10} more")

    prompt = "\n[bold]Remove stale mappings from accounts.yaml? [Y/n]:[/bold] "
    response = console.input(prompt).strip().lower()

    if response in ("y", ""):
        for filename in stale_filenames:
            config.file_mappings.pop(filename, None)
        console.print(f"[green]Removed {len(stale_filenames)} stale mapping(s)[/green]")
        return True

    return False


def show_corrections_command(corrections_path: Path) -> int:
    """Show current corrections.

    Args:
        corrections_path: Path to corrections.yaml.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    console.print("[bold]Current Corrections[/bold]\n")

    if not corrections_path.exists():
        console.print("[dim]No corrections file found.[/dim]")
        console.print(f"[dim]Expected location: {corrections_path}[/dim]")
        return 0

    try:
        corrections = load_corrections(corrections_path)
    except yaml.YAMLError as e:
        console.print(f"[red]Error: Corrupted corrections file: {e}[/red]")
        console.print(f"[dim]File: {corrections_path}[/dim]")
        console.print("[dim]Try deleting the file or fixing the YAML syntax.[/dim]")
        return 1
    except ConfigError as e:
        console.print(f"[red]Error: Invalid corrections format: {e}[/red]")
        return 1
    except PermissionError:
        console.print(f"[red]Error: Permission denied reading: {corrections_path}[/red]")
        return 1
    except OSError as e:
        console.print(f"[red]Error reading corrections file: {e}[/red]")
        return 1

    if not corrections:
        console.print("[dim]No corrections stored.[/dim]")
        return 0

    console.print(f"Found {len(corrections)} corrections:\n")

    from rich.table import Table

    table = Table(show_header=True, header_style="bold")
    table.add_column("Fingerprint", style="dim")
    table.add_column("Category ID")
    table.add_column("Source File")
    table.add_column("Corrected At")

    for fingerprint, correction in sorted(corrections.items()):
        table.add_row(
            fingerprint[:12] + "...",
            correction.category_id,
            correction.source_file or "-",
            correction.corrected_at or "-"
        )

    console.print(table)

    return 0


def clear_corrections_command(corrections_path: Path, force: bool = False) -> int:
    """Clear all stored corrections.

    Args:
        corrections_path: Path to corrections.yaml.
        force: Skip confirmation prompt if True.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    if not corrections_path.exists():
        console.print("[dim]No corrections file found. Nothing to clear.[/dim]")
        return 0

    try:
        corrections = load_corrections(corrections_path)
    except (yaml.YAMLError, ConfigError) as e:
        console.print(f"[red]Error reading corrections: {e}[/red]")
        return 1

    count = len(corrections)

    if count == 0:
        console.print("[dim]No corrections stored. Nothing to clear.[/dim]")
        return 0

    # Confirm with user unless --force is specified
    if not force:
        console.print(f"[yellow]This will delete {count} corrections.[/yellow]")
        response = console.input("Are you sure? [y/N]: ")

        if response.lower() != "y":
            console.print("[dim]Cancelled.[/dim]")
            return 0

    # Clear by saving empty dict
    try:
        save_corrections(corrections_path, {})
    except OSError as e:
        console.print(f"[red]Error saving corrections: {e}[/red]")
        return 1

    console.print(f"[green]Cleared {count} corrections.[/green]")

    return 0


def set_balance_command(
    account_id: str,
    balance_amount: str,
    balance_date: date | None,
    accounts_path: Path | None,
    config_dir: Path,
) -> int:
    """Set the opening balance for an account."""
    from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

    console.print(f"[bold]Setting opening balance for {account_id}[/bold]\n")

    # Parse the balance amount
    try:
        opening_balance = Decimal(balance_amount)
    except InvalidOperation:
        console.print(f"[red]Error: Invalid balance amount: {balance_amount}[/red]")
        console.print("[dim]Balance must be a valid decimal number (e.g., 5234.56)[/dim]")
        return 1

    # Validate the balance is a finite number (not inf or nan)
    if not opening_balance.is_finite():
        console.print(f"[red]Error: Invalid balance amount: {balance_amount}[/red]")
        console.print("[dim]Balance must be a finite number, not infinity or NaN[/dim]")
        return 1

    # Normalize to 2 decimal places for financial consistency
    original_balance = opening_balance
    try:
        opening_balance = opening_balance.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        console.print(f"[red]Error: Balance value too large: {balance_amount}[/red]")
        console.print("[dim]Balance magnitude exceeds representable range[/dim]")
        return 1

    # Notify user if rounding occurred
    if opening_balance != original_balance:
        console.print(
            f"[yellow]Note: Balance rounded to 2 decimal places: {original_balance} → {opening_balance}[/yellow]"
        )

    # Warn about negative balances (valid for credit cards but unusual)
    if opening_balance < 0:
        console.print(
            "[yellow]Note: Negative opening balance entered. "
            "This is valid for credit cards and lines of credit.[/yellow]"
        )

    # Capture today's date once for consistent validation
    today = date.today()

    # Use today's date if not specified
    if balance_date is None:
        balance_date = today
        console.print(
            f"[dim]Using today's date ({today.isoformat()}) for balance date. "
            "Use --balance-date to specify a different date.[/dim]"
        )

    # Validate balance date is not unreasonably old
    # Unix epoch (1970) prevents obvious typos like 1924 instead of 2024
    # while still allowing legitimate historical data from the computing era
    min_date = date(1970, 1, 1)
    if balance_date < min_date:
        console.print(f"[red]Error: Balance date too old: {balance_date}[/red]")
        console.print(f"[dim]Balance date must be {min_date.isoformat()} or later[/dim]")
        return 1

    # Validate balance date is not in the future
    if balance_date > today:
        console.print(f"[red]Error: Balance date cannot be in the future: {balance_date}[/red]")
        console.print("[dim]Opening balance date must be today or earlier[/dim]")
        return 1

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

    # Format the balance for display (handle negative properly)
    if opening_balance < 0:
        formatted_balance = f"-${abs(opening_balance):,.2f}"
    else:
        formatted_balance = f"${opening_balance:,.2f}"
    console.print(
        f"[green]Set opening balance for {account_id}: "
        f"{formatted_balance} as of {balance_date.isoformat()}[/green]"
    )
    console.print(f"[dim]Saved to: {actual_accounts_path}[/dim]")

    return 0


def import_corrections_command(
    import_path: Path,
    corrections_path: Path,
    config_dir: Path,
    categories_path: Path | None,
) -> int:
    """Import corrections from a reviewed output file.

    Args:
        import_path: Path to the XLSX or CSV file to import.
        corrections_path: Path to corrections.yaml.
        config_dir: Path to config directory.
        categories_path: Optional path to categories.yaml.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    from financial_consolidator.processing.correction_importer import (
        CorrectionImportError,
        import_corrections_from_file,
    )

    console.print(f"[bold]Importing corrections from {import_path}[/bold]\n")

    if not import_path.exists():
        console.print(f"[red]Error: File not found: {import_path}[/red]")
        return 1

    # Load config to get category definitions
    try:
        config = load_config(
            categories_path=categories_path,
            config_dir=config_dir,
        )
    except FileNotFoundError as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return 1

    # Import corrections
    try:
        result = import_corrections_from_file(import_path, config)
    except CorrectionImportError as e:
        console.print(f"[red]Error importing corrections: {e}[/red]")
        return 1
    except FileNotFoundError as e:
        console.print(f"[red]File not found: {e}[/red]")
        return 1
    except IsADirectoryError:
        console.print(f"[red]Error: Path is a directory, not a file: {import_path}[/red]")
        return 1
    except PermissionError:
        console.print(f"[red]Error: Permission denied reading: {import_path}[/red]")
        return 1
    except OSError as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        return 1

    # Load existing corrections
    try:
        existing = load_corrections(corrections_path) if corrections_path.exists() else {}
    except (yaml.YAMLError, ConfigError) as e:
        console.print(f"[red]Error reading existing corrections: {e}[/red]")
        return 1

    # Merge (new corrections override existing)
    merged = {**existing, **result.corrections}
    new_count = len(result.corrections)
    override_count = len(set(result.corrections.keys()) & set(existing.keys()))

    # Save merged corrections
    try:
        save_corrections(corrections_path, merged)
    except OSError as e:
        console.print(f"[red]Error saving corrections: {e}[/red]")
        return 1

    # Display results
    console.print(f"[green]Imported {new_count} corrections[/green]")
    if override_count > 0:
        console.print(f"[dim]  ({override_count} overrode existing corrections)[/dim]")
    console.print(f"[green]Total corrections: {len(merged)}[/green]")

    if result.skipped_count > 0:
        console.print(f"\n[yellow]Skipped {result.skipped_count} rows:[/yellow]")
        for reason in result.skipped_reasons[:10]:  # Show first 10
            console.print(f"[dim]  - {reason}[/dim]")
        if len(result.skipped_reasons) > 10:
            console.print(f"[dim]  ... and {len(result.skipped_reasons) - 10} more[/dim]")

    console.print(f"\n[dim]Corrections saved to: {corrections_path}[/dim]")

    return 0


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
        console.print("\n[green]✓[/green] Configuration loaded successfully")
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
        for err in errors:
            console.print(f"  - {err}")
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


def run_ai_categorization(
    args: argparse.Namespace,
    config: Config,
    transactions: list,
    console_instance: Console,
) -> dict[str, object]:
    """Run AI-powered categorization if enabled.

    Args:
        args: Parsed command-line arguments.
        config: Application configuration.
        transactions: List of transactions to process.
        console_instance: Rich console for output.

    Returns:
        Dictionary of AI usage statistics.
    """
    from financial_consolidator.processing.ai import (
        AICategorizer,
        APIKeyNotFoundError,
        BudgetExceededError,
    )

    # Determine which AI features to run
    do_validate = args.ai or args.ai_validate
    do_categorize = args.ai or args.ai_categorize

    # Get AI settings
    budget_limit = args.ai_budget or config.ai.budget_limit
    confidence_threshold = args.ai_confidence or config.ai.validation_threshold

    console_instance.print("\n[bold]AI Categorization[/bold]")

    # Create AI categorizer
    try:
        ai_categorizer = AICategorizer.create(
            config=config,
            api_key_env=config.ai.api_key_env,
            model=config.ai.model,
            budget_limit=budget_limit,
            validation_threshold=confidence_threshold,
        )
    except Exception as e:
        console_instance.print(f"[red]Failed to initialize AI: {e}[/red]")
        return {}

    if not ai_categorizer.is_available:
        console_instance.print(
            f"[yellow]AI not available - set {config.ai.api_key_env} environment variable[/yellow]"
        )
        return {}

    # Count transactions for each operation
    low_conf_count = sum(
        1 for t in transactions
        if t.category and not t.is_uncategorized and t.confidence_score < confidence_threshold
    )
    uncategorized_count = sum(1 for t in transactions if t.is_uncategorized)

    # Estimate costs
    total_estimate = 0.0
    if do_validate and low_conf_count > 0:
        low_conf_txns = [
            t for t in transactions
            if t.category and not t.is_uncategorized
            and t.confidence_score < confidence_threshold
        ]
        val_estimate = ai_categorizer.estimate_validation_cost(low_conf_txns)
        console_instance.print(
            f"  Validation: {low_conf_count} transactions, ~${val_estimate.estimated_cost:.4f}"
        )
        total_estimate += val_estimate.estimated_cost

    if do_categorize and uncategorized_count > 0:
        cat_estimate = ai_categorizer.estimate_categorization_cost(
            [t for t in transactions if t.is_uncategorized]
        )
        cost = cat_estimate.estimated_cost
        console_instance.print(
            f"  Categorization: {uncategorized_count} transactions, ~${cost:.4f}"
        )
        total_estimate += cat_estimate.estimated_cost

    if total_estimate == 0:
        console_instance.print("[dim]No transactions need AI processing[/dim]")
        return {}

    console_instance.print(f"  [bold]Total estimated cost: ${total_estimate:.4f}[/bold]")
    console_instance.print(f"  Budget limit: ${budget_limit:.2f}")

    # Dry run - just show estimates
    if args.ai_dry_run:
        console_instance.print("[yellow]Dry run - no API calls made[/yellow]")
        return {"dry_run": True, "estimated_cost": total_estimate}

    # Confirm with user (unless skipped)
    if config.ai.require_confirmation and not args.skip_ai_confirm:
        response = console_instance.input(
            f"\n[bold]Proceed with AI processing (~${total_estimate:.4f})? [Y/n]:[/bold] "
        ).strip().lower()
        if response not in ("y", "yes", ""):
            console_instance.print("[yellow]AI processing cancelled[/yellow]")
            return {"cancelled": True}

    # Run AI validation
    if do_validate and low_conf_count > 0:
        console_instance.print("\n[bold green]Running AI validation...[/bold green]")
        try:
            val_results = ai_categorizer.validate_low_confidence(
                transactions, apply_corrections=True
            )
            validated = sum(1 for r in val_results if r.status.value == "validated")
            corrected = sum(1 for r in val_results if r.status.value == "corrected")
            console_instance.print(
                f"  Validated: {validated}, Corrected: {corrected}, "
                f"Uncertain: {len(val_results) - validated - corrected}"
            )
        except BudgetExceededError as e:
            console_instance.print(f"[red]Budget exceeded: {e}[/red]")
        except APIKeyNotFoundError as e:
            console_instance.print(f"[red]API key error: {e}[/red]")
        except Exception as e:
            console_instance.print(f"[red]Validation error: {e}[/red]")
            logger.exception("AI validation failed")

    # Run AI categorization
    if do_categorize and uncategorized_count > 0:
        console_instance.print("\n[bold green]Running AI categorization...[/bold green]")
        batch_size = 20
        total_batches = (uncategorized_count + batch_size - 1) // batch_size

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console_instance,
            ) as progress:
                task = progress.add_task(
                    f"Processing {uncategorized_count} transactions...",
                    total=total_batches
                )

                def on_progress(current_batch: int, _total: int) -> None:
                    progress.update(task, completed=current_batch)

                cat_result = ai_categorizer.categorize_uncategorized(
                    transactions,
                    use_batch=True,
                    batch_size=batch_size,
                    progress_callback=on_progress,
                )

            console_instance.print(
                f"  Categorized: {cat_result.succeeded}, Failed: {cat_result.failed}"
            )
            if cat_result.errors:
                for err in cat_result.errors[:3]:
                    console_instance.print(f"  [dim]Error: {err}[/dim]")
        except BudgetExceededError as e:
            console_instance.print(f"[red]Budget exceeded: {e}[/red]")
        except APIKeyNotFoundError as e:
            console_instance.print(f"[red]API key error: {e}[/red]")
        except Exception as e:
            console_instance.print(f"[red]Categorization error: {e}[/red]")
            logger.exception("AI categorization failed")

    # Get usage stats
    stats = ai_categorizer.client.usage_stats
    console_instance.print(
        f"\n  [bold]AI Usage:[/bold] {stats.total_requests} requests, "
        f"${stats.total_cost:.4f} spent"
    )

    return {
        "total_requests": stats.total_requests,
        "total_tokens": stats.total_input_tokens + stats.total_output_tokens,
        "total_cost": stats.total_cost,
        "validations_performed": stats.validations_performed,
        "categorizations_performed": stats.categorizations_performed,
    }


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

    # Handle corrections management commands (no input-dir required)
    corrections_path = args.corrections_file or (args.config_dir / "corrections.yaml")

    if args.show_corrections:
        return show_corrections_command(corrections_path)

    if args.clear_corrections:
        return clear_corrections_command(corrections_path, force=args.force)

    if args.import_corrections:
        return import_corrections_command(
            args.import_corrections,
            corrections_path,
            args.config_dir,
            args.categories,
        )

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

    # Validate required arguments for processing mode
    if args.input_dir is None:
        console.print("[red]Error: --input-dir is required[/red]")
        parser.print_usage()
        return 1

    if args.output is None:
        args.output = generate_default_output_path()
        console.print(f"[dim]Using default output: {args.output}[/dim]")

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
            corrections_path=corrections_path,
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
    from financial_consolidator.models.transaction import Transaction
    from financial_consolidator.output import CSVExporter, ExcelWriter
    from financial_consolidator.parsers import FileDetector, ParseError
    from financial_consolidator.processing import (
        AnomalyDetector,
        BalanceCalculator,
        Categorizer,
        Deduplicator,
        Normalizer,
    )

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
    total_raw_transactions = 0
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

    # Check for stale mappings (interactive mode only)
    if not args.no_interactive:
        stale_mappings = find_stale_mappings(config, files)
        if stale_mappings:
            prompt_prune_stale_mappings(stale_mappings, config)

    # Phase 1: Resolve account mappings (interactive prompts happen here, before progress bar)
    file_account_map: dict[Path, Account] = {}
    for file_path in files:
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

        file_account_map[file_path] = account

    # Phase 2: Parse files (progress bar, no prompts)
    files_to_parse = list(file_account_map.keys())
    with create_progress() as progress:
        task = progress.add_task("Parsing files...", total=len(files_to_parse))

        for file_path in files_to_parse:
            account = file_account_map[file_path]

            # Parse file
            try:
                raw_transactions = detector.parse_file(file_path)
                file_txn_count = len(raw_transactions)
                total_raw_transactions += file_txn_count

                # Normalize transactions
                transactions = normalizer.normalize(raw_transactions, account)
                all_transactions.extend(transactions)
                parsed_files += 1

                # Success output - show both counts when they differ
                normalized_count = len(transactions)
                if normalized_count == file_txn_count:
                    progress.console.print(
                        f"  [green]✓[/green] {file_path.name}: {file_txn_count} transactions"
                    )
                else:
                    progress.console.print(
                        f"  [green]✓[/green] {file_path.name}: {normalized_count}/{file_txn_count} transactions"
                    )

            except ParseError as e:
                error_msg = f"{file_path.name}: {e}"
                if args.strict:
                    console.print(f"[red]Error: {error_msg}[/red]")
                    return 1
                error_list.append(error_msg)
                logger.warning(error_msg)
                # Failure output
                progress.console.print(
                    f"  [red]✗[/red] {file_path.name}: failed - {e}"
                )
            except Exception as e:
                error_msg = f"{file_path.name}: Unexpected error: {e}"
                if args.strict:
                    console.print(f"[red]Error: {error_msg}[/red]")
                    return 1
                error_list.append(error_msg)
                logger.error(error_msg)
                # Failure output
                progress.console.print(
                    f"  [red]✗[/red] {file_path.name}: failed - {e}"
                )

            progress.update(task, advance=1)

    if config.start_date or config.end_date:
        # Date filter active - show ratio with date context
        date_info = f"{config.start_date or 'start'} to {config.end_date or 'present'}"
        console.print(
            f"Parsed {len(all_transactions)}/{total_raw_transactions} transactions "
            f"from {parsed_files} files (date range: {date_info})"
        )
    else:
        # No date filter - show normalization ratio
        console.print(
            f"Parsed {len(all_transactions)}/{total_raw_transactions} transactions "
            f"from {parsed_files} files"
        )

    if not all_transactions:
        console.print("[yellow]No transactions found.[/yellow]")
        return 0

    # Process transactions
    with console.status("[bold green]Categorizing transactions..."):
        categorizer.categorize(all_transactions)

    # AI categorization (if enabled)
    ai_stats: dict[str, object] = {}
    use_ai = args.ai or args.ai_validate or args.ai_categorize
    if use_ai:
        ai_stats = run_ai_categorization(args, config, all_transactions, console)

    with console.status("[bold green]Detecting duplicates..."):
        deduplicator.find_duplicates(all_transactions)

    with console.status("[bold green]Calculating balances..."):
        balance_calculator.calculate_balances(all_transactions)

    with console.status("[bold green]Detecting anomalies..."):
        anomaly_detector.detect_anomalies(all_transactions)
        date_gaps = anomaly_detector.get_date_gaps(all_transactions)

    # Generate P&L summary (shared data for both CSV and Excel exporters)
    pl_summary = generate_pl_summary(all_transactions, config)

    # Calculate statistics
    categorized = sum(1 for t in all_transactions if not t.is_uncategorized)
    uncategorized = sum(1 for t in all_transactions if t.is_uncategorized)
    duplicates = sum(1 for t in all_transactions if t.is_duplicate)
    anomalies = sum(1 for t in all_transactions if t.is_anomaly)

    # Generate output (unless dry run)
    if not args.dry_run:
        # Determine output format from extension
        output_ext = args.output.suffix.lower()
        is_csv_output = output_ext == ".csv"

        with create_progress() as progress:
            if is_csv_output:
                # CSV is primary output
                task = progress.add_task("Writing CSV files...", total=1)
                csv_exporter = CSVExporter(config)
                csv_exporter.export(args.output, all_transactions, date_gaps, pl_summary)
                progress.update(task, advance=1)

                # Also write Excel if --xlsx flag is provided
                if args.xlsx:
                    task = progress.add_task("Writing Excel output...", total=1)
                    excel_writer = ExcelWriter(config)
                    xlsx_path = args.output.with_suffix(".xlsx")
                    excel_writer.write(xlsx_path, all_transactions, date_gaps, pl_summary)
                    progress.update(task, advance=1)
            else:
                # Excel is primary output (legacy behavior for .xlsx extension)
                task = progress.add_task("Writing Excel output...", total=1)
                excel_writer = ExcelWriter(config)
                excel_writer.write(args.output, all_transactions, date_gaps, pl_summary)
                progress.update(task, advance=1)

                # Also write CSV if --csv flag is provided
                if args.csv:
                    task = progress.add_task("Writing CSV files...", total=1)
                    csv_exporter = CSVExporter(config)
                    csv_exporter.export(args.output, all_transactions, date_gaps, pl_summary)
                    progress.update(task, advance=1)

        if is_csv_output:
            console.print(f"\n[green]CSV files written to {args.output.parent}[/green]")
            if args.xlsx:
                xlsx_out = args.output.with_suffix(".xlsx")
                console.print(f"[green]Excel file written to {xlsx_out}[/green]")
        else:
            console.print(f"\n[green]Output written to {args.output}[/green]")
            if args.csv:
                console.print(f"[green]CSV files written to {args.output.parent}[/green]")
    else:
        console.print("\n[yellow]Dry run - no output generated[/yellow]")

    # Handle additional exports (these work even in dry-run mode)
    if args.export_uncategorized:
        try:
            validated_path = validate_output_path(args.export_uncategorized)
            csv_exporter = CSVExporter(config)
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            output_path = csv_exporter.export_uncategorized_for_review(
                validated_path.parent,
                all_transactions,
            )
            console.print(f"[green]Uncategorized transactions exported to {output_path}[/green]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return 1

    if args.export_summary:
        try:
            validated_path = validate_output_path(args.export_summary)
            csv_exporter = CSVExporter(config)
            validated_path.parent.mkdir(parents=True, exist_ok=True)
            output_path = csv_exporter.export_categorization_summary(
                validated_path.parent,
                all_transactions,
                ai_stats=ai_stats if ai_stats else None,
            )
            console.print(f"[green]Categorization summary exported to {output_path}[/green]")
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            return 1

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
