"""User import service tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db.models import User
from app.services.user_import_service import (
    UserImportService,
    infer_phone_country,
    normalize_wa_id,
    resolve_local_photo_file,
)


def test_normalize_wa_id_and_country_detection() -> None:
    assert normalize_wa_id("+44 7767 348952") == "447767348952"
    assert infer_phone_country("447767348952") == ("44", "GB")
    assert infer_phone_country("51980638666") == ("51", "PE")


def test_resolve_local_photo_file_uses_source_url_basename(tmp_path: Path) -> None:
    photo_path = tmp_path / "473403098_357715290768153_1762072041177642909_n.jpg"
    photo_path.write_bytes(b"jpg")

    resolved = resolve_local_photo_file(
        raw_number="+447767348952",
        wa_id="447767348952",
        source_url=(
            "https://example.com/v/t61.24694-24/"
            "473403098_357715290768153_1762072041177642909_n.jpg?foo=bar"
        ),
        photos_dir=tmp_path,
    )

    assert resolved == photo_path


@pytest.mark.asyncio
async def test_import_group_members_updates_profile_snapshot_without_overwriting_confirmed_name(
    session_maker,
    tmp_path: Path,
) -> None:
    async with session_maker() as session:
        user = User(
            wa_id="447767348952",
            wa_profile_name="Kenji WA",
            confirmed_name="Kenji H.",
        )
        session.add(user)
        await session.commit()

        csv_path = tmp_path / "members.csv"
        csv_path.write_text(
            "Numero,Nombre_Guardado,Alias_Grupo,Foto_URL\n"
            '"+447767348952","Kenji Saved","~kenji","https://example.com/avatar.jpg"\n',
            encoding="utf-8",
        )

        service = UserImportService(session)
        summary = await service.import_group_members(csv_path=csv_path)
        await session.refresh(user)

        assert summary.created == 0
        assert summary.updated == 1
        assert user.wa_profile_name == "Kenji WA"
        assert user.confirmed_name == "Kenji H."
        assert user.group_alias == "~kenji"
        assert user.profile_photo_source_url == "https://example.com/avatar.jpg"
        assert user.phone_country_prefix == "44"
        assert user.country_code == "GB"
        assert user.profile_metadata == {"saved_contact_name": "Kenji Saved"}
