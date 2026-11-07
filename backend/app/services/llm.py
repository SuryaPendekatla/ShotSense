"""LLM layer: turns classified shots into a shot breakdown and video-generation prompts.

Works with Anthropic or OpenAI (vision optional). With no API key, or if the call fails,
a deterministic template breakdown is produced so the app always returns a result.
"""
import json
import logging
import re
from dataclasses import dataclass

import httpx

from ..config import Settings
from .labels import label_info

log = logging.getLogger("shotsense")


@dataclass
class ShotFacts:
    index: int
    start_sec: float
    end_sec: float
    label: str
    confidence: float
    thumbnail: str  # JPEG data URL


@dataclass
class Breakdown:
    summary: str
    pacing: str
    descriptions: dict[int, str]
    prompts: dict[int, str]
    source: str  # "anthropic" | "openai" | "template"


SYSTEM_PROMPT = """You are an experienced cinematographer and AI-video prompt writer.
You receive a list of shots from a video, each with timecodes and a shot-scale label
predicted by a computer-vision model, sometimes with the key frame image.
Return ONLY a JSON object, no prose, with this shape:
{
  "summary": "2-3 sentences on the visual style and how the framing choices serve the piece",
  "pacing": "1-2 sentences on rhythm and cutting, using the shot durations",
  "shots": [
    {"index": 1,
     "description": "one sentence: what is in frame and what this framing does narratively",
     "prompt": "a detailed text-to-video prompt (40-80 words) that recreates this shot: subject, action, shot scale, lens, camera movement, lighting, mood, colour palette, duration"}
  ]
}
Include every shot index you were given. Keep the predicted shot scale in each prompt
unless the image clearly contradicts it, in which case say so in the description."""


def _fmt_time(sec: float) -> str:
    m, s = divmod(sec, 60)
    return f"{int(m):02d}:{s:05.2f}"


def _stats(shots: list[ShotFacts]) -> tuple[str, str]:
    durations = [max(0.0, s.end_sec - s.start_sec) for s in shots]
    total = sum(durations)
    avg = total / len(shots) if shots else 0.0
    counts: dict[str, int] = {}
    for s in shots:
        counts[s.label] = counts.get(s.label, 0) + 1
    top_label, top_n = max(counts.items(), key=lambda kv: kv[1])
    share = round(100 * top_n / len(shots))
    if len(shots) == 1:
        summary = f"A single frame classified as a {label_info(top_label)['name'].lower()}."
        return summary, "Single still image, so there is no cutting rhythm to analyse."
    summary = (f"{len(shots)} shots covering {total:.1f}s of footage. The dominant framing is "
               f"{label_info(top_label)['name'].lower()} ({share}% of shots), across "
               f"{len(counts)} distinct shot scales.")
    if avg < 2:
        feel = "fast, trailer-like cutting that keeps energy high"
    elif avg < 5:
        feel = "brisk cutting typical of commercials and music videos"
    elif avg < 10:
        feel = "measured pacing that gives each shot room to land"
    else:
        feel = "slow, contemplative pacing with long takes"
    return summary, f"Average shot length is {avg:.1f}s: {feel}."


def template_breakdown(shots: list[ShotFacts], notes: str = "") -> Breakdown:
    summary, pacing = _stats(shots)
    style = f" Project style: {notes.strip().rstrip('.')}." if notes.strip() else ""
    descriptions, prompts = {}, {}
    for s in shots:
        info = label_info(s.label)
        dur = max(1.0, round(s.end_sec - s.start_sec, 1))
        descriptions[s.index] = info["use"]
        prompts[s.index] = (
            f"{info['name']} with the same subject, composition and setting as the reference frame, "
            f"{info['lens'] or 'natural lens'}.{style} Soft cinematic lighting, subtle camera movement, "
            f"filmic colour grade, 24fps, {dur:g} seconds.")
    return Breakdown(summary, pacing, descriptions, prompts, "template")


