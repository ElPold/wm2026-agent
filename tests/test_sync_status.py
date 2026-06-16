import json

from src.pipeline.sync_status import (
    build_sync_display,
    load_sync_status,
    update_sync_status,
)


def test_update_and_load_sync_status(tmp_path):
    path = tmp_path / "sync_status.json"
    update_sync_status(
        "predictions",
        {
            "updated_at": "2026-06-16T10:00:00+02:00",
            "rounds": 17,
            "mode": "all-rounds",
            "source": "auto",
        },
        path=path,
    )
    update_sync_status(
        "kicktipp",
        {
            "synced_at": "2026-06-16T10:05:00+02:00",
            "status": "ok",
            "spieltag": 2,
            "tips_count": 7,
            "agent_rounds": ["Matchday 4", "Matchday 5", "Matchday 6"],
            "mode": "auto",
            "error": None,
        },
        path=path,
    )

    payload = load_sync_status(path)
    assert payload["predictions"]["rounds"] == 17
    assert payload["kicktipp"]["status"] == "ok"


def test_build_sync_display_formats_timestamps(tmp_path):
    path = tmp_path / "sync_status.json"
    path.write_text(
        json.dumps(
            {
                "predictions": {
                    "updated_at": "2026-06-16T10:00:00+02:00",
                    "rounds": 17,
                    "mode": "all-rounds",
                    "source": "auto",
                },
                "kicktipp": {
                    "synced_at": "2026-06-16T10:05:00+02:00",
                    "status": "failed",
                    "spieltag": 2,
                    "tips_count": 0,
                    "agent_rounds": [],
                    "mode": "auto",
                    "error": "kicktipp-agent exit code 1",
                },
            }
        ),
        encoding="utf-8",
    )

    display = build_sync_display(path)
    assert display is not None
    assert display["predictions"]["updated_at"] == "16.06.2026 10:00"
    assert display["kicktipp"]["status_class"] == "failed"
    assert display["kicktipp"]["error"] == "kicktipp-agent exit code 1"
