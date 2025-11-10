#!/usr/bin/env python3
"""
ABOUTME: Script to complete the TTL cache elimination migration
ABOUTME: Removes all remaining state_cache references and ensures SQL-only persistence
"""
import re
from pathlib import Path

# Main file to modify
MAIN_PY = Path(__file__).parent.parent / "root" / "backend" / "main.py"

def remove_remaining_cache_operations():
    """Remove all remaining state_cache write operations."""
    with open(MAIN_PY, 'r') as f:
        content = f.read()

    # Find and comment out all state_cache writes
    patterns_to_remove = [
        r'state_cache\[.*?\] = \{[^}]*?\}',  # Multi-line dict assignments
        r'state_cache\[.*?\]\[.*?\] = .*',    # Nested assignments
        r'state_cache\.pop\(.*?\)',           # Pop operations
    ]

    for pattern in patterns_to_remove:
        # Find all matches
        matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
        print(f"Found {len(matches)} matches for pattern: {pattern}")

        # Comment them out (going in reverse to preserve indices)
        for match in reversed(matches):
            start, end = match.span()
            original = content[start:end]
            # Add comment marker
            commented = f"# REMOVED: {original}"
            content = content[:start] + commented + content[end:]

    with open(MAIN_PY, 'w') as f:
        f.write(content)

    print(f"✅ Removed remaining cache operations from {MAIN_PY}")

def verify_no_cache_references():
    """Verify no active cache operations remain."""
    with open(MAIN_PY, 'r') as f:
        content = f.read()

    # Look for uncommented state_cache operations
    active_writes = re.findall(r'^(?!#).*state_cache\[', content, re.MULTILINE)
    active_pops = re.findall(r'^(?!#).*state_cache\.pop', content, re.MULTILINE)

    if active_writes or active_pops:
        print(f"⚠️  Found {len(active_writes)} active cache writes")
        print(f"⚠️  Found {len(active_pops)} active cache pops")
        for item in (active_writes + active_pops)[:5]:  # Show first 5
            print(f"   - {item.strip()}")
        return False
    else:
        print("✅ No active cache operations found")
        return True

if __name__ == "__main__":
    print("Starting cache migration cleanup...")
    remove_remaining_cache_operations()
    verify_no_cache_references()
    print("\n✅ Migration script complete!")
    print("Next steps:")
    print("  1. Review the changes in main.py")
    print("  2. Test the application")
    print("  3. Update frontend to use project_id instead of job_id")
