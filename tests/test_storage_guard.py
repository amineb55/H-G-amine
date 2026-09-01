"""The storage layer refuses anything that could escape an inspection's space."""

import pytest

from app.services import storage


def test_path_traversal_in_storage_key_is_refused():
    with pytest.raises(storage.StorageError):
        storage.path("../outside")


def test_evidence_names_are_validated():
    for inspection_id, filename in [
        ("ok-id", "a b.jpg"),
        ("ok-id", ".."),
        ("bad/id", "image.jpg"),
        ("", "image.jpg"),
    ]:
        with pytest.raises(storage.StorageError):
            storage.get_evidence(inspection_id, filename)
        with pytest.raises(storage.StorageError):
            storage.put_evidence(inspection_id, filename, b"data")


def test_delete_evidence_validates_the_inspection_id():
    with pytest.raises(storage.StorageError):
        storage.delete_evidence("../../etc")


def test_evidence_endpoint_rejects_bad_names(client, upload):
    inspection_id = upload().json()["inspection_id"]
    response = client.get(f"/inspections/{inspection_id}/evidence/bad%20name.jpg")
    assert response.status_code == 400


def test_missing_evidence_is_404(client, upload):
    inspection_id = upload().json()["inspection_id"]
    response = client.get(f"/inspections/{inspection_id}/evidence/absent.jpg")
    assert response.status_code == 404


def test_delete_media_removes_the_whole_directory(tmp_path):
    import uuid
    from pathlib import Path

    inspection_id = f"unit-{uuid.uuid4().hex}"
    target = Path(storage.path(inspection_id))
    target.mkdir(parents=True)
    (target / "media.jpg").write_bytes(b"x")

    storage.delete_media(inspection_id)
    assert not target.exists()
