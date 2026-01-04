"""
Test the document context building for AI agent
"""
import logging
from io import BytesIO

from src.tools.document_scanner import DocumentScanner

# Mock logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _build_document_context(document_data):
    """
    Test version of _build_document_context from agent_service.py
    """
    if not document_data:
        return ""

    # Ensure document_data is a list
    if not isinstance(document_data, list):
        logger.warning(f"document_data should be a list, got {type(document_data)}")
        return ""

    context_parts = ["\n\n=== UPLOADED DOCUMENTS ==="]

    for idx, doc in enumerate(document_data, 1):
        # Skip if not a dictionary
        if not isinstance(doc, dict):
            logger.warning(f"Skipping non-dict document: {type(doc)}")
            continue
        
        filename = doc.get("filename", "Unknown")
        content = doc.get("content", "")
        file_type = doc.get("file_type", "unknown")
        truncated = doc.get("truncated", False)
        full_length = doc.get("full_length", len(content))
        
        # Build document header
        context_parts.append(f"\n--- Document {idx}: {filename} ---")
        context_parts.append(f"Type: {file_type.upper()}")
        
        # Add metadata if available
        metadata = doc.get("metadata", {})
        if metadata:
            metadata_str = ", ".join([f"{k}: {v}" for k, v in metadata.items() if k not in ['characters']])
            if metadata_str:
                context_parts.append(f"Info: {metadata_str}")
        
        # Show truncation info
        if truncated:
            context_parts.append(f"Size: {full_length} chars (showing first 1000)")
        
        # Add content with clear delimiter
        context_parts.append(f"\nContent:\n{content[:1000]}")
        if truncated:
            context_parts.append("[... content truncated ...]")
    
    context_parts.append("\n=== END DOCUMENTS ===\n")

    return "\n".join(context_parts)


def test_context_building():
    """Test the complete document context building"""
    csv_content = """date,location,pm25,pm10,aqi
2025-12-23,New York,15.5,25.3,58
2025-12-24,New York,18.2,28.1,65
2025-12-25,New York,12.1,22.5,50
"""
    
    scanner = DocumentScanner()
    scan_result = scanner.scan_document_from_bytes(
        BytesIO(csv_content.encode('utf-8')), 
        'air-quality-data.csv'
    )
    
    # Wrap in list as done in routes.py
    document_data = [scan_result]
    
    # Build context as done in agent_service.py
    context = _build_document_context(document_data)
    
    print("=== Generated Context for AI ===")
    print(context)
    print("\n=== Context Stats ===")
    print(f"Length: {len(context)} characters")
    print(f"Success: {'UPLOADED DOCUMENTS' in context and 'END DOCUMENTS' in context}")
    
    return 'UPLOADED DOCUMENTS' in context

if __name__ == "__main__":
    success = test_context_building()
    if success:
        print("\n✅ Context building test passed!")
    else:
        print("\n❌ Context building test failed!")
