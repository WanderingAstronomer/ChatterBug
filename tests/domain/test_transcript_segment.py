from vociferous.domain import TranscriptSegment


def test_transcript_segment_prefers_refined_text() -> None:
    segment = TranscriptSegment(start=0.0, end=1.0, raw_text="raw", refined_text="clean")

    assert segment.text == "clean"
    assert segment.start_s == 0.0
    assert segment.end_s == 1.0


def test_transcript_segment_generates_id() -> None:
    segment = TranscriptSegment(start=0.0, end=1.0, raw_text="hello")

    assert segment.id
    assert segment.raw_text == "hello"


def test_transcript_segment_validation() -> None:
    try:
        TranscriptSegment(start=2.0, end=1.0, raw_text="oops")
    except ValueError as exc:
        assert "greater than or equal" in str(exc)
    else:  # pragma: no cover - sanity guard
        assert False, "Expected ValueError for end before start"


def test_transcript_segment_with_refined_returns_new_instance() -> None:
    segment = TranscriptSegment(start=0.0, end=1.0, raw_text="raw")
    refined = segment.with_refined("clean")

    assert refined is not segment
    assert refined.refined_text == "clean"
    assert refined.text == "clean"
