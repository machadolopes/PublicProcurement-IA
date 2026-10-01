"""Depósito Zenodo via API (requer token pessoal).

1. Crie um token em https://zenodo.org/account/settings/applications/tokens/new/
   (escopos deposit:write e deposit:actions).
2. PowerShell:
     $env:ZENODO_TOKEN = "...."
     python scripts/deposit_zenodo.py

Publica o ZIP em deposit/PublicProcurement-IA-data-v0.1.0.zip e grava o DOI em config.yaml.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / "deposit" / "PublicProcurement-IA-data-v0.1.0.zip"
META = ROOT / ".zenodo.json"
CONFIG = ROOT / "config.yaml"
BASE = os.environ.get("ZENODO_BASE", "https://zenodo.org/api")


def main() -> int:
    token = os.environ.get("ZENODO_TOKEN", "").strip()
    if not token:
        print("Defina ZENODO_TOKEN (token pessoal do Zenodo).", file=sys.stderr)
        return 2
    if not ZIP.is_file():
        print(f"ZIP em falta: {ZIP}", file=sys.stderr)
        return 2
    meta = json.loads(META.read_text(encoding="utf-8"))
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=BASE, headers=headers, timeout=300.0) as client:
        r = client.post("/deposit/depositions", json={})
        r.raise_for_status()
        dep = r.json()
        deposition_id = dep["id"]
        bucket = dep["links"]["bucket"]
        print(f"Deposition {deposition_id}")

        with ZIP.open("rb") as handle:
            put = client.put(
                f"{bucket}/{ZIP.name}",
                content=handle,
                headers={**headers, "Content-Type": "application/octet-stream"},
            )
        put.raise_for_status()
        print(f"Uploaded {ZIP.name} ({ZIP.stat().st_size} bytes)")

        meta_body = {"metadata": meta}
        m = client.put(f"/deposit/depositions/{deposition_id}", json=meta_body)
        m.raise_for_status()

        pub = client.post(f"/deposit/depositions/{deposition_id}/actions/publish")
        pub.raise_for_status()
        record = pub.json()
        doi = record.get("doi") or record.get("metadata", {}).get("prereserve_doi", {}).get("doi")
        html = record.get("links", {}).get("html", "")
        print(f"DOI: {doi}")
        print(f"Record: {html}")

        if doi and CONFIG.is_file():
            text = CONFIG.read_text(encoding="utf-8")
            if 'doi: ""' in text:
                CONFIG.write_text(text.replace('doi: ""', f'doi: "{doi}"'), encoding="utf-8")
                print("config.yaml atualizado.")
            else:
                print("Atualize config.yaml manualmente com o DOI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
