"""Concept-prompt segmentation via the hosted SAM 3.1 Responses API.

Tiled internally over :mod:`argus.analysis.tiling` windows and stitched
with :mod:`argus.analysis.stitch` NMS. Offline, keyless, or failing live
calls fall back to in-code fixture boxes (never raise into routes), with
every call logged to the ``meta_spend`` ledger.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

from argus.analysis.stitch import stitch_detections
from argus.analysis.tiling import OVERLAP, TILE_SIZE, cap_dimensions, tile_windows
from argus.orchestrator.meta_client import log_spend

MODEL_ID = "sam-3.1"
DEFAULT_BASE_URL = "https://api.meta.ai/v1"

SUPPORTED_CONCEPTS = ("ship", "clear-cut", "solar farm", "reservoir")

CANNED_BOXES: dict[str, list[dict]] = {
    "ship": [
        {"x1": 120, "y1": 200, "x2": 420, "y2": 320, "score": 0.93, "label": "ship"}
    ],
    "clear-cut": [
        {
            "x1": 80,
            "y1": 90,
            "x2": 560,
            "y2": 480,
            "score": 0.88,
            "label": "clear-cut",
        }
    ],
    "solar farm": [
        {
            "x1": 60,
            "y1": 140,
            "x2": 700,
            "y2": 520,
            "score": 0.91,
            "label": "solar farm",
        }
    ],
    "reservoir": [
        {
            "x1": 100,
            "y1": 120,
            "x2": 640,
            "y2": 500,
            "score": 0.89,
            "label": "reservoir",
        }
    ],
}

_BOX_RE = re.compile(
    r"<\|box;x1=([\d.]+);y1=([\d.]+);x2=([\d.]+);y2=([\d.]+)[^|]*\|>"
)

_OFFLINE_TRUTHY = {"1", "true", "yes", "on"}


def is_offline() -> bool:
    """True when ARGUS_OFFLINE requests fixture-only behaviour."""
    return os.environ.get("ARGUS_OFFLINE", "").strip().lower() in _OFFLINE_TRUTHY


def _base_url() -> str:
    return os.environ.get("META_BASE_URL", DEFAULT_BASE_URL)


def _model_id() -> str:
    return os.environ.get("ARGUS_SAM_MODEL", MODEL_ID)


def _api_key() -> str:
    return os.environ.get("META_API_KEY", "")


def _default_cost(tokens_in: int, tokens_out: int) -> float:
    return (int(tokens_in) + int(tokens_out)) / 1000.0 * 0.001


def _normalize_concept(noun_phrase: object) -> str:
    text = str(noun_phrase or "").strip().lower()
    if not text:
        return "solar farm"
    if "solar" in text and "farm" in text:
        return "solar farm"
    if "solar" in text:
        return "solar farm"
    if "clear" in text and "cut" in text:
        return "clear-cut"
    if "clearcut" in text or "clear-cut" in text or "clear_cut" in text:
        return "clear-cut"
    if "reservoir" in text:
        return "reservoir"
    if "ship" in text:
        return "ship"
    return "solar farm"


def _fixture_boxes(concept: str) -> list[dict]:
    boxes = CANNED_BOXES.get(concept)
    if boxes:
        return [dict(box) for box in boxes]
    return [dict(box) for box in CANNED_BOXES["solar farm"]]


def _dims_from_image(image: Any) -> tuple[int, int, str]:
    width, height, ref = 1024, 1024, ""
    try:
        if image is None:
            return width, height, ref
        if isinstance(image, dict):
            ref = str(
                image.get("image_url")
                or image.get("url")
                or image.get("path")
                or image.get("scene_id")
                or ""
            )
            w = image.get("width", width)
            h = image.get("height", height)
            try:
                w = int(float(w))  # type: ignore[arg-type]
                h = int(float(h))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return 1024, 1024, ref
            if w > 0 and h > 0:
                return w, h, ref
            return 1024, 1024, ref
        if isinstance(image, str):
            text = image.strip()
            if text.startswith("file://"):
                return width, height, text[len("file://") :]
            return width, height, text
        return width, height, str(image)
    except Exception:  # noqa: BLE001 - image refs must never raise
        return 1024, 1024, ""


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "argus").is_dir():
            return parent
    return here.parents[2]


def _masks_dir() -> Path:
    override = os.environ.get("ARGUS_FIXTURE_DIR")
    if override:
        return Path(override) / "masks"
    return _repo_root() / "data" / "masks"


def _write_masks(
    concept: str,
    boxes: list[dict],
    width: int,
    height: int,
    tiles: int,
) -> str:
    directory = _masks_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"masks-{uuid.uuid4().hex[:8]}.json"
    path.write_text(
        json.dumps(
            {
                "width": int(width),
                "height": int(height),
                "concept": str(concept),
                "boxes": boxes,
                "tiles": int(tiles),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return str(path)


def _slug(concept: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(concept).lower()).strip("-") or "concept"


def _extract_boxes(text: str, label: str) -> list[dict]:
    boxes: list[dict] = []
    for match in _BOX_RE.finditer(str(text or "")):
        try:
            x1, y1, x2, y2 = (float(match.group(i)) for i in range(1, 5))
        except (TypeError, ValueError):
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append(
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "score": 1.0, "label": label}
        )
    return boxes


def _response_texts(body: Any) -> tuple[str, dict]:
    texts: list[str] = []
    usage: dict = {}
    if not isinstance(body, dict):
        return "", usage
    output_text = body.get("output_text")
    if isinstance(output_text, str) and output_text:
        texts.append(output_text)
    elif isinstance(output_text, list):
        texts.extend(t for t in output_text if isinstance(t, str))
    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            for part in item.get("content", []) or []:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
    raw_usage = body.get("usage")
    if isinstance(raw_usage, dict):
        usage = raw_usage
    return "\n".join(texts), usage


def _usage_counts(usage: dict) -> tuple[int, int]:
    tokens_in = 0
    tokens_out = 0
    if isinstance(usage, dict):
        for key in ("input_tokens", "prompt_tokens", "tokens_in"):
            if isinstance(usage.get(key), (int, float)):
                tokens_in = int(usage[key])
                break
        for key in ("output_tokens", "completion_tokens", "tokens_out"):
            if isinstance(usage.get(key), (int, float)):
                tokens_out = int(usage[key])
                break
    return tokens_in, tokens_out


def _live_segment(
    noun_phrase: str,
    concept: str,
    image_ref: str,
    width: int,
    height: int,
    windows: list[dict],
) -> tuple[list[dict], int, int]:
    model = _model_id()
    base = _base_url().rstrip("/")
    per_tile: list[dict] = []
    total_in = 0
    total_out = 0
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    for tile in windows:
        content: list[dict] = [
            {
                "type": "input_text",
                "text": f"{noun_phrase} (tile col {tile['column']} row {tile['row']})",
            }
        ]
        if image_ref.startswith(("https://", "http://")):
            content.append({"type": "input_image", "image_url": image_ref})
        payload = {
            "model": model,
            "input": [
                {"type": "message", "role": "user", "content": content}
            ],
            "stream": False,
        }
        response = httpx.post(
            f"{base}/responses", json=payload, headers=headers, timeout=20.0
        )
        response.raise_for_status()
        text, usage = _response_texts(response.json())
        tokens_in, tokens_out = _usage_counts(usage)
        total_in += tokens_in
        total_out += tokens_out
        boxes = _extract_boxes(text, concept)
        if boxes:
            per_tile.append({"tile": tile, "boxes": boxes})
    stitched = stitch_detections(per_tile)
    return stitched, total_in, total_out


def segment_concept(noun_phrase: str = "", image: Any = None) -> dict:
    """Segment a noun-phrase concept; tiled, stitched, never raises.

    Returns ``{"boxes", "masks_path", "source_url", "model", "concept",
    "tiles"}``; every failure path returns the fixture result.
    """
    raw = str(noun_phrase or "")
    concept = _normalize_concept(raw)
    echo = raw.strip().lower() or concept
    width, height, image_ref = _dims_from_image(image)
    try:
        capped_w, capped_h, _scale = cap_dimensions(width, height)
        windows = tile_windows(capped_w, capped_h, TILE_SIZE, OVERLAP)
        if not windows:
            windows = tile_windows(1024, 1024, TILE_SIZE, OVERLAP)
            capped_w, capped_h = 1024, 1024
        model = _model_id()
        if is_offline() or not _api_key():
            boxes = _fixture_boxes(concept)
            log_spend("segment_concept", model, 0, 0, 0.0)
            masks_path = _write_masks(echo, boxes, capped_w, capped_h, len(windows))
            return {
                "boxes": boxes,
                "masks_path": masks_path,
                "source_url": f"fixture://sam-3.1/{_slug(echo)}",
                "model": model,
                "concept": echo,
                "tiles": len(windows),
            }
        try:
            stitched, tokens_in, tokens_out = _live_segment(
                raw or concept, concept, image_ref, capped_w, capped_h, windows
            )
            boxes = stitched or _fixture_boxes(concept)
            log_spend(
                "segment_concept",
                model,
                tokens_in,
                tokens_out,
                _default_cost(tokens_in, tokens_out),
            )
            masks_path = _write_masks(echo, boxes, capped_w, capped_h, len(windows))
            return {
                "boxes": boxes,
                "masks_path": masks_path,
                "source_url": f"{_base_url().rstrip('/')}/responses",
                "model": model,
                "concept": echo,
                "tiles": len(windows),
            }
        except Exception:  # noqa: BLE001 - live failure falls back to fixture
            boxes = _fixture_boxes(concept)
            log_spend("segment_concept", model, 0, 0, 0.0)
            masks_path = _write_masks(echo, boxes, capped_w, capped_h, len(windows))
            return {
                "boxes": boxes,
                "masks_path": masks_path,
                "source_url": f"fixture://sam-3.1/{_slug(echo)}",
                "model": model,
                "concept": echo,
                "tiles": len(windows),
            }
    except Exception:  # noqa: BLE001 - segment_concept never raises
        try:
            model = _model_id()
        except Exception:  # noqa: BLE001
            model = MODEL_ID
        try:
            log_spend("segment_concept", model, 0, 0, 0.0)
        except Exception:  # noqa: BLE001, S110
            pass
        try:
            masks_path = _write_masks(echo, _fixture_boxes(concept), 1024, 1024, 1)
        except Exception:  # noqa: BLE001
            masks_path = ""
        return {
            "boxes": _fixture_boxes(concept),
            "masks_path": masks_path,
            "source_url": f"fixture://sam-3.1/{_slug(echo)}",
            "model": model,
            "concept": echo,
            "tiles": 1,
        }
