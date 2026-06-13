from src.pipeline.prediction_store import (
    merge_predictions_index,
    should_replace_prediction,
)


def test_should_not_replace_locked_tip_with_pending():
    existing = {"fixture_id": "wc26-001", "tip": "1:0", "pending": False}
    incoming = {"fixture_id": "wc26-001", "pending": True}
    assert should_replace_prediction(existing, incoming, started=True) is False


def test_should_replace_pending_with_tip():
    existing = {"fixture_id": "wc26-001", "pending": True}
    incoming = {"fixture_id": "wc26-001", "tip": "1:0"}
    assert should_replace_prediction(existing, incoming, started=True) is True


def test_merge_keeps_tip_when_later_payload_is_pending():
    payloads = [
        {
            "predictions": [
                {
                    "fixture_id": "wc26-001",
                    "kickoff_berlin": "2026-06-11T21:00:00+02:00",
                    "tip": "1:0",
                }
            ]
        },
        {
            "predictions": [
                {
                    "fixture_id": "wc26-001",
                    "kickoff_berlin": "2026-06-11T21:00:00+02:00",
                    "pending": True,
                }
            ]
        },
    ]
    merged = merge_predictions_index(payloads)
    assert merged["wc26-001"]["tip"] == "1:0"
