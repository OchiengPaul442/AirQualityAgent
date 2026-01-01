"""
Document Scanner Tool

Enhanced document reading utility with in-memory processing
Supports PDF, CSV, and Excel files without disk storage
Cost-effective and memory-efficient approach
"""

import os
from io import BytesIO
from typing import Any, Dict, Union


class DocumentScanner:
    """Scan and extract text/data from documents in memory (PDF, CSV, Excel)"""

    def scan_document_from_bytes(
        self, file_bytes: Union[BytesIO, bytes], filename: str
    ) -> Dict[str, Any]:
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
                    "error": f"Unsupported file type. Supported: PDF, CSV, Excel (.xlsx, .xls)",
                    "filename": filename,
                    "file_extension": os.path.splitext(filename)[1],
                }

        except Exception as e:
            return {"error": f"Error scanning document: {str(e)}", "filename": filename}

    def scan_file(self, file_path: str) -> Dict[str, Any]:
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

    def _scan_pdf_bytes(self, file_bytes: BytesIO, filename: str) -> Dict[str, Any]:
        """Extract text from PDF file bytes"""
        try:
            import PyPDF2

            text = ""
            reader = PyPDF2.PdfReader(file_bytes)
            page_count = len(reader.pages)

            for page in reader.pages:
                text += page.extract_text() + "\n"

            # 10KB limit for AI processing
            max_length = 10000

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

    def _scan_csv_bytes(self, file_bytes: BytesIO, filename: str) -> Dict[str, Any]:
        """Extract data from CSV file bytes"""
        try:
            import pandas as pd

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

            # Show first 50 rows
            preview_rows = min(50, len(df))
            content_parts.append(f"First {preview_rows} rows:\n")
            content_parts.append(df.head(preview_rows).to_string(index=False))

            # Add statistics for numeric columns
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                content_parts.append("\n\nNumeric Column Statistics:\n")
                content_parts.append(df[numeric_cols].describe().to_string())

            content = "\n".join(content_parts)

            return {
                "success": True,
                "filename": filename,
                "file_type": "csv",
                "content": content[:10000],  # 10KB limit
                "full_length": len(content),
                "truncated": len(content) > 10000,
                "metadata": summary,
                "preview_data": df.head(10).to_dict(orient="records"),
            }
        except ImportError:
            return {
                "error": "pandas not installed. Required for CSV support.",
                "filename": filename,
                "install_command": "pip install pandas",
            }
        except Exception as e:
            return {"error": f"Error reading CSV: {str(e)}", "filename": filename}

    def _scan_excel_bytes(self, file_bytes: BytesIO, filename: str) -> Dict[str, Any]:
        """Extract data from Excel file bytes"""
        try:
            import pandas as pd

            # Read all sheets from bytes
            excel_file = pd.ExcelFile(file_bytes)
            sheet_names = excel_file.sheet_names

            content_parts = []
            content_parts.append(f"Excel File: {filename}\n")
            content_parts.append(f"Total Sheets: {len(sheet_names)}\n")
            content_parts.append(f"Sheet Names: {', '.join(sheet_names)}\n\n")

            all_sheets_data = {}

            # Process first 5 sheets
            for sheet_name in sheet_names[:5]:
                df = pd.read_excel(file_bytes, sheet_name=sheet_name)

                content_parts.append(f"\n--- Sheet: {sheet_name} ---\n")
                content_parts.append(f"Rows: {len(df)}, Columns: {len(df.columns)}\n")
                content_parts.append(f"Columns: {', '.join(df.columns.tolist())}\n")

                # Show first 20 rows per sheet
                preview_rows = min(20, len(df))
                content_parts.append(f"\nFirst {preview_rows} rows:\n")
                content_parts.append(df.head(preview_rows).to_string(index=False))
                content_parts.append("\n")

                all_sheets_data[sheet_name] = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": df.columns.tolist(),
                    "preview": df.head(10).to_dict(orient="records"),
                }

            content = "\n".join(content_parts)

            return {
                "success": True,
                "filename": filename,
                "file_type": "excel",
                "content": content[:10000],  # 10KB limit
                "full_length": len(content),
                "truncated": len(content) > 10000,
                "metadata": {
                    "sheet_count": len(sheet_names),
                    "sheet_names": sheet_names,
                    "sheets_data": all_sheets_data,
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
