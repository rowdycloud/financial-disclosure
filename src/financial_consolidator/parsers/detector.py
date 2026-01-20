"""File format auto-detection and file discovery module."""

from pathlib import Path

from financial_consolidator.models.transaction import RawTransaction
from financial_consolidator.parsers.base import BaseParser, ParseError
from financial_consolidator.parsers.csv_parser import CSVParser
from financial_consolidator.parsers.excel_parser import ExcelParser
from financial_consolidator.parsers.ofx_parser import OFXParser
from financial_consolidator.parsers.pdf_parser import PDFParser
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class FileDetector:
    """Detects file formats and manages parsers.

    This class provides:
    - File discovery in a directory
    - Format auto-detection
    - Parser selection
    - Batch parsing with error handling
    """

    def __init__(self, strict: bool = False):
        """Initialize with all available parsers.

        Args:
            strict: If True, parsers will raise on row-level parse errors.
                   If False (default), row-level errors are logged and skipped.
        """
        self.strict = strict
        self.parsers: list[BaseParser] = [
            CSVParser(strict=strict),
            OFXParser(),
            ExcelParser(),
            PDFParser(),
        ]

    @property
    def supported_extensions(self) -> list[str]:
        """Get all supported file extensions.

        Returns:
            List of supported extensions.
        """
        extensions: set[str] = set()
        for parser in self.parsers:
            extensions.update(parser.supported_extensions)
        return sorted(extensions)

    def discover_files(self, directory: Path) -> list[Path]:
        """Discover all parseable files in a directory.

        Args:
            directory: Directory to search.

        Returns:
            List of file paths that can potentially be parsed.
        """
        if not directory.exists() or not directory.is_dir():
            logger.warning(f"Directory not found or not a directory: {directory}")
            return []

        files: list[Path] = []
        supported = set(self.supported_extensions)

        # Resolve the target directory to get its real path
        resolved_directory = directory.resolve()

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported:
                # Check for symlink path traversal - ensure resolved path is within target directory
                try:
                    resolved_path = file_path.resolve()
                    # Use relative_to() which raises ValueError if path is not relative
                    # This is safer than string prefix comparison which can be bypassed
                    resolved_path.relative_to(resolved_directory)
                except ValueError:
                    logger.warning(
                        f"Skipping file outside target directory (symlink traversal): {file_path}"
                    )
                    continue
                except OSError as e:
                    logger.warning(f"Skipping file with invalid path: {file_path}: {e}")
                    continue
                files.append(file_path)

        # Sort by name for consistent ordering
        files.sort(key=lambda p: p.name.lower())

        logger.info(f"Discovered {len(files)} potential files in {directory}")
        return files

    def detect_parser(self, file_path: Path) -> BaseParser | None:
        """Detect the appropriate parser for a file.

        Tries each parser in order and returns the first one
        that can handle the file.

        Args:
            file_path: Path to the file.

        Returns:
            Parser that can handle the file, or None.
        """
        for parser in self.parsers:
            try:
                if parser.can_parse(file_path):
                    logger.debug(
                        f"File {file_path.name} matched by {parser.name}"
                    )
                    return parser
            except Exception as e:
                logger.debug(
                    f"Error checking {parser.name} for {file_path.name}: {e}"
                )

        logger.warning(f"No parser found for {file_path.name}")
        return None

    def detect_institution(self, file_path: Path) -> str | None:
        """Detect the financial institution from a file.

        Args:
            file_path: Path to the file.

        Returns:
            Institution name if detected.
        """
        parser = self.detect_parser(file_path)
        if parser:
            try:
                return parser.detect_institution(file_path)
            except Exception as e:
                logger.debug(
                    f"Error detecting institution in {file_path.name}: {e}"
                )
        return None

    def parse_file(self, file_path: Path) -> list[RawTransaction]:
        """Parse a single file using the appropriate parser.

        Args:
            file_path: Path to the file.

        Returns:
            List of RawTransaction objects.

        Raises:
            ParseError: If no parser found or parsing fails.
            PermissionError: If file cannot be read.
            UnicodeDecodeError: If file encoding is invalid.

        Note:
            Other exceptions may propagate from underlying parsers.
        """
        parser = self.detect_parser(file_path)
        if parser is None:
            raise ParseError(f"No parser found for file: {file_path}", file_path)

        return parser.parse(file_path)

    def parse_directory(
        self,
        directory: Path,
        strict: bool = False,
    ) -> tuple[list[RawTransaction], list[str], list[str]]:
        """Parse all files in a directory.

        Args:
            directory: Directory to process.
            strict: If True, raise on first error. If False, skip failed files.

        Returns:
            Tuple of:
            - List of all parsed transactions
            - List of successfully parsed file names
            - List of error messages for failed files
        """
        files = self.discover_files(directory)

        all_transactions: list[RawTransaction] = []
        parsed_files: list[str] = []
        errors: list[str] = []

        for file_path in files:
            try:
                transactions = self.parse_file(file_path)
                all_transactions.extend(transactions)
                parsed_files.append(file_path.name)
                logger.info(
                    f"Parsed {len(transactions)} transactions from {file_path.name}"
                )
            except ParseError as e:
                error_msg = f"{file_path.name}: {e}"
                if strict:
                    raise ParseError(error_msg, file_path)
                errors.append(error_msg)
                logger.warning(f"Skipping {file_path.name}: {e}")
            except FileNotFoundError:
                error_msg = f"{file_path.name}: File not found"
                if strict:
                    raise
                errors.append(error_msg)
                logger.warning(error_msg)
            except Exception as e:
                error_msg = f"{file_path.name}: Unexpected error: {e}"
                if strict:
                    raise ParseError(error_msg, file_path)
                errors.append(error_msg)
                logger.error(error_msg)

        logger.info(
            f"Parsed {len(all_transactions)} total transactions from "
            f"{len(parsed_files)} files ({len(errors)} errors)"
        )

        return all_transactions, parsed_files, errors


# Singleton instance for convenience
_detector: FileDetector | None = None


def get_detector(strict: bool = False) -> FileDetector:
    """Get or create a FileDetector instance.

    Note: The singleton is recreated if strict mode differs from current instance.

    Args:
        strict: If True, parsers will raise on row-level parse errors.

    Returns:
        FileDetector instance.
    """
    global _detector
    if _detector is None or _detector.strict != strict:
        _detector = FileDetector(strict=strict)
    return _detector


def detect_parser(file_path: Path) -> BaseParser | None:
    """Convenience function to detect parser for a file.

    Args:
        file_path: Path to the file.

    Returns:
        Parser that can handle the file, or None.
    """
    return get_detector().detect_parser(file_path)


def parse_file(file_path: Path) -> list[RawTransaction]:
    """Convenience function to parse a single file.

    Args:
        file_path: Path to the file.

    Returns:
        List of RawTransaction objects.

    Raises:
        ParseError: If parsing fails.
    """
    return get_detector().parse_file(file_path)


def discover_files(directory: Path) -> list[Path]:
    """Convenience function to discover files in a directory.

    Args:
        directory: Directory to search.

    Returns:
        List of file paths.
    """
    return get_detector().discover_files(directory)
