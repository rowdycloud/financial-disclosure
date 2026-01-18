"""Abstract base class for file parsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from financial_consolidator.models.transaction import RawTransaction
from financial_consolidator.utils.logging_config import get_logger

logger = get_logger(__name__)


class ParseError(Exception):
    """Exception raised when parsing fails."""

    def __init__(self, message: str, file_path: Optional[Path] = None):
        """Initialize ParseError.

        Args:
            message: Error message.
            file_path: Optional path to the file that failed to parse.
        """
        self.file_path = file_path
        super().__init__(message)


class BaseParser(ABC):
    """Abstract base class for all file parsers.

    Subclasses must implement:
    - can_parse(): Check if this parser can handle a file
    - parse(): Parse a file and return raw transactions
    - supported_extensions: List of file extensions this parser handles
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of file extensions this parser supports.

        Returns:
            List of extensions like ['.csv', '.tsv'].
        """
        pass

    @property
    def name(self) -> str:
        """Return parser name for logging.

        Returns:
            Parser name string.
        """
        return self.__class__.__name__

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        This method should check file extension and optionally
        peek at file content to verify format.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if this parser can handle the file.
        """
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> list[RawTransaction]:
        """Parse a file and return raw transactions.

        Args:
            file_path: Path to the file to parse.

        Returns:
            List of RawTransaction objects.

        Raises:
            ParseError: If parsing fails.
            FileNotFoundError: If file doesn't exist.
        """
        pass

    def detect_institution(self, file_path: Path) -> Optional[str]:
        """Attempt to detect the financial institution from file content.

        Override in subclasses to provide institution-specific detection.

        Args:
            file_path: Path to the file.

        Returns:
            Institution name if detected, None otherwise.
        """
        return None

    def _check_extension(self, file_path: Path) -> bool:
        """Check if file extension matches supported extensions.

        Args:
            file_path: Path to check.

        Returns:
            True if extension is supported.
        """
        return file_path.suffix.lower() in self.supported_extensions

    def _read_first_lines(self, file_path: Path, n_lines: int = 10) -> list[str]:
        """Read first N lines of a text file.

        Useful for format detection without reading entire file.

        Args:
            file_path: Path to the file.
            n_lines: Number of lines to read.

        Returns:
            List of first N lines.
        """
        lines = []
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= n_lines:
                        break
                    lines.append(line.rstrip("\n\r"))
        except Exception as e:
            logger.warning(f"Could not read first lines of {file_path}: {e}")
        return lines
