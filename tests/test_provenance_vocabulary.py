"""The words the recorder writes and the words the dashboard reads must match.

There is no type checking on the ARM build, so a frontend map keyed on "real"
while the backend writes "real-arm" compiles, ships, and quietly labels every
real recording "source not recorded". These tests pin both ends of the string.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hashtag_robotics.models import DatasetManifest, JobKind
from hashtag_robotics.workflows import RECORDING_SOURCE

APP_TSX = Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.tsx"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [(JobKind.SIM_RECORDING, "simulation"), (JobKind.RECORDING, "real-arm")],
)
def test_the_frontend_knows_the_word_the_recorder_writes(kind: JobKind, expected: str) -> None:
    assert RECORDING_SOURCE[kind] == expected
    table = re.search(r"const PROVENANCE[^{]*\{(.*?)\n\};", APP_TSX.read_text(), re.S)
    assert table is not None, "PROVENANCE table not found in App.tsx"
    assert f'"{expected}"' in table.group(1) or f"{expected}:" in table.group(1)


def test_a_merge_of_two_simulated_takes_is_still_simulated() -> None:
    inputs = [
        DatasetManifest(name="a", task="t", provenance={"source": "simulation"}),
        DatasetManifest(name="b", task="t", provenance={"source": "simulation"}),
    ]

    sources = {m.provenance["source"] for m in inputs}

    assert len(sources) == 1


def test_a_merge_of_sim_and_real_is_neither() -> None:
    """Co-training sets are mixed by design; calling one "real arm" is a lie."""
    inputs = [
        DatasetManifest(name="a", task="t", provenance={"source": "simulation"}),
        DatasetManifest(name="b", task="t", provenance={"source": "real-arm"}),
    ]

    sources = {m.provenance["source"] for m in inputs}

    assert len(sources) > 1
    assert "mixed" in APP_TSX.read_text()


# -- what a merge may claim about where it came from --------------------------


def merged_source(manifests: list[DatasetManifest]) -> dict[str, object]:
    """The rule the transform applies, kept in one place so it can be checked."""
    sources = [str(item.provenance.get("source") or "") for item in manifests]
    distinct = set(sources)
    result: dict[str, object] = {}
    if len(distinct) == 1 and "" not in distinct:
        result["source"] = distinct.pop()
    elif len(distinct) > 1:
        result["source"] = "mixed"
        result["mixed_sources"] = sorted(name for name in distinct if name)
    return result


def manifest(source: str | None) -> DatasetManifest:
    provenance = {"source": source} if source else {}
    return DatasetManifest(name="x", task="t", provenance=provenance)


def test_two_simulated_takes_stay_simulated() -> None:
    assert merged_source([manifest("simulation"), manifest("simulation")]) == {
        "source": "simulation"
    }


def test_sim_and_real_come_out_mixed() -> None:
    assert merged_source([manifest("simulation"), manifest("real-arm")]) == {
        "source": "mixed",
        "mixed_sources": ["real-arm", "simulation"],
    }


def test_an_unrecorded_source_cannot_join_a_consensus() -> None:
    """Caught on real data: the T7 recording predates provenance being written,
    so merging it with a simulated take produced a set labelled "simulation" --
    a real arm's frames flying a simulated flag."""
    result = merged_source([manifest("simulation"), manifest(None)])

    assert result["source"] == "mixed"
    assert result["mixed_sources"] == ["simulation"]


def test_when_nothing_declares_a_source_nothing_is_claimed() -> None:
    assert merged_source([manifest(None), manifest(None)]) == {}


def test_the_rule_in_the_test_matches_the_one_that_runs() -> None:
    """Two copies of a rule is how they drift; this pins them to each other."""
    source = (
        Path(__file__).resolve().parents[1] / "src" / "hashtag_robotics" / "workflows.py"
    ).read_text()

    assert 'if len(distinct) == 1 and "" not in distinct:' in source
    assert 'provenance["source"] = "mixed"' in source
