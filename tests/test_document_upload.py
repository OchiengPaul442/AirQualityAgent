"""
Quick test script to verify document scanning functionality
"""
import os
from io import BytesIO

from src.tools.document_scanner import DocumentScanner


def test_csv_scan():
    """Test CSV scanning with sample data"""
    csv_content = """date,location,pm25,pm10,aqi
2025-12-23,New York,15.5,25.3,58
2025-12-24,New York,18.2,28.1,65
2025-12-25,New York,12.1,22.5,50
2025-12-26,New York,20.3,32.8,72
2025-12-27,New York,16.8,26.9,60
"""
    
    scanner = DocumentScanner()
    result = scanner.scan_document_from_bytes(
        BytesIO(csv_content.encode('utf-8')), 
        'test_air_quality.csv'
    )
    
    print("\n=== CSV Scan Result ===")
    print(f"Success: {result.get('success')}")
    print(f"Filename: {result.get('filename')}")
    print(f"File Type: {result.get('file_type')}")
    print(f"Rows: {result.get('metadata', {}).get('rows')}")
    print(f"Columns: {result.get('metadata', {}).get('columns')}")
    print(f"\nContent Preview:\n{result.get('content', '')[:500]}")
    
    # Test wrapping in list (as done in routes.py)
    document_data = [result]
    print(f"\n=== Document Data as List ===")
    print(f"Type: {type(document_data)}")
    print(f"Length: {len(document_data)}")
    print(f"First item type: {type(document_data[0])}")
    
    # Test iteration (as done in agent_service.py)
    for doc in document_data:
        if isinstance(doc, dict):
            print(f"✓ Document is dict: {doc.get('filename')}")
        else:
            print(f"✗ Document is not dict: {type(doc)}")
    
    assert result.get('success', False)

if __name__ == "__main__":
    success = test_csv_scan()
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Tests failed!")
