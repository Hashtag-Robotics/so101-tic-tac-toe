from __future__ import annotations

import re
from html import unescape
from typing import Literal

from pydantic import Field, model_validator

from hashtag_robotics.models import StrictModel

TAG = re.compile(r"<[^>]+>")
GAME = re.compile(
    r'<details\s+class="game"[^>]*>(.*?)</details>',
    re.DOTALL | re.IGNORECASE,
)
EPISODE = re.compile(
    r'<label\s+class="ep"[^>]*>(.*?)</label>',
    re.DOTALL | re.IGNORECASE,
)


class RecordingPlanParseRequest(StrictModel):
    source_name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=2_000_000)


class PlannedEpisode(StrictModel):
    global_episode: int = Field(ge=1)
    game: int = Field(ge=1)
    block: str = Field(min_length=1, max_length=16)
    instruction: str = Field(min_length=1, max_length=500)
    board_before: str = Field(pattern=r"^[XO.]{3}/[XO.]{3}/[XO.]{3}$")
    after: Literal["undo", "leave"]
    piece: str = Field(min_length=1, max_length=16)
    target_cell: str = Field(min_length=1, max_length=32)


class RecordingGame(StrictModel):
    game: int = Field(ge=1)
    block: str = Field(min_length=1, max_length=16)
    reset_instruction: str
    episodes: list[PlannedEpisode] = Field(min_length=1)

    @model_validator(mode="after")
    def ordered_episode_ids(self) -> RecordingGame:
        ids = [episode.global_episode for episode in self.episodes]
        if ids != list(range(ids[0], ids[0] + len(ids))):
            raise ValueError(f"Game {self.game} episode ids are not consecutive: {ids}")
        return self


class RecordingRoadmap(StrictModel):
    source_name: str
    games: list[RecordingGame] = Field(min_length=1)
    total_episodes: int = Field(ge=1)

    @model_validator(mode="after")
    def globally_ordered(self) -> RecordingRoadmap:
        ids = [episode.global_episode for game in self.games for episode in game.episodes]
        if len(ids) != len(set(ids)):
            raise ValueError("The roadmap contains duplicate global episode ids.")
        if ids != sorted(ids):
            raise ValueError("The roadmap games are not in global episode order.")
        if self.total_episodes != len(ids):
            raise ValueError("The roadmap total does not match its episode rows.")
        return self


class RecordingPlanError(ValueError):
    pass


def parse_recording_roadmap(source_name: str, content: str) -> RecordingRoadmap:
    """Extract the executable X/O plan from the roadmap's semantic HTML."""
    games: list[RecordingGame] = []
    for game_match in GAME.finditer(content):
        fragment = game_match.group(1)
        game_number = _required_int(fragment, r'<span\s+class="gname">\s*Oyun\s+(\d+)')
        block = _required_text(fragment, r'<span\s+class="grange">\s*blok\s+([^·<]+)')
        reset = _optional_text(fragment, r'<div\s+class="reset-note">(.*?)</div>')
        episodes = [
            _parse_episode(row.group(1), game_number, block) for row in EPISODE.finditer(fragment)
        ]
        if not episodes:
            raise RecordingPlanError(f"Oyun {game_number} içinde episode bulunamadı.")
        games.append(
            RecordingGame(
                game=game_number,
                block=block,
                reset_instruction=reset,
                episodes=episodes,
            )
        )

    if not games:
        raise RecordingPlanError("HTML içinde details.game kayıt planı bulunamadı.")
    try:
        return RecordingRoadmap(
            source_name=source_name,
            games=games,
            total_episodes=sum(len(game.episodes) for game in games),
        )
    except ValueError as error:
        raise RecordingPlanError(str(error)) from error


def _parse_episode(fragment: str, game: int, block: str) -> PlannedEpisode:
    global_episode = _required_int(fragment, r'<input[^>]+data-id="(\d+)"')
    instruction = _required_text(
        fragment,
        r'<button\s+class="cmdline"[^>]*>(.*?)</button>',
    )
    board_html = _required_raw(fragment, r'<div\s+class="mb">(.*?)</div>')
    cells = re.findall(r'<i\s+class="([^"]*)"', board_html, re.IGNORECASE)
    if len(cells) != 9:
        raise RecordingPlanError(
            f"Episode {global_episode:03d} mini tahtasında 9 yerine {len(cells)} hücre var."
        )
    board = ["X" if "x" in cell.split() else "O" if "o" in cell.split() else "." for cell in cells]
    board_before = "/".join("".join(board[index : index + 3]) for index in range(0, 9, 3))

    after = "undo" if re.search(r'class="[^"]*\bundo\b', fragment) else "leave"
    piece_match = re.search(
        r'class="chip\s+cube"[^>]*>.*?</span>\s*([XO])\s*([1-9])\b',
        fragment,
        re.DOTALL | re.IGNORECASE,
    )
    if piece_match is None:
        raise RecordingPlanError(f"Episode {global_episode:03d} taş/hedef kodu okunamadı.")
    piece = "red X" if piece_match.group(1) == "X" else "white O"
    target_cell = _target_from_instruction(instruction)
    return PlannedEpisode(
        global_episode=global_episode,
        game=game,
        block=block,
        instruction=instruction,
        board_before=board_before,
        after=after,
        piece=piece,
        target_cell=target_cell,
    )


def _target_from_instruction(instruction: str) -> str:
    match = re.search(
        r"\b(?:the\s+)?((?:top|middle|bottom)\s+(?:left|center|right))\s+cell\b", instruction
    )
    if match is None:
        raise RecordingPlanError(f"Komuttan hedef hücre okunamadı: {instruction}")
    return match.group(1)


def _clean(value: str) -> str:
    return " ".join(unescape(TAG.sub(" ", value)).split())


def _required_raw(fragment: str, pattern: str) -> str:
    match = re.search(pattern, fragment, re.DOTALL | re.IGNORECASE)
    if match is None:
        raise RecordingPlanError(f"Roadmap alanı bulunamadı: {pattern}")
    return match.group(1)


def _required_text(fragment: str, pattern: str) -> str:
    value = _clean(_required_raw(fragment, pattern))
    if not value:
        raise RecordingPlanError(f"Roadmap alanı boş: {pattern}")
    return value


def _optional_text(fragment: str, pattern: str) -> str:
    match = re.search(pattern, fragment, re.DOTALL | re.IGNORECASE)
    return _clean(match.group(1)) if match else ""


def _required_int(fragment: str, pattern: str) -> int:
    return int(_required_raw(fragment, pattern))
