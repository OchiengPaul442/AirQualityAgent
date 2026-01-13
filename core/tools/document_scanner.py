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

from shared.config.settings import get_settings
from shared.utils.provider_errors import aeris_unavailable_message

logger = logging.getLogger(__name__)


class DocumentScanner:
    """Scan and extract text/data from documents in memory (PDF, CSV, Excel)"""

    def __init__(self):
        self.settings = get_settings()
        # Track if document was already processed (audit requirement)
        self._document_processed = False
        self._processed_content_cache = None

    def verify_document_in_context(self, context: str) -> tuple[bool, str | None]:
        """
        Verify if document content is already in context.
        
        Per audit requirement: "Check context for <document_content> tags"
        
        Args:
            context: Current conversation context or message history
            
        Returns:
            Tuple of (found: bool, content: str | None)
            - If found: (True, extracted_content)
            - If not found: (False, None)
        """
        if not context:
            return (False, None)
        
        # Check for document content markers
        if "<document_content>" in context and "</document_content>" in context:
            # Extract content between tags
            start = context.find("<document_content>") + len("<document_content>")
            end = context.find("</document_content>")
            content = context[start:end].strip()
            logger.info("Document content found in context - using existing data")
            return (True, content)
        
        # Check for markdown code blocks with document metadata
        if "```" in context and any(marker in context for marker in ["CSV File:", "Excel File:", "PDF File:"]):
            logger.info("Document content detected in markdown - using existing data")
            return (True, None)  # Content is in markdown, not extracted
        
        return (False, None)

    def smart_document_handling(
        self, 
        file_bytes: BytesIO | bytes, 
        filename: str,
        interactive: bool = True
    ) -> dict[str, Any]:
        """
        Intelligent document handling with user disambiguation for large files.
        
        Per audit requirement: "Smart handling for large files with chunking strategy"
        
        Args:
            file_bytes: Document bytes
            filename: Original filename
            interactive: Whether to prompt user for disambiguation (default True)
            
        Returns:
            Dictionary with content or disambiguation request
        """
        file_lower = filename.lower()
        
        # Pre-scan file size and structure
        if isinstance(file_bytes, bytes):
            file_size_mb = len(file_bytes) / (1024 * 1024)
            file_bytes_io = BytesIO(file_bytes)
        else:
            file_bytes.seek(0, 2)  # Seek to end
            file_size_mb = file_bytes.tell() / (1024 * 1024)
            file_bytes.seek(0)  # Seek back to start
            file_bytes_io = file_bytes
        
        # Handle PDF files
        if file_lower.endswith(".pdf"):
            try:
                import PyPDF2
                file_bytes_io.seek(0)
                reader = PyPDF2.PdfReader(file_bytes_io)
                page_count = len(reader.pages)
                
                if page_count > 100 and interactive:
                    # Request user disambiguation (audit requirement)
                    return {
                        "needs_disambiguation": True,
                        "filename": filename,
                        "file_type": "pdf",
                        "page_count": page_count,
                        "size_mb": round(file_size_mb, 2),
                        "message": (
                            f"Large PDF detected: {page_count} pages ({file_size_mb:.2f} MB). "
                            f"To optimize processing, please specify:\n"
                            f"- Which pages to prioritize? (e.g., '1-10', 'all', 'summary sections')\n"
                            f"- What information are you looking for? (e.g., 'air quality data', 'statistics')"
                        ),
                        "suggested_actions": [
                            "Process first 50 pages",
                            "Process last 50 pages",
                            "Process all pages (may take longer)",
                            "Specify custom page range"
                        ]
                    }
                
                logger.info(f"Processing PDF: {filename} - {page_count} pages ({file_size_mb:.2f} MB)")
            except Exception as e:
                logger.warning(f"Error pre-scanning PDF: {e}")
        
        # Handle Excel files
        elif file_lower.endswith((".xlsx", ".xls")):
            try:
                import pandas as pd
                file_bytes_io.seek(0)
                excel_file = pd.ExcelFile(file_bytes_io)
                sheet_names = excel_file.sheet_names
                
                if len(sheet_names) > 3 and interactive:
                    # Request user disambiguation (audit requirement)
                    return {
                        "needs_disambiguation": True,
                        "filename": filename,
                        "file_type": "excel",
                        "sheet_count": len(sheet_names),
                        "sheet_names": sheet_names,
                        "size_mb": round(file_size_mb, 2),
                        "message": (
                            f"Multi-sheet Excel file detected: {len(sheet_names)} sheets ({file_size_mb:.2f} MB).\n"
                            f"Sheets: {', '.join(sheet_names)}\n\n"
                            f"To optimize processing, please specify:\n"
                            f"- Which sheet(s) contain air quality data?\n"
                            f"- What specific data should I focus on?"
                        ),
                        "suggested_actions": [
                            f"Process sheet: {sheet_names[0]}",
                            "Process all sheets",
                            "Specify sheet name(s)"
                        ]
                    }
                
                logger.info(f"Processing Excel: {filename} - {len(sheet_names)} sheets ({file_size_mb:.2f} MB)")
            except Exception as e:
                logger.warning(f"Error pre-scanning Excel: {e}")
        
        # Handle CSV files
        elif file_lower.endswith(".csv"):
            try:
                import pandas as pd
                file_bytes_io.seek(0)
                # Quick scan to count rows
                df_shape = pd.read_csv(file_bytes_io, nrows=1)
                file_bytes_io.seek(0)
                # Count total rows efficiently
                total_rows = sum(1 for _ in file_bytes_io) - 1  # Subtract header
                file_bytes_io.seek(0)
                
                if total_rows > 1000 and interactive:
                    # Request user disambiguation (audit requirement)
                    return {
                        "needs_disambiguation": True,
                        "filename": filename,
                        "file_type": "csv",
                        "row_count": total_rows,
                        "column_count": len(df_shape.columns),
                        "columns": df_shape.columns.tolist(),
                        "size_mb": round(file_size_mb, 2),
                        "message": (
                            f"Large CSV file detected: {total_rows:,} rows ({file_size_mb:.2f} MB).\n"
                            f"Columns: {', '.join(df_shape.columns.tolist())}\n\n"
                            f"To optimize processing, please specify:\n"
                            f"- What data range should I focus on? (e.g., 'recent data', 'specific date range')\n"
                            f"- Which columns are most important?"
                        ),
                        "suggested_actions": [
                            "Process first 500 rows",
                            "Process last 500 rows",
                            "Process all data (may take longer)",
                            "Specify date range or filter"
                        ]
                    }
                
                logger.info(f"Processing CSV: {filename} - {total_rows:,} rows ({file_size_mb:.2f} MB)")
            except Exception as e:
                logger.warning(f"Error pre-scanning CSV: {e}")
        
        # If no disambiguation needed or not interactive, proceed with normal scanning
        logger.info(f"Processing {filename} - {file_size_mb:.2f} MB")
        return self.scan_document_from_bytes(file_bytes_io, filename)

    def scan_document_from_bytes(
        self, file_bytes: BytesIO | bytes, filename: str, use_smart_handling: bool = True
    ) -> dict[str, Any]:
        """
        Read and extract text/data from document bytes (in-memory processing)

        Supported formats: PDF, CSV, Excel (.xlsx, .xls)

        Args:
            file_bytes: BytesIO object or bytes containing file data
            filename: Original filename with extension
            use_smart_handling: Enable smart handling for large files (default True)

        Returns:
            Dictionary with content, file type, metadata, or error
        """
        try:
            # Convert bytes to BytesIO if needed
            if isinstance(file_bytes, bytes):
                file_bytes = BytesIO(file_bytes)

            # Use smart handling if enabled (audit requirement)
            if use_smart_handling:
                return self.smart_document_handling(file_bytes, filename, interactive=True)

            file_lower = filename.lower()

            # Log processing details (audit requirement)
            file_bytes.seek(0, 2)  # Seek to end
            file_size = file_bytes.tell()
            file_bytes.seek(0)  # Seek back
            logger.info(
                f"Document processing started - "
                f"Filename: {filename}, "
                f"Size: {file_size / 1024:.2f} KB, "
                f"Type: {os.path.splitext(filename)[1]}"
            )

            # Handle PDF files
            if file_lower.endswith(".pdf"):
                result = self._scan_pdf_bytes(file_bytes, filename)
                self._log_processing_result(result)
                return result

            # Handle CSV files
            elif file_lower.endswith(".csv"):
                result = self._scan_csv_bytes(file_bytes, filename)
                self._log_processing_result(result)
                return result

            # Handle Excel files
            elif file_lower.endswith((".xlsx", ".xls")):
                result = self._scan_excel_bytes(file_bytes, filename)
                self._log_processing_result(result)
                return result

            else:
                return {
                    "error": "Unsupported file type. Supported: PDF, CSV, Excel (.xlsx, .xls)",
                    "filename": filename,
                    "file_extension": os.path.splitext(filename)[1],
                }

        except Exception as e:
            logger.error(f"Error scanning document {filename}: {e}", exc_info=True)
            return {"error": "Failed to process document.", "message": aeris_unavailable_message(), "filename": filename}

    def _log_processing_result(self, result: dict[str, Any]):
        """
        Log document processing results.
        
        Per audit requirement: "Log processing details: filename, type, size"
        """
        if result.get("success"):
            logger.info(
                f"Document processed successfully - "
                f"Filename: {result.get('filename')}, "
                f"Type: {result.get('file_type')}, "
                f"Content length: {result.get('full_length', 0)} chars, "
                f"Truncated: {result.get('truncated', False)}"
            )
            
            # Additional metadata logging
            metadata = result.get("metadata", {})
            if result.get("file_type") == "pdf":
                logger.info(f"PDF details - Pages: {metadata.get('pages')}")
            elif result.get("file_type") == "csv":
                logger.info(f"CSV details - Rows: {metadata.get('rows')}, Columns: {metadata.get('columns')}")
            elif result.get("file_type") == "excel":
                logger.info(
                    f"Excel details - Sheets: {metadata.get('sheet_count')}, "
                    f"Total rows: {metadata.get('total_rows')}"
                )
        else:
            logger.warning(
                f"Document processing failed - "
                f"Filename: {result.get('filename')}, "
                f"Error: {result.get('error')}"
            )

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
            logger.error(f"Error reading file {file_path}: {e}", exc_info=True)
            return {
                "error": "Failed to process document.",
                "message": aeris_unavailable_message(),
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
            logger.error(f"Error reading PDF {filename}: {e}", exc_info=True)
            return {"error": "Failed to process document.", "message": aeris_unavailable_message(), "filename": filename}

    def _scan_csv_bytes(self, file_bytes: BytesIO | bytes, filename: str) -> dict[str, Any]:
        """Extract data from CSV file bytes with multiple encoding support"""
        try:
            import gc  # Garbage collection for memory management

            import pandas as pd

            # Ensure file_bytes is BytesIO
            if isinstance(file_bytes, bytes):
                file_bytes = BytesIO(file_bytes)

            # Try multiple encodings to handle various file formats
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            df = None
            last_error = None
            successful_encoding = None
            
            for encoding in encodings:
                try:
                    file_bytes.seek(0)  # Reset position
                    df = pd.read_csv(file_bytes, encoding=encoding, on_bad_lines='skip')
                    successful_encoding = encoding
                    logger.info(f"Successfully read CSV with {encoding} encoding")
                    break
                except (UnicodeDecodeError, pd.errors.ParserError) as e:
                    last_error = e
                    continue
            
            if df is None:
                raise last_error or ValueError("Could not read CSV with any encoding")

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
                "content": content[
                    : self.settings.DOCUMENT_MAX_LENGTH_CSV
                ],  # Configurable limit for better large file handling
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
            logger.error(f"Error reading CSV {filename}: {e}", exc_info=True)
            return {"error": "Failed to process document.", "message": aeris_unavailable_message(), "filename": filename}

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

                    content_parts.append(
                        f"\n--- Sheet {i+1}/{len(sheet_names)}: {sheet_name} ---\n"
                    )
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
                        elif hasattr(obj, "isoformat"):  # datetime-like objects
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
                "content": content[
                    : self.settings.DOCUMENT_MAX_LENGTH_EXCEL
                ],  # Configurable limit for comprehensive multi-sheet analysis
                "full_length": len(content),
                "truncated": len(content) > self.settings.DOCUMENT_MAX_LENGTH_EXCEL,
                "metadata": {
                    "sheet_count": len(sheet_names),
                    "sheet_names": sheet_names,
                    "sheets_data": all_sheets_data,
                    "total_rows": sum(
                        s.get("rows", 0)
                        for s in all_sheets_data.values()
                        if isinstance(s, dict) and "rows" in s
                    ),
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
            logger.error(f"Error reading Excel file {filename}: {e}", exc_info=True)
            return {"error": "Failed to process document.", "message": aeris_unavailable_message(), "filename": filename}
