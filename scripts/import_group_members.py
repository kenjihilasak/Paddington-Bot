"""Import WhatsApp group members from a CSV export into users."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.db.session import AsyncSessionLocal
from app.services.user_import_service import UserImportService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", dest="csv_path", required=True, help="Path to the CSV export file.")
    parser.add_argument(
        "--photos-dir",
        dest="photos_dir",
        default=None,
        help="Optional directory containing downloaded profile photos.",
    )
    parser.add_argument(
        "--copy-photos-to",
        dest="copy_photos_to",
        default=None,
        help="Optional target directory to copy matched photos into.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report changes without committing them.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv_path).expanduser().resolve()
    photos_dir = Path(args.photos_dir).expanduser().resolve() if args.photos_dir else None
    copy_photos_to = Path(args.copy_photos_to).expanduser().resolve() if args.copy_photos_to else None

    async with AsyncSessionLocal() as session:
        service = UserImportService(session)
        summary = await service.import_group_members(
            csv_path=csv_path,
            photos_dir=photos_dir,
            copy_photos_to=copy_photos_to,
            dry_run=args.dry_run,
        )

    mode = "dry-run" if args.dry_run else "import"
    print(
        f"{mode} finished: created={summary.created}, updated={summary.updated}, skipped={summary.skipped}"
    )


if __name__ == "__main__":
    asyncio.run(main())
