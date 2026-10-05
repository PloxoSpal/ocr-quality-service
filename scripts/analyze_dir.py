import argparse
import sys
from pathlib import Path

import httpx

SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".pdf"}


def main() -> int:
    """Точка входа."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--checks", default=None, help="Comma-separated subset of checks")
    args = parser.parse_args()

    files = sorted(p for d in args.dirs for p in d.iterdir() if p.suffix.lower() in SUFFIXES)
    if not files:
        print("No files found", file=sys.stderr)
        return 2

    suitable = failed = 0
    with httpx.Client(base_url=args.url, timeout=300.0) as client:
        for path in files:
            data = {"checks": args.checks} if args.checks else None
            response = client.post(
                "/analyze", files={"file": (path.name, path.read_bytes())}, data=data
            )
            if response.status_code != 200:
                failed += 1
                detail = response.json().get("detail")
                print(f"{path.name:20s} HTTP {response.status_code} {detail}")
                continue
            body = response.json()
            suitable += body["suitable_for_ocr"]
            pages = f" pages={body['summary']['page_count']}" if "summary" in body else ""
            issues = "; ".join(body["issues"]) or "-"
            print(
                f"{path.name:20s} {'OK ' if body['suitable_for_ocr'] else 'BAD'} "
                f"score={body['quality_score'] if body['quality_score'] is not None else '-':<6} "
                f"{body['processing_time_ms']:7.1f} ms{pages}  {issues}"
            )
    print(
        f"\n{len(files)} files: {suitable} suitable, {len(files) - suitable - failed} not, "
        f"{failed} errors"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
