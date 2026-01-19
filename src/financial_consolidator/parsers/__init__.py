"""File parsers for various financial statement formats."""

from financial_consolidator.parsers.base import BaseParser, ParseError
from financial_consolidator.parsers.csv_parser import CSVParser
from financial_consolidator.parsers.detector import (
    FileDetector,
    detect_parser,
    discover_files,
    get_detector,
    parse_file,
)
from financial_consolidator.parsers.excel_parser import ExcelParser
from financial_consolidator.parsers.ofx_parser import OFXParser
from financial_consolidator.parsers.pdf_parser import PDFParser

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
