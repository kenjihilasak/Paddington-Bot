"""Manual CSV import helpers for WhatsApp group member profiles."""

from __future__ import annotations

import csv
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories import UserRepository


COUNTRY_CODE_BY_PHONE_PREFIX = {
    "353": "IE",
    "351": "PT",
    "598": "UY",
    "595": "PY",
    "593": "EC",
    "591": "BO",
    "58": "VE",
    "57": "CO",
    "56": "CL",
    "54": "AR",
    "52": "MX",
    "51": "PE",
    "49": "DE",
    "44": "GB",
    "39": "IT",
    "34": "ES",
    "33": "FR",
    "1": "US",
}
SUPPORTED_PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


@dataclass(slots=True)
class GroupMemberImportSummary:
    """Simple result summary for CLI imports."""

    created: int = 0
    updated: int = 0
    skipped: int = 0


def normalize_wa_id(raw_value: str) -> str:
    """Normalize a WhatsApp number into digits-only E.164 style without plus."""

    return "".join(character for character in raw_value if character.isdigit())


def clean_optional_text(raw_value: str | None) -> str | None:
    """Trim optional text and collapse invisible placeholders to null."""

    if raw_value is None:
        return None
    normalized = unicodedata.normalize("NFKC", raw_value).replace("\u2800", " ").strip()
    return normalized or None


def first_present_value(row: dict[str, str], *field_names: str) -> str | None:
    """Return the first non-empty CSV value from any supported column name."""

    for field_name in field_names:
        value = clean_optional_text(row.get(field_name))
        if value is not None:
            return value
    return None


def infer_phone_country(wa_id: str) -> tuple[str | None, str | None]:
    """Infer the phone prefix and ISO country code for known community prefixes."""

    for prefix in sorted(COUNTRY_CODE_BY_PHONE_PREFIX, key=len, reverse=True):
        if wa_id.startswith(prefix):
            return prefix, COUNTRY_CODE_BY_PHONE_PREFIX[prefix]
    return None, None


def resolve_local_photo_file(
    *,
    raw_number: str,
    wa_id: str,
    source_url: str | None,
    photos_dir: Path | None,
) -> Path | None:
    """Try common file-name strategies to match a downloaded avatar."""

    if photos_dir is None or not photos_dir.exists():
        return None

    candidate_stems: list[str] = []
    cleaned_number = clean_optional_text(raw_number)
    if cleaned_number:
        candidate_stems.extend([cleaned_number, cleaned_number.lstrip("+")])
    if wa_id:
        candidate_stems.append(wa_id)

    if source_url:
        parsed = urlparse(source_url)
        basename = Path(parsed.path).name
        if basename:
            candidate_stems.append(basename)
            candidate_stems.append(Path(basename).stem)

    seen: set[str] = set()
    for stem in candidate_stems:
        if not stem:
            continue
        normalized_stem = stem.strip()
        if not normalized_stem or normalized_stem in seen:
            continue
        seen.add(normalized_stem)

        direct_candidate = photos_dir / normalized_stem
        if direct_candidate.is_file():
            return direct_candidate

        for extension in SUPPORTED_PHOTO_EXTENSIONS:
            file_candidate = photos_dir / f"{normalized_stem}{extension}"
            if file_candidate.is_file():
                return file_candidate

    return None


class UserImportService:
    """Persist WhatsApp group member profile snapshots into users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repository = UserRepository(session)

    async def import_group_members(
        self,
        *,
        csv_path: Path,
        photos_dir: Path | None = None,
        copy_photos_to: Path | None = None,
        dry_run: bool = False,
    ) -> GroupMemberImportSummary:
        """Import a CSV export of WhatsApp group members into users."""

        summary = GroupMemberImportSummary()
        if copy_photos_to is not None:
            copy_photos_to.mkdir(parents=True, exist_ok=True)

        with csv_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
            reader = csv.DictReader(file_handle)
            for row in reader:
                raw_number = first_present_value(row, "wa_id", "Numero") or ""
                wa_id = normalize_wa_id(raw_number)
                if not wa_id:
                    summary.skipped += 1
                    continue

                existing_user = await self.user_repository.get_by_wa_id(wa_id)
                user = existing_user or User(wa_id=wa_id)
                if existing_user is None:
                    self.session.add(user)
                    summary.created += 1
                else:
                    summary.updated += 1

                wa_profile_name = first_present_value(row, "wa_profile_name")
                if wa_profile_name is not None:
                    user.wa_profile_name = wa_profile_name

                profile_photo_source_url = first_present_value(row, "photo_url", "Foto_URL")
                if profile_photo_source_url is not None:
                    user.profile_photo_source_url = profile_photo_source_url

                phone_country_prefix, country_code = infer_phone_country(wa_id)
                user.phone_country_prefix = phone_country_prefix
                user.country_code = country_code

                metadata = dict(user.profile_metadata or {})
                saved_contact_name = first_present_value(row, "Nombre_Guardado")
                if saved_contact_name is not None:
                    metadata["saved_contact_name"] = saved_contact_name

                local_photo_file = resolve_local_photo_file(
                    raw_number=raw_number,
                    wa_id=wa_id,
                    source_url=profile_photo_source_url,
                    photos_dir=photos_dir,
                )
                if local_photo_file is not None:
                    if copy_photos_to is not None:
                        target_path = copy_photos_to / f"{wa_id}{local_photo_file.suffix.lower()}"
                        shutil.copy2(local_photo_file, target_path)
                        metadata["local_photo_file"] = str(target_path)
                    else:
                        metadata["local_photo_file"] = str(local_photo_file)

                user.profile_metadata = metadata or None

        if dry_run:
            await self.session.rollback()
            return summary

        await self.session.commit()
        return summary
