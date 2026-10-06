"""
Publish local ablation datasets into the static dashboard data folder.

Dataset layout (self-contained under results/<id>/):
  results/<id>/ablation_results.json
  results/<id>/*_trace.jsonl

Published to:
  web/public/data/<id>/...
  web/public/data/index.json
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from harnessdiff.sanitize import scrub_jsonl_line, scrub_value

DEFAULT_RESULTS_ROOT = Path("results")
DEFAULT_WEB_DATA = Path("web/public/data")

_DATASET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def dataset_id_from_path(path: Path) -> str:
    """Derive a stable dataset id from an output directory name."""
    name = path.name.strip() or "mock"
    name = name.replace(" ", "-")
    if not _DATASET_ID_RE.match(name):
        name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "dataset"
    return name


def discover_datasets(results_root: Path = DEFAULT_RESULTS_ROOT) -> List[Dict[str, Any]]:
    """
    Find self-contained datasets under results/.

    Accepts:
      results/<id>/ablation_results.json         -> id from folder name (preferred)
      results/ablation_results.json              -> id "mock" (legacy flat layout,
                                                   only if results/mock/ is absent)
    """
    results_root = Path(results_root)
    found: List[Dict[str, Any]] = []

    if not results_root.exists():
        return found

    subdirs: List[Dict[str, Any]] = []
    for child in sorted(results_root.iterdir()):
        if not child.is_dir():
            continue
        results_file = child / "ablation_results.json"
        if results_file.is_file():
            ds_id = dataset_id_from_path(child)
            subdirs.append(_describe_dataset(ds_id, child, results_file))

    if subdirs:
        return subdirs

    # Legacy flat layout: results/ablation_results.json + traces alongside
    flat = results_root / "ablation_results.json"
    if flat.is_file():
        found.append(_describe_dataset("mock", results_root, flat))

    return found


def _describe_dataset(ds_id: str, source_dir: Path, results_file: Path) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "id": ds_id,
        "label": _label_for(ds_id),
        "source_dir": str(source_dir),
        "results_file": str(results_file),
        "is_mock": ds_id == "mock",
    }
    try:
        with open(results_file, encoding="utf-8") as f:
            payload = json.load(f)
        meta["timestamp"] = payload.get("timestamp")
        model_info = payload.get("model") or {}
        meta["model"] = model_info
        if model_info.get("display_name"):
            meta["label"] = model_info["display_name"]
        elif model_info.get("spec"):
            meta["label"] = model_info["spec"]
        summary = payload.get("summary") or {}
        if summary:
            final = list(summary.values())[-1]
            meta["final_success_rate"] = final.get("real_success_rate")
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return meta


def _label_for(ds_id: str) -> str:
    if ds_id == "mock":
        return "Mock model"
    return ds_id.replace("-", " ").replace("_", " ")


def publish_datasets(
    results_root: Path = DEFAULT_RESULTS_ROOT,
    web_data: Path = DEFAULT_WEB_DATA,
    dataset_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Copy discovered datasets into web/public/data/ and write index.json.

    Returns a summary of what was published.
    """
    results_root = Path(results_root)
    web_data = Path(web_data)
    web_data.mkdir(parents=True, exist_ok=True)

    discovered = discover_datasets(results_root)
    if dataset_ids:
        wanted = set(dataset_ids)
        discovered = [d for d in discovered if d["id"] in wanted]

    published: List[Dict[str, Any]] = []
    for ds in discovered:
        dest = web_data / ds["id"]
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)

        # Results JSON (scrubbed)
        with open(ds["results_file"], encoding="utf-8") as f:
            payload = json.load(f)
        payload = scrub_value(payload)
        # Ensure model metadata is present for the dashboard
        payload.setdefault("model", ds.get("model") or {})
        if not payload["model"]:
            payload["model"] = {
                "spec": "mock" if ds["is_mock"] else ds["id"],
                "display_name": ds["label"],
                "provider": "mock" if ds["is_mock"] else "unknown",
            }
        payload["dataset_id"] = ds["id"]

        with open(dest / "ablation_results.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # Traces: prefer baseline + final for dashboard; copy all jsonl as self-contained
        source_dir = Path(ds["source_dir"])
        for trace in sorted(source_dir.glob("*_trace.jsonl")):
            # Skip intermediate layers to keep publish slim; keep baseline + last layer
            name = trace.name
            if name.startswith("baseline_") or name.startswith("layer_verification_"):
                _copy_scrubbed_jsonl(trace, dest / name)
            elif ds["is_mock"] is False:
                # Real-model datasets: also keep full set if small; still scrub
                # Intermediate layers optional — include for completeness of self-contained dir
                if name.startswith("layer_"):
                    _copy_scrubbed_jsonl(trace, dest / name)

        # For mock, only baseline + verification (dashboard needs those)
        # Already handled above.

        entry = {
            "id": ds["id"],
            "label": ds["label"],
            "is_mock": ds["is_mock"],
            "path": f"/data/{ds['id']}",
            "timestamp": payload.get("timestamp"),
            "model": payload.get("model"),
            "final_success_rate": ds.get("final_success_rate"),
        }
        published.append(entry)

    # Preserve any already-published datasets under web_data that weren't in results/
    # only if we published at least the mock from results; still rewrite index from disk
    index_entries = _index_from_disk(web_data)
    # Prefer freshly published metadata when ids overlap
    by_id = {e["id"]: e for e in index_entries}
    for e in published:
        by_id[e["id"]] = e
    index = {
        "datasets": sorted(
            by_id.values(),
            key=lambda d: (0 if d.get("is_mock") else 1, d.get("label") or d["id"]),
        )
    }
    with open(web_data / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    return {"published": published, "index": index}


def _copy_scrubbed_jsonl(src: Path, dest: Path) -> None:
    with open(src, encoding="utf-8") as fin, open(dest, "w", encoding="utf-8") as fout:
        for line in fin:
            scrubbed = scrub_jsonl_line(line)
            if scrubbed:
                fout.write(scrubbed + "\n")


def _index_from_disk(web_data: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not web_data.exists():
        return entries
    for child in sorted(web_data.iterdir()):
        if not child.is_dir():
            continue
        results_file = child / "ablation_results.json"
        if not results_file.is_file():
            continue
        ds_id = child.name
        entry: Dict[str, Any] = {
            "id": ds_id,
            "label": _label_for(ds_id),
            "is_mock": ds_id == "mock",
            "path": f"/data/{ds_id}",
        }
        try:
            with open(results_file, encoding="utf-8") as f:
                payload = json.load(f)
            entry["timestamp"] = payload.get("timestamp")
            entry["model"] = payload.get("model")
            if payload.get("model", {}).get("display_name"):
                entry["label"] = payload["model"]["display_name"]
            summary = payload.get("summary") or {}
            if summary:
                entry["final_success_rate"] = list(summary.values())[-1].get("real_success_rate")
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        entries.append(entry)
    return entries
