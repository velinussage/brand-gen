#!/usr/bin/env python3
"""
Migration script for brand-gen run events.
This script:
1. Discovers all *.jsonl files (excluding _index.jsonl) under any runs/ subdirectory in:
   - /Users/twells/Documents/brand-gen/.brand-gen/brands/
   - /Users/twells/Documents/brand-gen/brands/
2. Migrates each file to ensure all events with schema_type == "run_event" have a consistent
   run_id and campaign_id.
3. Automatically backs up each file to <workflow_id>.jsonl.bak before modification.
4. Generates or updates a runs/_index.jsonl file under each runs/ folder mapping
   run_id and campaign_id to summarized execution details.
"""

import sys
import json
import uuid
import shutil
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("migrate_runs")

# Add repository root to system path to ensure brand_gen can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from brand_gen.run_ledger import append_run_event
    logger.info("Successfully verified import of brand_gen.run_ledger.")
except ImportError as e:
    logger.warning(f"Could not import brand_gen.run_ledger directly (expected if running standalone): {e}")

# Deterministic UUID namespace for brand-gen
NAMESPACE_BRAND_GEN = uuid.uuid5(uuid.NAMESPACE_DNS, "brand-gen.dev")


def generate_deterministic_ids(workflow_id: str) -> Tuple[str, str]:
    """
    Generate deterministic, unique UUIDs for run_id and campaign_id based on the workflow_id.
    """
    run_id = str(uuid.uuid5(NAMESPACE_BRAND_GEN, f"run:{workflow_id}"))
    campaign_id = str(uuid.uuid5(NAMESPACE_BRAND_GEN, f"campaign:{workflow_id}"))
    return run_id, campaign_id


