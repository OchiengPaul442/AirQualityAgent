"""
Document Scanner Tool

Simple document reading utility that supports text files and PDFs
"""

import os
from typing import Any, Dict


class DocumentScanner:
    """Scan and extract text from documents"""

    def scan_document(self, file_path: str) -> Dict[str, Any]:
        """
        Read and extract text from a document file
        
        Args:
            file_path: Path to the file to scan
            
        Returns:
            Dictionary with content or error
        """
        try:
            if not os.path.exists(file_path):
                return {
                    "error": f"File not found at {file_path}",
                    "file_path": file_path
                }

            # Handle PDF files
            if file_path.lower().endswith(".pdf"):
                try:
                    import PyPDF2
                    
                    text = ""
                    with open(file_path, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                    
                    return {
                        "file_path": file_path,
                        "file_type": "pdf",
                        "content": text[:4000],  # Truncate for safety
                        "full_length": len(text),
                        "truncated": len(text) > 4000
                    }
                except ImportError:
                    return {
                        "error": "PyPDF2 not installed. Run: pip install PyPDF2",
                        "file_path": file_path
                    }

            # Handle text files
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                return {
                    "file_path": file_path,
                    "file_type": "text",
                    "content": content[:2000],  # Truncate for safety
                    "full_length": len(content),
                    "truncated": len(content) > 2000
                }
            except Exception as e:
                return {
                    "error": f"Error reading file: {str(e)}",
                    "file_path": file_path
                }

        except Exception as e:
            return {
                "error": f"Error scanning document: {str(e)}",
                "file_path": file_path
            }