def _user_text(shots: list[ShotFacts], notes: str, with_images: bool) -> str:
    lines = []
    if notes.strip():
        lines.append(f"Creator's notes about this project: {notes.strip()}")
    lines.append("Shots:")
    for s in shots:
        info = label_info(s.label)
        lines.append(f"- Shot {s.index}: {_fmt_time(s.start_sec)}-{_fmt_time(s.end_sec)} "
                     f"({s.end_sec - s.start_sec:.1f}s), predicted {info['name']} ({info['abbr']}), "
                     f"confidence {s.confidence:.0%}")
    if with_images:
        lines.append("Key frames follow in shot order, each preceded by its shot number.")
    return "\n".join(lines)


def _split_data_url(url: str) -> tuple[str, str]:
    header, data = url.split(",", 1)
    media_type = header.split(";")[0].removeprefix("data:") or "image/jpeg"
    return media_type, data


def _call_anthropic(settings: Settings, shots: list[ShotFacts], notes: str) -> str:
    content: list[dict] = [{"type": "text", "text": _user_text(shots, notes, settings.llm_vision)}]
    if settings.llm_vision:
        for s in shots:
            media_type, data = _split_data_url(s.thumbnail)
            content.append({"type": "text", "text": f"Shot {s.index}:"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}})
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": settings.anthropic_model, "max_tokens": 8000, "system": SYSTEM_PROMPT,
              "messages": [{"role": "user", "content": content}]},
        timeout=settings.llm_timeout_seconds,
    )
    resp.raise_for_status()
    return "".join(block.get("text", "") for block in resp.json()["content"] if block.get("type") == "text")


def _call_openai(settings: Settings, shots: list[ShotFacts], notes: str) -> str:
    content: list[dict] = [{"type": "text", "text": _user_text(shots, notes, settings.llm_vision)}]
    if settings.llm_vision:
        for s in shots:
            content.append({"type": "text", "text": f"Shot {s.index}:"})
            content.append({"type": "image_url", "image_url": {"url": s.thumbnail, "detail": "low"}})
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json={"model": settings.openai_model, "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                           {"role": "user", "content": content}]},
        timeout=settings.llm_timeout_seconds,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_llm_json(text: str) -> dict:
    """Extract the JSON object from a model reply, tolerating code fences or stray prose."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object in LLM reply")
    return json.loads(text[start:end + 1])


def resolve_provider(settings: Settings) -> str | None:
    provider = settings.llm_provider.lower()
    if provider == "anthropic" and settings.anthropic_api_key:
        return "anthropic"
    if provider == "openai" and settings.openai_api_key:
        return "openai"
    if provider == "auto":
        if settings.anthropic_api_key:
            return "anthropic"
        if settings.openai_api_key:
            return "openai"
    return None


def build_breakdown(settings: Settings, shots: list[ShotFacts], notes: str = "") -> Breakdown:
    fallback = template_breakdown(shots, notes)
    provider = resolve_provider(settings)
    if provider is None:
        return fallback
    subset = shots[: settings.llm_max_shots]
    try:
        raw = _call_anthropic(settings, subset, notes) if provider == "anthropic" else _call_openai(settings, subset, notes)
        data = parse_llm_json(raw)
    except Exception as exc:  # noqa: BLE001 - never fail an analysis because of the LLM
        log.warning("LLM breakdown failed (%s); using template breakdown.", exc)
        return fallback

    descriptions, prompts = dict(fallback.descriptions), dict(fallback.prompts)
    for item in data.get("shots", []):
        try:
            idx = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if idx in descriptions:
            if str(item.get("description", "")).strip():
                descriptions[idx] = str(item["description"]).strip()
            if str(item.get("prompt", "")).strip():
                prompts[idx] = str(item["prompt"]).strip()
    summary = str(data.get("summary") or "").strip()
    pacing = str(data.get("pacing") or "").strip()
    return Breakdown(
        summary=f"{fallback.summary} {summary}".strip() if summary else fallback.summary,
        pacing=pacing or fallback.pacing,
        descriptions=descriptions,
        prompts=prompts,
        source=provider,
    )
