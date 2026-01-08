"""
Document Scanner Tool

Enhanced document reading utility with in-memory processing
Supports PDF, CSV, and Excel files without disk storage
Cost-effective and memory-efficient approach

Enhanced to handle large files with better chunking and ALL Excel sheets
"""

import logging
import os
from io import BytesIO
from typing import Any

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from src.config import get_settings

logger = logging.getLogger(__name__)


class DocumentScanner:
    """Scan and extract text/data from documents in memory (PDF, CSV, Excel)"""

    def __init__(self):
        self.settings = get_settings()

    def scan_document_from_bytes(
        self, file_bytes: BytesIO | bytes, filename: str
    ) -> dict[str, Any]:
        """
        Read and extract text/data from document bytes (in-memory processing)

        Supported formats: PDF, CSV, Excel (.xlsx, .xls)

        Args:
            file_bytes: BytesIO object or bytes containing file data
            filename: Original filename with extension

        Returns:
            Dictionary with content, file type, metadata, or error
        """
        try:
            # Convert bytes to BytesIO if needed
            if isinstance(file_bytes, bytes):
                file_bytes = BytesIO(file_bytes)

            file_lower = filename.lower()

            # Handle PDF files
            if file_lower.endswith(".pdf"):
                return self._scan_pdf_bytes(file_bytes, filename)

            # Handle CSV files
            elif file_lower.endswith(".csv"):
                return self._scan_csv_bytes(file_bytes, filename)

            # Handle Excel files
            elif file_lower.endswith((".xlsx", ".xls")):
                return self._scan_excel_bytes(file_bytes, filename)

            else:
                return {
                    "error": "Unsupported file type. Supported: PDF, CSV, Excel (.xlsx, .xls)",
                    "filename": filename,
                    "file_extension": os.path.splitext(filename)[1],
                }

        except Exception as e:
            return {"error": f"Error scanning document: {str(e)}", "filename": filename}

    def scan_file(self, file_path: str) -> dict[str, Any]:
        """
        Read and extract text/data from a file on disk

        Args:
            file_path: Path to the file to scan

        Returns:
            Dictionary with content, file type, metadata, or error
        """
        try:
            with open(file_path, "rb") as f:
                file_bytes = BytesIO(f.read())
            return self.scan_document_from_bytes(file_bytes, os.path.basename(file_path))
        except FileNotFoundError:
            return {
                "error": f"File not found: {file_path}",
                "filename": os.path.basename(file_path),
            }
        except Exception as e:
            return {
                "error": f"Error reading file: {str(e)}",
                "filename": os.path.basename(file_path),
            }

    def _scan_pdf_bytes(self, file_bytes: BytesIO | bytes, filename: str) -> dict[str, Any]:
        """Extract text from PDF file bytes"""
        try:
            import PyPDF2

            # Ensure file_bytes is BytesIO
            if isinstance(file_bytes, bytes):
                file_bytes = BytesIO(file_bytes)

            text = ""
            reader = PyPDF2.PdfReader(file_bytes)
            page_count = len(reader.pages)

            for page in reader.pages:
                text += page.extract_text() + "\n"

            # Configurable limit for AI processing to handle larger documents
            max_length = self.settings.DOCUMENT_MAX_LENGTH_PDF

            return {
                "success": True,
                "filename": filename,
                "file_type": "pdf",
                "content": text[:max_length],
                "full_length": len(text),
                "truncated": len(text) > max_length,
                "page_count": page_count,
                "metadata": {"pages": page_count, "characters": len(text)},
            }
        except ImportError:
            return {
                "error": "PyPDF2 not installed. Required for PDF support.",
                "filename": filename,
                "install_command": "pip install PyPDF2",
            }
        except Exception as e:
            return {"error": f"Error reading PDF: {str(e)}", "filename": filename}

    def _scan_csv_bytes(self, file_bytes: BytesIO | bytes, filename: str) -> dict[str, Any]:
        """Extract data from CSV file bytes"""
        try:
            import gc  # Garbage collection for memory management

            import pandas as pd

            # Ensure file_bytes is BytesIO
            if isinstance(file_bytes, bytes):
                file_bytes = BytesIO(file_bytes)

            # Read CSV from bytes
            df = pd.read_csv(file_bytes, encoding="utf-8", on_bad_lines="skip")

            # Get summary statistics
            summary = {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": df.columns.tolist(),
                "dtypes": df.dtypes.astype(str).to_dict(),
            }

            # Convert to readable text format
            content_parts = []
            content_parts.append(f"CSV File: {filename}\n")
            content_parts.append(f"Rows: {summary['rows']}, Columns: {summary['columns']}\n")
            content_parts.append(f"Columns: {', '.join(summary['column_names'])}\n\n")

            # Show configurable number of rows for better data analysis
            preview_rows = min(self.settings.DOCUMENT_PREVIEW_ROWS_CSV, len(df))
            content_parts.append(f"First {preview_rows} rows:\n")
            content_parts.append(df.head(preview_rows).to_string(index=False))

            # Add statistics for numeric columns
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                content_parts.append("\n\nNumeric Column Statistics:\n")
                content_parts.append(df[numeric_cols].describe().to_string())

            content = "\n".join(content_parts)

            # Store preview before cleaning up - convert datetime to strings for JSON serializability
            preview_df = df.head(10).copy()
            for col in preview_df.columns:
                if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
                    preview_df[col] = preview_df[col].astype(str)
            preview_data = preview_df.to_dict(orient="records")

            # Clean up dataframe to free memory
            del df
            del preview_df
            gc.collect()

            return {
                "success": True,
                "filename": filename,
                "file_type": "csv",
                "content": content[:self.settings.DOCUMENT_MAX_LENGTH_CSV],  # Configurable limit for better large file handling
                "full_length": len(content),
                "truncated": len(content) > self.settings.DOCUMENT_MAX_LENGTH_CSV,
                "metadata": summary,
                "preview_data": preview_data,
            }
        except ImportError:
            return {
                "error": "pandas not installed. Required for CSV support.",
                "filename": filename,
                "install_command": "pip install pandas",
            }
        except Exception as e:
            return {"error": f"Error reading CSV: {str(e)}", "filename": filename}

    def _scan_excel_bytes(self, file_bytes: BytesIO | bytes, filename: str) -> dict[str, Any]:
        """Extract data from Excel file bytes - processes ALL sheets"""
        try:
            import gc  # Garbage collection for memory management

            import pandas as pd

            # Ensure file_bytes is BytesIO
            if isinstance(file_bytes, bytes):
                file_bytes = BytesIO(file_bytes)

            # Read all sheets from bytes
            excel_file = pd.ExcelFile(file_bytes)
            sheet_names = excel_file.sheet_names

            content_parts = []
            content_parts.append(f"Excel File: {filename}\n")
            content_parts.append(f"Total Sheets: {len(sheet_names)}\n")
            content_parts.append(f"Sheet Names: {', '.join(sheet_names)}\n\n")

            all_sheets_data = {}

            # Process ALL sheets (not limited to first 5) for comprehensive analysis
            for i, sheet_name in enumerate(sheet_names):
                try:
                    df = pd.read_excel(file_bytes, sheet_name=sheet_name)

                    content_parts.append(f"\n--- Sheet {i+1}/{len(sheet_names)}: {sheet_name} ---\n")
                    content_parts.append(f"Rows: {len(df)}, Columns: {len(df.columns)}\n")
                    content_parts.append(f"Columns: {', '.join(df.columns.tolist())}\n")

                    # Show configurable number of rows per sheet for better data analysis
                    preview_rows = min(self.settings.DOCUMENT_PREVIEW_ROWS_EXCEL, len(df))
                    content_parts.append(f"\nFirst {preview_rows} rows:\n")
                    content_parts.append(df.head(preview_rows).to_string(index=False))

                    # Add numeric statistics for this sheet
                    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                    if numeric_cols:
                        content_parts.append("\n\nNumeric Statistics:\n")
                        content_parts.append(df[numeric_cols].describe().to_string())

                    content_parts.append("\n")

                    # Convert datetime objects to strings for JSON serializability
                    preview_df = df.head(20).copy()
                    for col in preview_df.columns:
                        if pd.api.types.is_datetime64_any_dtype(preview_df[col]):
                            preview_df[col] = preview_df[col].astype(str)
                    
                    # Convert preview dict - handle any remaining datetime objects
                    preview_data = preview_df.to_dict(orient="records")
                    
                    # Recursively convert any datetime objects in the preview data
                    def convert_datetime_to_str(obj):
                        if isinstance(obj, dict):
                            return {k: convert_datetime_to_str(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_datetime_to_str(item) for item in obj]
                        elif pd.isna(obj):
                            return None
                        elif hasattr(obj, 'isoformat'):  # datetime-like objects
                            return obj.isoformat()
                        else:
                            return obj
                    
                    all_sheets_data[sheet_name] = {
                        "rows": len(df),
                        "columns": len(df.columns),
                        "column_names": df.columns.tolist(),
                        "preview": convert_datetime_to_str(preview_data),
                        "dtypes": df.dtypes.astype(str).to_dict(),
                    }

                    # Clean up dataframe to free memory after processing
                    del df
                    gc.collect()

                except Exception as sheet_error:
                    logger.warning(f"Error reading sheet '{sheet_name}': {sheet_error}")
                    content_parts.append(f"\n--- Sheet: {sheet_name} ---\n")
                    content_parts.append(f"Error reading sheet: {str(sheet_error)}\n\n")
                    all_sheets_data[sheet_name] = {"error": str(sheet_error)}

            content = "\n".join(content_parts)

            # Clean up excel file object to free memory
            del excel_file
            gc.collect()

            return {
                "success": True,
                "filename": filename,
                "file_type": "excel",
                "content": content[:self.settings.DOCUMENT_MAX_LENGTH_EXCEL],  # Configurable limit for comprehensive multi-sheet analysis
                "full_length": len(content),
                "truncated": len(content) > self.settings.DOCUMENT_MAX_LENGTH_EXCEL,
                "metadata": {
                    "sheet_count": len(sheet_names),
                    "sheet_names": sheet_names,
                    "sheets_data": all_sheets_data,
                    "total_rows": sum(s.get("rows", 0) for s in all_sheets_data.values() if isinstance(s, dict) and "rows" in s),
                },
            }
        except ImportError as ie:
            missing_lib = "openpyxl" if "openpyxl" in str(ie) else "pandas"
            return {
                "error": f"{missing_lib} not installed. Required for Excel support.",
                "filename": filename,
                "install_command": f"pip install {missing_lib}",
            }
        except Exception as e:
            return {"error": f"Error reading Excel file: {str(e)}", "filename": filename}
