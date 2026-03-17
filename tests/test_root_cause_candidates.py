from nanobot.agent.root_cause_candidates import (
    extract_candidate_signals,
    map_root_cause_candidates,
    render_candidate_root_causes,
)


def test_extract_signals_detects_timeout_and_cross_node_common() -> None:
    summary = """
## Multi-Target Summary: search_log
### Common Findings
- node-a, node-b: timeout while connecting to storage backend
## Timeline
- 10:21:03 node-a timeout while connecting to storage backend
- 10:21:05 node-b timeout while connecting to storage backend
"""

    result = extract_candidate_signals(summary)

    assert "timeout" in result.signals
    assert "cross_node_common" in result.signals
    assert any("timeout while connecting" in item for item in result.evidence_lines)


def test_extract_signals_detects_retry_and_dependency_hints() -> None:
    summary = """
## Local Findings
- node-a: retry exceeded for storage backend
"""

    result = extract_candidate_signals(summary)

    assert "retry_exhausted" in result.signals
    assert "dependency_backend" in result.signals


def test_map_root_cause_candidates_maps_timeout_to_cross_node_shared_issue() -> None:
    extracted = extract_candidate_signals(
        """
### Common Findings
- node-a, node-b: timeout while connecting to storage backend
"""
    )

    candidates = map_root_cause_candidates(extracted)

    assert "跨节点共享连接/超时异常" in [item.candidate_type for item in candidates]


def test_map_root_cause_candidates_maps_single_node_to_local_issue() -> None:
    extracted = extract_candidate_signals(
        """
### Local Findings
- node-a: timeout while connecting to storage backend
"""
    )

    candidates = map_root_cause_candidates(extracted)

    assert "局部节点异常" in [item.candidate_type for item in candidates]


def test_map_root_cause_candidates_returns_empty_when_evidence_is_too_weak() -> None:
    extracted = extract_candidate_signals("minor issue observed")

    candidates = map_root_cause_candidates(extracted)

    assert candidates == []


def test_render_candidate_root_causes_includes_supporting_evidence() -> None:
    extracted = extract_candidate_signals(
        """
### Common Findings
- node-a, node-b: timeout while connecting to storage backend
## Timeline
- 10:21:03 node-a timeout while connecting to storage backend
- 10:21:05 node-b timeout while connecting to storage backend
"""
    )
    candidates = map_root_cause_candidates(extracted)

    rendered = render_candidate_root_causes(candidates)

    assert "Candidate Root Cause" in rendered
    assert "Supporting Evidence" in rendered
    assert "已确认根因" not in rendered
    assert "跨节点共享连接/超时异常" in rendered


def test_render_candidate_root_causes_falls_back_when_no_candidates() -> None:
    rendered = render_candidate_root_causes([])

    assert "当前证据不足以形成候选根因" in rendered


def test_map_root_cause_candidates_clips_to_two_candidates() -> None:
    extracted = extract_candidate_signals(
        """
### Common Findings
- node-a, node-b: timeout while connecting to storage backend
### Local Findings
- node-c: service failed with retry exceeded
## Timeline
- 10:21:03 node-a timeout while connecting to storage backend
- 10:21:05 node-b timeout while connecting to storage backend
- 10:21:08 node-c failed retry exceeded for storage backend
"""
    )

    candidates = map_root_cause_candidates(extracted)

    assert len(candidates) <= 2


def test_render_candidate_root_causes_never_uses_confirmed_wording() -> None:
    extracted = extract_candidate_signals(
        """
### Common Findings
- node-a, node-b: timeout while connecting to storage backend
"""
    )
    candidates = map_root_cause_candidates(extracted)

    rendered = render_candidate_root_causes(candidates)

    assert "已确认根因" not in rendered
    assert "候选根因" in rendered