def migrate_runs_directory(runs_dir: Path) -> None:
    """
    Scan, migrate, and build index for a single runs/ directory.
    """
    logger.info(f"Scanning runs directory: {runs_dir}")
    
    # 1. Discover all *.jsonl files (excluding _index.jsonl, backups, and hidden files)
    jsonl_files: List[Path] = []
    for file_path in runs_dir.glob("*.jsonl"):
        if file_path.name.startswith("_index.jsonl") or file_path.name.startswith("."):
            continue
        if file_path.is_file():
            jsonl_files.append(file_path)
            
    if not jsonl_files:
        logger.info(f"No run files found in {runs_dir}")
        return

    logger.info(f"Found {len(jsonl_files)} run files to process in {runs_dir}")
    index_entries: List[Dict[str, Any]] = []

    for file_path in sorted(jsonl_files):
        workflow_id = file_path.stem
        
        # Read the file line-by-line
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            continue

        lines = content.splitlines()
        events: List[Dict[str, Any]] = []
        raw_lines: List[Any] = []  # Can hold parsed dicts or original strings if parsing failed
        
        # First pass: parse lines and search for existing run_id/campaign_id
        existing_run_id = None
        existing_campaign_id = None
        
        for line in lines:
            line_str = line.strip()
            if not line_str:
                raw_lines.append(line_str)
                continue
            
            try:
                parsed = json.loads(line_str)
                if isinstance(parsed, dict):
                    raw_lines.append(parsed)
                    if parsed.get("schema_type") == "run_event":
                        events.append(parsed)
                        r_id = parsed.get("run_id")
                        c_id = parsed.get("campaign_id")
                        if r_id and not existing_run_id:
                            existing_run_id = r_id
                        if c_id and not existing_campaign_id:
                            existing_campaign_id = c_id
                else:
                    raw_lines.append(line)
            except json.JSONDecodeError:
                raw_lines.append(line)

        # Generate deterministic IDs if none found
        if not existing_run_id or not existing_campaign_id:
            gen_run_id, gen_campaign_id = generate_deterministic_ids(workflow_id)
            if not existing_run_id:
                existing_run_id = gen_run_id
            if not existing_campaign_id:
                existing_campaign_id = gen_campaign_id

        # Update all run_events in raw_lines and verify if we made any changes
        modified = False
        updated_lines: List[str] = []
        
        for record in raw_lines:
            if isinstance(record, dict):
                if record.get("schema_type") == "run_event":
                    r_id = record.get("run_id")
                    c_id = record.get("campaign_id")
                    if not r_id or r_id != existing_run_id:
                        record["run_id"] = str(existing_run_id)
                        modified = True
                    if not c_id or c_id != existing_campaign_id:
                        record["campaign_id"] = str(existing_campaign_id)
                        modified = True
                
                # Convert back to JSON string
                updated_lines.append(json.dumps(record, default=str))
            else:
                updated_lines.append(record)

        # If modified, write back to file safely
        if modified:
            logger.info(f"Migrating file: {file_path.name}")
            
            # Backup before modification
            backup_path = file_path.with_suffix(".jsonl.bak")
            try:
                shutil.copy2(file_path, backup_path)
                logger.debug(f"Created backup: {backup_path.name}")
            except Exception as e:
                logger.error(f"Failed to create backup of {file_path.name}: {e}")
                # We can still proceed, but let's log the issue

            # Atomic write to temporary file
            tmp_path = file_path.with_suffix(".jsonl.tmp")
            try:
                with tmp_path.open("w", encoding="utf-8") as f:
                    for line in updated_lines:
                        f.write(line + "\n")
                tmp_path.replace(file_path)
                logger.info(f"Successfully migrated: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to write updated events to {file_path.name}: {e}")
                if tmp_path.exists():
                    tmp_path.unlink()
                continue
        else:
            logger.info(f"Already up-to-date: {file_path.name}")

        # Re-fetch events from raw_lines to build the index accurately
        migrated_events = [r for r in raw_lines if isinstance(r, dict) and r.get("schema_type") == "run_event"]

        # Compile index information
        if not migrated_events:
            # Handle empty or non-event run files gracefully
            timestamp = ""
            material_type = ""
            status = ""
            cost = 0.0
            event_count = 0
        else:
            timestamp = next((e.get("timestamp") for e in migrated_events if e.get("timestamp")), "")
            material_type = next((e.get("material_type") for e in migrated_events if e.get("material_type")), "")
            status = next((e.get("status") for e in reversed(migrated_events) if e.get("status")), "")
            event_count = len(migrated_events)
            
            cost = 0.0
            for e in migrated_events:
                c_val = e.get("cost")
                if c_val is not None:
                    try:
                        cost += float(c_val)
                    except (ValueError, TypeError):
                        pass

        index_entries.append({
            "run_id": str(existing_run_id),
            "campaign_id": str(existing_campaign_id),
            "workflow_id": str(workflow_id),
            "timestamp": str(timestamp),
            "material_type": str(material_type),
            "status": str(status),
            "event_count": int(event_count),
            "cost": float(cost),
        })

    # 2. Write or update runs/_index.jsonl in the folder
    index_path = runs_dir / "_index.jsonl"
    index_tmp_path = runs_dir / "_index.jsonl.tmp"
    
    # Sort index entries by timestamp, then workflow_id
    index_entries.sort(key=lambda x: (x.get("timestamp") or "", x.get("workflow_id") or ""))

    logger.info(f"Compiling index for {runs_dir} with {len(index_entries)} entries...")
    try:
        with index_tmp_path.open("w", encoding="utf-8") as f:
            for entry in index_entries:
                f.write(json.dumps(entry, default=str) + "\n")
        index_tmp_path.replace(index_path)
        logger.info(f"Successfully compiled index: {index_path}")
    except Exception as e:
        logger.error(f"Failed to write index to {index_path}: {e}")
        if index_tmp_path.exists():
            index_tmp_path.unlink()


def main() -> None:
    """
    Main entry point for run events migration.
    """
    logger.info("Starting run events migration...")
    
    root_dirs = [
        Path("/Users/twells/Documents/brand-gen/.brand-gen/brands"),
        Path("/Users/twells/Documents/brand-gen/brands"),
    ]
    
    runs_dirs: List[Path] = []
    for root_dir in root_dirs:
        if root_dir.exists() and root_dir.is_dir():
            for brand_dir in sorted(root_dir.iterdir()):
                if brand_dir.is_dir():
                    runs_dir = brand_dir / "runs"
                    if runs_dir.exists() and runs_dir.is_dir():
                        runs_dirs.append(runs_dir)
                        
    if not runs_dirs:
        logger.warning("No runs directories discovered to migrate.")
        return
        
    logger.info(f"Discovered {len(runs_dirs)} runs directories to process.")
    for runs_dir in runs_dirs:
        try:
            migrate_runs_directory(runs_dir)
        except Exception as e:
            logger.exception(f"Unexpected error processing directory {runs_dir}: {e}")
            
    logger.info("Run events migration completed successfully!")


if __name__ == "__main__":
    main()
