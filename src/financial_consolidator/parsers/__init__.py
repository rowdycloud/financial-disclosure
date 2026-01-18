"""File parsers for various financial statement formats."""

from financial_consolidator.parsers.base import BaseParser, ParseError
from financial_consolidator.parsers.csv_parser import CSVParser
from financial_consolidator.parsers.ofx_parser import OFXParser
from financial_consolidator.parsers.excel_parser import ExcelParser
from financial_consolidator.parsers.pdf_parser import PDFParser
from financial_consolidator.parsers.detector import (
    FileDetector,
    get_detector,
    detect_parser,
    parse_file,
    discover_files,
)

__all__ = [
    "BaseParser",
    "ParseError",
    "CSVParser",
    "OFXParser",
    "ExcelParser",
    "PDFParser",
    "FileDetector",
    "get_detector",
    "detect_parser",
    "parse_file",
    "discover_files",
]
