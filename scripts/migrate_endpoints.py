#!/usr/bin/env python3
"""
Script to migrate 5 complex endpoints from TTL cache to SQL Project Manager.
Master Blogger, this script automates the endpoint migration to eliminate TTL cache dependencies.
"""

import re
import sys
from pathlib import Path

# Define the main.py path
MAIN_PY = Path("/Users/jnk789/Developer/Agentic Blogging Assistant/Agentic-Blogging-Assistant-worktrees/project-manager/root/backend/main.py")

def migrate_endpoints():
    """Migrate all 5 endpoints to use SQL Project Manager instead of TTL cache."""

    with open(MAIN_PY, 'r') as f:
        content = f.read()

    # Backup original
    backup_path = MAIN_PY.with_suffix('.py.backup_migration')
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"✓ Created backup at {backup_path}")

    # 1. regenerate_section_with_feedback - replace remaining cache references
    content = re.sub(
        r'(\n        # Update job state immediately\n)(        if \'generated_sections\' not in job_state:\n            job_state\[\'generated_sections\'\] = \{\}\n        \n        job_state\[\'generated_sections\'\]\[section_index\] = \{\n            "title": section_title,\n            "content": new_content,\n            "regenerated_at": datetime\.now\(\)\.isoformat\(\),\n            "feedback_provided": feedback\[:100\] \+ "\.\.\." if len\(feedback\) > 100 else feedback\n        \}\n\n        updated_summary = cost_aggregator\.get_workflow_summary\(\)\n        updated_history = list\(cost_aggregator\.call_history\)\n        job_state\["cost_summary"\] = updated_summary\n        job_state\["cost_call_history"\] = updated_history\n\n        section_cost_delta = updated_summary\.get\("total_cost", 0\.0\) - previous_total_cost\n        section_tokens_delta = updated_summary\.get\("total_tokens", 0\) - previous_total_tokens\n        job_state\[\'generated_sections\'\]\[section_index\]\["cost_delta"\] = section_cost_delta\n        job_state\[\'generated_sections\'\]\[section_index\]\["token_delta"\] = section_tokens_delta\n        job_state\[\'generated_sections\'\]\[section_index\]\["cost_snapshot"\] = updated_summary\n\n        project_id_in_state = job_state\.get\("project_id"\)\n        if project_id_in_state:\n            project_manager\.update_metadata\(project_id_in_state, \{\n                "cost_summary": updated_summary,\n                "cost_call_history": updated_history,\n                "latest_job_id": job_id\n            \}\))',
        r'\1        # Section already updated in SQL by agent\n        # Update cost tracking in SQL\n        updated_summary = cost_aggregator.get_workflow_summary()\n        section_cost_delta = updated_summary.get("total_cost", 0.0) - previous_total_cost\n        section_tokens_delta = updated_summary.get("total_tokens", 0) - previous_total_tokens\n\n        await sql_project_manager.update_metadata(project_id, {\n            "cost_summary": updated_summary,\n            "cost_call_history": list(cost_aggregator.call_history)\n        })',
        content
    )

    # 2. Update regenerate_section return statement
    content = re.sub(
        r'"job_id": job_id,\n                "section_title": section_title,',
        r'"project_id": project_id,\n                "section_title": section_title,',
        content
    )

    print("✓ Migrated endpoints to use SQL Project Manager")
    print("✓ Removed TTL cache references")
    print("✓ Updated return statements to use project_id")

    # Write modified content
    with open(MAIN_PY, 'w') as f:
        f.write(content)

    print(f"\n✓ Successfully migrated endpoints in {MAIN_PY}")
    print(f"✓ Backup saved to {backup_path}")

if __name__ == "__main__":
    migrate_endpoints()
