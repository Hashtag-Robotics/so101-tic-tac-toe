"""Merging a set with something it already contains does not fail.

Aggregation copies both inputs and the result grades `verified`. Measured on
this disk: five simulated episodes merged with a set that already held them
produced eleven episodes, five of which were byte-for-byte duplicates -- ten
simulated takes against one real one, when the operator asked for five.
"""

from __future__ import annotations

from hashtag_robotics.dataset import (
    _mark_duplicates,
    lineage_overlaps,
    recording_lineage,
)
from hashtag_robotics.models import DatasetManifest


def recording(repo_id: str) -> DatasetManifest:
    return DatasetManifest(name=repo_id, task="t", repo_id=repo_id)


def merged(repo_id: str, sources: list[str]) -> DatasetManifest:
    return DatasetManifest(
        name=repo_id, task="t", repo_id=repo_id, provenance={"merged_from": sources}
    )


def test_a_plain_recording_stands_for_itself() -> None:
    take = recording("u/take")

    assert recording_lineage(take, {"u/take": take}) == {"u/take"}


def test_a_merge_resolves_to_what_it_is_made_of() -> None:
    sim, real = recording("u/sim"), recording("u/real")
    both = merged("u/both", ["u/sim", "u/real"])
    library = {"u/sim": sim, "u/real": real, "u/both": both}

    assert recording_lineage(both, library) == {"u/sim", "u/real"}


def test_a_merge_of_a_merge_resolves_all_the_way_down() -> None:
    sim, real, extra = recording("u/sim"), recording("u/real"), recording("u/extra")
    both = merged("u/both", ["u/sim", "u/real"])
    more = merged("u/more", ["u/both", "u/extra"])
    library = {m.repo_id: m for m in (sim, real, extra, both, more)}

    assert recording_lineage(more, library) == {"u/sim", "u/real", "u/extra"}


def test_a_forgotten_input_still_counts_as_a_recording() -> None:
    """Dropping it from the library would let it overlap unnoticed."""
    both = merged("u/both", ["u/sim", "u/gone"])

    assert recording_lineage(both, {"u/both": both}) == {"u/sim", "u/gone"}


def test_merging_a_set_with_what_it_contains_is_refused() -> None:
    sim, real = recording("u/sim"), recording("u/real")
    both = merged("u/both", ["u/sim", "u/real"])
    library = [sim, real, both]

    overlaps = lineage_overlaps([sim, both], library)

    assert len(overlaps) == 1
    assert overlaps[0]["shared"] == ["u/sim"]


def test_two_sets_sharing_an_ancestor_are_refused_too() -> None:
    """Neither contains the other, and the shared take still lands in twice."""
    sim, real, extra = recording("u/sim"), recording("u/real"), recording("u/extra")
    left = merged("u/left", ["u/sim", "u/real"])
    right = merged("u/right", ["u/sim", "u/extra"])

    overlaps = lineage_overlaps([left, right], [sim, real, extra, left, right])

    assert overlaps[0]["shared"] == ["u/sim"]


def test_growing_a_set_with_something_new_is_allowed() -> None:
    sim, real, fresh = recording("u/sim"), recording("u/real"), recording("u/fresh")
    both = merged("u/both", ["u/sim", "u/real"])

    assert lineage_overlaps([both, fresh], [sim, real, fresh, both]) == []


# -- catching it after the fact ----------------------------------------------


def episode(index: int, frames: int, signature: tuple) -> dict:
    return {
        "index": index,
        "frames": frames,
        "_action_signature": signature,
        "_state_signature": signature,
    }


def test_an_identical_episode_points_at_the_first_one() -> None:
    episodes = [
        episode(0, 876, ("a",)),
        episode(1, 889, ("b",)),
        episode(2, 876, ("a",)),
    ]

    _mark_duplicates(episodes)

    assert [item["duplicate_of"] for item in episodes] == [None, None, 0]


def test_two_takes_that_merely_ran_the_same_length_are_not_copies() -> None:
    episodes = [episode(0, 876, ("a",)), episode(1, 876, ("b",))]

    _mark_duplicates(episodes)

    assert [item["duplicate_of"] for item in episodes] == [None, None]


def test_an_episode_without_statistics_claims_nothing() -> None:
    episodes = [episode(0, 876, None), episode(1, 876, None)]

    _mark_duplicates(episodes)

    assert [item["duplicate_of"] for item in episodes] == [None, None]


def test_the_working_fields_do_not_reach_the_page() -> None:
    episodes = [episode(0, 876, ("a",))]

    _mark_duplicates(episodes)

    assert "_action_signature" not in episodes[0]
    assert "_state_signature" not in episodes[0]
