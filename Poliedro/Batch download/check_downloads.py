#!/usr/bin/env python3
"""
Check download status by comparing CSV entries with downloaded files.
Lists:
- Entries missing all files
- Entries missing one file (no pair)
- Orphan files (not in CSV)
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

import dateparser

# Configuration - same as downloader
CSV_FILE = Path("./zoom_recordings.csv")
OUTPUT_DIR = Path("./zoom_downloads")


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', name)
    sanitized = sanitized.strip('. ')
    return sanitized[:200] if len(sanitized) > 200 else sanitized


def parse_date(date_str: str) -> str:
    """Parse Portuguese date string to YYYY-MM-DD format."""
    parsed = dateparser.parse(date_str, languages=['pt'], settings={
        'PREFER_DAY_OF_MONTH': 'first',
        'PREFER_DATES_FROM': 'past',
        'DEFAULT_LANGUAGES': ['pt']
    })
    if parsed:
        return parsed.strftime('%Y-%m-%d')
    return date_str


def build_filename_base(row: dict) -> str:
    """Build the expected filename base from CSV row (without _esq/_dir suffix)."""
    date_formatted = parse_date(row['data'])
    title = row.get('conteudo', '') or row.get('title', '')
    
    name = f"{row['semestre']} - {row['disciplina']} - {row['frente']} - {date_formatted} - {title}"
    return sanitize_filename(name)


def load_csv_entries() -> list[dict]:
    """Load all entries from CSV."""
    entries = []
    
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            # Normalize keys to lowercase
            normalized = {k.lower().strip(): v.strip() for k, v in row.items()}
            
            # Map columns
            entry = {
                'disciplina': normalized.get('disciplina', ''),
                'semestre': normalized.get('semestre', ''),
                'data': normalized.get('data', ''),
                'professor': normalized.get('professor', ''),
                'frente': normalized.get('frente', ''),
                'conteudo': normalized.get('conteúdo / link da aula', '') or normalized.get('conteudo', ''),
                'url': normalized.get('link', '') or normalized.get('url', ''),
            }
            
            if entry['url']:
                entry['filename_base'] = build_filename_base(entry)
                entries.append(entry)
    
    return entries


def scan_download_files() -> dict[str, list[Path]]:
    """Scan download directory and group files by base name."""
    files_by_base = defaultdict(list)
    
    if not OUTPUT_DIR.exists():
        return files_by_base
    
    for file in OUTPUT_DIR.glob("*.mp4"):
        # Remove " - esq" or " - dir" suffix to get base name
        name = file.stem
        if name.endswith(' - esq') or name.endswith(' - dir'):
            base = name[:-6]  # Remove " - esq" or " - dir" (6 chars)
        elif name.endswith('_esq') or name.endswith('_dir'):
            base = name[:-4]
        elif name.endswith('_screen') or name.endswith('_camera'):
            base = name.rsplit('_', 1)[0]
        else:
            base = name
        
        files_by_base[base].append(file)
    
    return files_by_base


def check_downloads():
    """Main check function."""
    print("=" * 70)
    print("DOWNLOAD STATUS CHECK")
    print("=" * 70)
    
    # Load data
    print(f"\nLoading CSV: {CSV_FILE}")
    entries = load_csv_entries()
    print(f"  Found {len(entries)} entries with URLs")
    
    print(f"\nScanning downloads: {OUTPUT_DIR}")
    files_by_base = scan_download_files()
    total_files = sum(len(files) for files in files_by_base.values())
    print(f"  Found {total_files} MP4 files ({len(files_by_base)} unique recordings)")
    
    # Track results
    missing_all = []      # Entries with no files
    missing_pair = []     # Entries with only one file
    complete = []         # Entries with both files
    
    # Set of all expected base names from CSV
    expected_bases = set()
    
    # Check each CSV entry
    for entry in entries:
        base = entry['filename_base']
        expected_bases.add(base)
        
        files = files_by_base.get(base, [])
        
        if len(files) == 0:
            missing_all.append(entry)
        elif len(files) == 1:
            missing_pair.append({
                **entry,
                'existing_file': files[0].name
            })
        else:
            complete.append(entry)
    
    # Find orphan files (files not matching any CSV entry)
    orphan_files = []
    for base, files in files_by_base.items():
        if base not in expected_bases:
            orphan_files.extend(files)
    
    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\n✓ Complete (both files): {len(complete)}")
    print(f"⚠ Missing pair (one file): {len(missing_pair)}")
    print(f"✗ Missing all files: {len(missing_all)}")
    print(f"? Orphan files (no CSV entry): {len(orphan_files)}")
    
    # Details: Missing all files
    if missing_all:
        print("\n" + "-" * 70)
        print("MISSING ALL FILES:")
        print("-" * 70)
        for entry in missing_all:
            print(f"  • {entry['disciplina']} - {entry['frente']} - {entry['data']}")
            print(f"    {entry['conteudo'][:60]}..." if len(entry['conteudo']) > 60 else f"    {entry['conteudo']}")
            print(f"    Expected: {entry['filename_base']}_*.mp4")
    
    # Details: Missing pair
    if missing_pair:
        print("\n" + "-" * 70)
        print("MISSING PAIR (only one file):")
        print("-" * 70)
        for entry in missing_pair:
            print(f"  • {entry['disciplina']} - {entry['frente']} - {entry['data']}")
            print(f"    Has: {entry['existing_file']}")
    
    # Details: Orphan files
    if orphan_files:
        print("\n" + "-" * 70)
        print("ORPHAN FILES (no CSV entry):")
        print("-" * 70)
        for file in sorted(orphan_files):
            size_mb = file.stat().st_size / 1024 / 1024
            print(f"  • {file.name} ({size_mb:.1f} MB)")
    
    # Save reports to CSV
    if missing_all:
        missing_csv = OUTPUT_DIR / "check_missing_all.csv"
        with open(missing_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Disciplina', 'Semestre', 'Data', 'Professor', 'Frente', 'Conteúdo / Link da aula', 'Link', 'Expected Name'])
            for entry in missing_all:
                writer.writerow([
                    entry['disciplina'], entry['semestre'], entry['data'],
                    entry['professor'], entry['frente'], entry['conteudo'], entry['url'],
                    entry['filename_base']
                ])
        print(f"\n📄 Missing entries saved to: {missing_csv}")
    
    if missing_pair:
        pair_csv = OUTPUT_DIR / "check_missing_pair.csv"
        with open(pair_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Disciplina', 'Semestre', 'Data', 'Professor', 'Frente', 'Conteúdo / Link da aula', 'Link', 'Expected Name', 'Existing File'])
            for entry in missing_pair:
                writer.writerow([
                    entry['disciplina'], entry['semestre'], entry['data'],
                    entry['professor'], entry['frente'], entry['conteudo'], entry['url'],
                    entry['filename_base'],
                    entry['existing_file']
                ])
        print(f"📄 Missing pairs saved to: {pair_csv}")
    
    if orphan_files:
        orphan_csv = OUTPUT_DIR / "check_orphan_files.csv"
        with open(orphan_csv, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Filename', 'Size (MB)'])
            for file in sorted(orphan_files):
                size_mb = file.stat().st_size / 1024 / 1024
                writer.writerow([file.name, f"{size_mb:.1f}"])
        print(f"📄 Orphan files saved to: {orphan_csv}")
    
    print("\n" + "=" * 70)
    print("CHECK COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    check_downloads()
