#!/usr/bin/env python3
"""
Test script to validate export functionality (CSV, XLSX, JSON) for legal events.
Tests the export generation logic directly without requiring full Docker stack.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from io import StringIO, BytesIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from core.constants import FIVE_COLUMN_HEADERS
from core.interfaces import EventRecord

# Sample test data
SAMPLE_EVENTS = [
    EventRecord(
        number=1,
        date="2024-01-15",
        event_particulars="On January 15, 2024, the plaintiff filed a motion to dismiss pursuant to Rule 12(b)(6) of the Federal Rules of Civil Procedure.",
        citation="Fed. R. Civ. P. 12(b)(6)",
        document_reference="motion_to_dismiss.pdf",
        attributes={}
    ),
    EventRecord(
        number=2,
        date="2024-02-10",
        event_particulars="Court hearing scheduled for discovery disputes on February 10, 2024 at 2:00 PM pursuant to Local Rule 37.1.",
        citation="Local Rule 37.1",
        document_reference="hearing_notice.pdf",
        attributes={}
    ),
    EventRecord(
        number=3,
        date="2024-03-05",
        event_particulars="Settlement conference ordered by the court for March 5, 2024. Both parties must attend with settlement authority.",
        citation="",
        document_reference="settlement_order.pdf",
        attributes={}
    )
]


def test_csv_export():
    """Test CSV export generation"""
    print(f"\n{'='*80}")
    print(f"Testing: CSV Export")
    print(f"{'='*80}")
    
    try:
        import csv
        
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=FIVE_COLUMN_HEADERS)
        writer.writeheader()
        
        for event in SAMPLE_EVENTS:
            # Convert EventRecord to dict matching five-column format
            row_dict = {
                "No": event.number,
                "Date": event.date,
                "Event Particulars": event.event_particulars,
                "Citation": event.citation,
                "Document Reference": event.document_reference
            }
            writer.writerow(row_dict)
        
        content = output.getvalue()
        
        # Validate
        if not content:
            print(f"❌ FAIL: CSV generation produced empty content")
            return {"status": "failed", "reason": "Empty CSV"}
        
        if "No,Date,Event Particulars,Citation,Document Reference" not in content:
            print(f"❌ FAIL: CSV header missing or incorrect")
            return {"status": "failed", "reason": "Invalid header"}
        
        lines = content.strip().split('\n')
        if len(lines) != 4:  # Header + 3 events
            print(f"❌ FAIL: Expected 4 lines, got {len(lines)}")
            return {"status": "failed", "reason": f"Invalid line count: {len(lines)}"}
        
        # Success
        print(f"✅ SUCCESS: CSV export generated")
        print(f"📊 Stats:")
        print(f"   - Size: {len(content)} bytes")
        print(f"   - Lines: {len(lines)} (1 header + 3 events)")
        print(f"   - Sample line: {lines[1][:80]}...")
        
        return {
            "status": "success",
            "size_bytes": len(content),
            "lines": len(lines),
            "format": "text/csv"
        }
        
    except Exception as e:
        print(f"❌ FAIL: Exception occurred - {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "reason": f"Exception: {str(e)}"}


def test_xlsx_export():
    """Test Excel/XLSX export generation"""
    print(f"\n{'='*80}")
    print(f"Testing: Excel (XLSX) Export")
    print(f"{'='*80}")
    
    try:
        import pandas as pd
        
        # Convert EventRecords to dict format
        data = []
        for event in SAMPLE_EVENTS:
            data.append({
                "No": event.number,
                "Date": event.date,
                "Event Particulars": event.event_particulars,
                "Citation": event.citation,
                "Document Reference": event.document_reference
            })
        
        df = pd.DataFrame(data)
        
        # Validate DataFrame
        if df.empty:
            print(f"❌ FAIL: DataFrame is empty")
            return {"status": "failed", "reason": "Empty DataFrame"}
        
        if len(df) != 3:
            print(f"❌ FAIL: Expected 3 rows, got {len(df)}")
            return {"status": "failed", "reason": f"Invalid row count: {len(df)}"}
        
        # Generate Excel file
        output = BytesIO()
        df.to_excel(output, index=False, sheet_name="Legal Events", engine='openpyxl')
        content_bytes = output.getvalue()
        
        if not content_bytes:
            print(f"❌ FAIL: Excel generation produced empty content")
            return {"status": "failed", "reason": "Empty XLSX"}
        
        # Success
        print(f"✅ SUCCESS: Excel export generated")
        print(f"📊 Stats:")
        print(f"   - Size: {len(content_bytes):,} bytes")
        print(f"   - Rows: {len(df)}")
        print(f"   - Columns: {list(df.columns)}")
        
        return {
            "status": "success",
            "size_bytes": len(content_bytes),
            "rows": len(df),
            "format": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        
    except Exception as e:
        print(f"❌ FAIL: Exception occurred - {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "reason": f"Exception: {str(e)}"}


def test_json_export():
    """Test JSON export generation"""
    print(f"\n{'='*80}")
    print(f"Testing: JSON Export")
    print(f"{'='*80}")
    
    try:
        # Convert EventRecords to dict format
        data = []
        for event in SAMPLE_EVENTS:
            data.append({
                "No": event.number,
                "Date": event.date,
                "Event Particulars": event.event_particulars,
                "Citation": event.citation,
                "Document Reference": event.document_reference
            })
        
        # Generate JSON
        content = json.dumps(data, indent=2)
        
        if not content:
            print(f"❌ FAIL: JSON generation produced empty content")
            return {"status": "failed", "reason": "Empty JSON"}
        
        # Validate JSON is parseable
        try:
            parsed = json.loads(content)
            if len(parsed) != 3:
                print(f"❌ FAIL: Expected 3 events, got {len(parsed)}")
                return {"status": "failed", "reason": f"Invalid event count: {len(parsed)}"}
        except json.JSONDecodeError as e:
            print(f"❌ FAIL: Invalid JSON produced: {e}")
            return {"status": "failed", "reason": "Invalid JSON"}
        
        # Success
        print(f"✅ SUCCESS: JSON export generated")
        print(f"📊 Stats:")
        print(f"   - Size: {len(content)} bytes")
        print(f"   - Events: {len(parsed)}")
        print(f"   - Sample event: {list(parsed[0].keys())}")
        
        return {
            "status": "success",
            "size_bytes": len(content),
            "events": len(parsed),
            "format": "application/json"
        }
        
    except Exception as e:
        print(f"❌ FAIL: Exception occurred - {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "reason": f"Exception: {str(e)}"}


def main():
    """Run export functionality tests"""
    print(f"╔{'='*78}╗")
    print(f"║{'Export Functionality Test':^78}║")
    print(f"╚{'='*78}╝")
    print(f"\n📅 Test Time: {datetime.utcnow().isoformat()}Z")
    print(f"📄 Sample Events: {len(SAMPLE_EVENTS)} test events")
    
    # Run tests
    results = {}
    
    results["csv"] = test_csv_export()
    results["xlsx"] = test_xlsx_export()
    results["json"] = test_json_export()
    
    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}\n")
    
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    failed_count = sum(1 for r in results.values() if r["status"] == "failed")
    
    print(f"📊 Results:")
    print(f"   ✅ Success: {success_count}/3")
    print(f"   ❌ Failed:  {failed_count}/3")
    
    print(f"\n📋 Detailed Results:\n")
    for fmt, result in results.items():
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"   {status_icon} {fmt.upper():6} - {result['status'].upper()}")
        if result["status"] == "success":
            print(f"      └─ Size: {result['size_bytes']:,} bytes")
        else:
            print(f"      └─ Reason: {result.get('reason', 'Unknown')}")
    
    print(f"\n{'='*80}\n")
    
    # Return exit code
    return 0 if success_count == 3 else 1


if __name__ == "__main__":
    sys.exit(main())
