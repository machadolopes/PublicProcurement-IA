"""Gravação do bruto, do JSONL e do manifest. O hash é do corpo HTTP."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw_root = root / "data" / "raw"
        self.raw_root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.raw_root / "manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return {
                "schema_version": 1,
                "files": [],
                "total_records_in_jsonl": 0,
            }
        with self.manifest_path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def page_dir(self, modalidade: int, data_inicial: str, data_final: str) -> Path:
        directory = (
            self.raw_root
            / "contratacoes"
            / "publicacao"
            / f"m{modalidade:02d}"
            / f"{data_inicial}_{data_final}"
        )
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def page_path(self, modalidade: int, data_inicial: str, data_final: str, pagina: int) -> Path:
        return self.page_dir(modalidade, data_inicial, data_final) / f"page-{pagina:05d}.json"

    def write_page(self, path: Path, body: bytes) -> str:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(body)
        temporary.replace(path)
        return sha256_bytes(path.read_bytes())

    def append_jsonl(self, jsonl_path: Path, records: list[Any]) -> int:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_path.open("a", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
                handle.write("\n")
        return len(records)

    def remember(
        self,
        relative_path: str,
        digest: str,
        nbytes: int,
        records: int,
        http_status: int,
    ) -> None:
        files = self._manifest.setdefault("files", [])
        files[:] = [item for item in files if item.get("path") != relative_path]
        files.append(
            {
                "path": relative_path,
                "sha256": digest,
                "bytes": nbytes,
                "records": records,
                "http_status": http_status,
                "written_at": utc_now(),
            }
        )
        self._manifest["total_records_in_jsonl"] = sum(item["records"] for item in files)
        self._manifest["updated_at"] = utc_now()
        self.flush()

    def flush(self) -> None:
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self._manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.manifest_path)

    def checkpoint_path(self, page_directory: Path) -> Path:
        return page_directory / "checkpoint.json"

    def read_checkpoint(self, page_directory: Path) -> dict[str, Any] | None:
        path = self.checkpoint_path(page_directory)
        if not path.is_file():
            return None
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def write_checkpoint(self, page_directory: Path, payload: dict[str, Any]) -> None:
        path = self.checkpoint_path(page_directory)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
