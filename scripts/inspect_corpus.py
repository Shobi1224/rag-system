"""Inspects and validates the Phase 1 static Kafka corpus."""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MANIFEST_FILE = BASE_DIR / "data" / "corpus" / "manifest.json"


def main():
    if not MANIFEST_FILE.exists():
        print("[!] No manifest found. Please run `python ingest/fetch_corpus.py` first.")
        return

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("\n=======================================================")
    print("             Phase 1: Ingested Corpus Inspection       ")
    print("=======================================================")
    print(f" Target Kafka Version: {manifest.get('kafka_target_version')}")
    print(f" Total Documents:      {manifest.get('total_documents')}")
    print(f" Total Tokens:         {manifest.get('total_tokens'):,} tokens")
    print(f" Total Size:           {manifest.get('total_size_kb')} KB ({manifest.get('total_size_bytes'):,} bytes)")
    print(f" Total Headings:       {manifest.get('total_headings', {}).get('total', 0)} "
          f"(H1: {manifest.get('total_headings', {}).get('h1', 0)}, "
          f"H2: {manifest.get('total_headings', {}).get('h2', 0)}, "
          f"H3: {manifest.get('total_headings', {}).get('h3', 0)})")
    
    print("\n Category Breakdown:")
    for cat, stats in manifest.get("category_summary", {}).items():
        print(f"   • {cat:<20}: {stats['documents']:>2} docs  |  {stats['tokens']:>6,} tokens")

    print("\n Sample Documents with Frontmatter & Hashes:")
    for doc in manifest.get("documents", [])[:6]:
        print(f"   - [{doc['doc_id']}] {doc['filename']} ({doc['token_count']:,} tokens, {doc['size_bytes']:,} bytes)")
        print(f"     SHA256: {doc['content_sha256'][:16]}... | URL: {doc['source_url']}")

    failed = manifest.get("failed_fetches", [])
    if failed:
        print(f"\n [!] Failed Fetches ({len(failed)}):")
        for url in failed:
            print(f"     - {url}")
    else:
        print("\n [OK] All sources processed successfully with zero fetch errors.")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
