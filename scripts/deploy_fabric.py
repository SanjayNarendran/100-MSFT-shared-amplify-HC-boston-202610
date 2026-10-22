#!/usr/bin/env python3
"""Deploy the CMS hospital quality demo into a Microsoft Fabric workspace.

Given the name of an existing Fabric workspace, this script:
  1. creates a lakehouse                           (step: lakehouse)
  2. uploads data/<DATASET>/*.csv to Files/raw/<DATASET>/ in the lakehouse,
     keeping the sub-folders                       (step: upload)
  3. creates a notebook that loads the raw CSVs into Delta tables  (step: notebook)
  4. runs the notebook                             (step: run)
  5. creates a Direct Lake semantic model          (step: model)
  6. checks the semantic model against expected row counts        (step: verify)

Every step is idempotent: re-running updates or skips what already exists.
No IDs are hard-coded; everything is looked up from the workspace name.

Authentication uses azure-identity DefaultAzureCredential (for example `az login`,
or the AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET environment variables).
"""
import argparse
import base64
import json
import sys
import time
from pathlib import Path

import requests
from azure.identity import DefaultAzureCredential
from azure.storage.filedatalake import DataLakeServiceClient

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
NOTEBOOK_FILE = REPO_ROOT / "notebooks" / "load_cms_tables.ipynb"
MODEL_DIR = REPO_ROOT / "semantic_model" / "CMS.SemanticModel"

FABRIC_API = "https://api.fabric.microsoft.com/v1"
POWERBI_API = "https://api.powerbi.com/v1.0/myorg"
ONELAKE_URL = "https://onelake.dfs.fabric.microsoft.com"
SCOPES = {
    "fabric": "https://api.fabric.microsoft.com/.default",
    "powerbi": "https://analysis.windows.net/powerbi/api/.default",
}

# Row counts the semantic model is expected to show for the data shipped in this repo.
EXPECTED_ROWS = {"PSI90": 23846, "HAI": 33800, "HCAHPS": 22440}
EXPECTED_MEASURE_COLUMNS = {"PSI90": 13, "HAI": 36, "HCAHPS": 21}

credential = DefaultAzureCredential()


def token(kind):
    return credential.get_token(SCOPES[kind]).token


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def request(method, url, scope="fabric", ok=(200, 201, 202, 204), **kwargs):
    """HTTP call with bearer token and throttling retry."""
    for _ in range(10):
        r = requests.request(
            method, url, headers={"Authorization": f"Bearer {token(scope)}"}, timeout=300, **kwargs
        )
        if r.status_code == 429:
            time.sleep(int(r.headers.get("Retry-After", 15)))
            continue
        break
    if r.status_code not in ok:
        raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text[:1500]}")
    return r


def wait_operation(r):
    """Follow a Fabric long running operation (HTTP 202) and return the final response."""
    if r.status_code != 202:
        return r
    location = r.headers["Location"]
    delay = int(r.headers.get("Retry-After", 5))
    while True:
        time.sleep(delay)
        s = request("GET", location)
        status = s.json().get("status")
        if status == "Succeeded":
            res = requests.get(
                location.rstrip("/") + "/result",
                headers={"Authorization": f"Bearer {token('fabric')}"},
                timeout=300,
            )
            return res if res.status_code == 200 else s
        if status in ("Failed", "Cancelled"):
            raise RuntimeError(f"Operation {status}: {s.text[:1500]}")
        delay = int(s.headers.get("Retry-After", 5))


def paged(url, key="value"):
    items, cont = [], None
    while True:
        r = request("GET", url + (("&" if "?" in url else "?") + f"continuationToken={cont}" if cont else ""))
        body = r.json()
        items += body.get(key, [])
        cont = body.get("continuationToken")
        if not cont:
            return items


# --------------------------------------------------------------------------- lookups
def find_workspace(name):
    matches = [w for w in paged(f"{FABRIC_API}/workspaces") if w["displayName"] == name]
    if not matches:
        sys.exit(f"Workspace '{name}' not found or you have no access to it.")
    if len(matches) > 1:
        sys.exit(f"More than one workspace is named '{name}'.")
    return matches[0]


def find_item(ws_id, item_type, name):
    for item in paged(f"{FABRIC_API}/workspaces/{ws_id}/items?type={item_type}"):
        if item["displayName"] == name:
            return item
    return None


# --------------------------------------------------------------------------- steps
def step_lakehouse(ws, args):
    lh = find_item(ws["id"], "Lakehouse", args.lakehouse)
    if lh:
        log(f"Lakehouse '{args.lakehouse}' already exists")
        return lh
    log(f"Creating lakehouse '{args.lakehouse}'")
    body = {"displayName": args.lakehouse, "description": "CMS HCAHPS, HAI and PSI hospital quality data"}
    for _ in range(15):
        try:
            return wait_operation(request("POST", f"{FABRIC_API}/workspaces/{ws['id']}/lakehouses", json=body)).json()
        except RuntimeError as e:
            if "ItemDisplayNameNotAvailableYet" not in str(e):
                raise
            time.sleep(20)
    raise RuntimeError("Lakehouse name did not become available")


def step_upload(ws, lh, args):
    files = sorted(DATA_DIR.glob("*/*.csv"))
    if not files:
        sys.exit(f"No CSV files found under {DATA_DIR}")
    with open(files[0], "rb") as fh:
        if fh.read(40).startswith(b"version https://git-lfs"):
            sys.exit("The CSV files are Git LFS pointers. Run 'git lfs pull' in the repository first.")
    service = DataLakeServiceClient(ONELAKE_URL, credential=credential)
    fs = service.get_file_system_client(ws["id"])
    log(f"Uploading {len(files)} files to Files/raw in the lakehouse")
    for path in files:
        target = f"{lh['id']}/Files/raw/{path.parent.name}/{path.name}"
        client = fs.get_file_client(target)
        size = path.stat().st_size
        try:
            if client.get_file_properties().size == size:
                log(f"  skip   raw/{path.parent.name}/{path.name} (already uploaded)")
                continue
        except Exception:
            pass
        log(f"  upload raw/{path.parent.name}/{path.name} ({size / 1e6:.0f} MB)")
        with open(path, "rb") as fh:
            client.upload_data(fh, overwrite=True, max_concurrency=4)


def b64(data):
    return base64.b64encode(data if isinstance(data, bytes) else data.encode("utf-8")).decode()


def upsert_item(ws_id, item_type, name, parts, fmt=None, description=None):
    definition = {"parts": [{"path": p, "payload": b64(c), "payloadType": "InlineBase64"} for p, c in parts]}
    if fmt:
        definition["format"] = fmt
    existing = find_item(ws_id, item_type, name)
    if existing:
        log(f"Updating {item_type} '{name}'")
        wait_operation(
            request("POST", f"{FABRIC_API}/workspaces/{ws_id}/items/{existing['id']}/updateDefinition", json={"definition": definition})
        )
        return existing
    log(f"Creating {item_type} '{name}'")
    body = {"displayName": name, "type": item_type, "definition": definition}
    if description:
        body["description"] = description
    return wait_operation(request("POST", f"{FABRIC_API}/workspaces/{ws_id}/items", json=body)).json()


def step_notebook(ws, lh, args):
    nb = json.loads(NOTEBOOK_FILE.read_text())
    nb.setdefault("metadata", {})["dependencies"] = {
        "lakehouse": {
            "default_lakehouse": lh["id"],
            "default_lakehouse_name": lh["displayName"],
            "default_lakehouse_workspace_id": ws["id"],
            "known_lakehouses": [{"id": lh["id"]}],
        }
    }
    item = upsert_item(
        ws["id"], "Notebook", args.notebook, [("notebook-content.ipynb", json.dumps(nb))], fmt="ipynb"
    )
    return item or find_item(ws["id"], "Notebook", args.notebook)


def step_run(ws, nb, args):
    log(f"Running notebook '{args.notebook}' (Spark start-up takes a few minutes)")
    r = request("POST", f"{FABRIC_API}/workspaces/{ws['id']}/items/{nb['id']}/jobs/instances?jobType=RunNotebook", json={})
    location = r.headers["Location"]
    while True:
        time.sleep(20)
        s = request("GET", location).json()
        log(f"  notebook status: {s.get('status')}")
        if s.get("status") == "Completed":
            return
        if s.get("status") in ("Failed", "Cancelled", "Deduped"):
            raise RuntimeError(f"Notebook run {s.get('status')}: {json.dumps(s.get('failureReason'))}")


def model_parts(ws, lh, args):
    parts = []
    for path in sorted(p for p in MODEL_DIR.rglob("*") if p.is_file()):
        text = path.read_text(encoding="utf-8")
        text = text.replace("__WORKSPACE_ID__", ws["id"]).replace("__LAKEHOUSE_ID__", lh["id"])
        text = text.replace("__MODEL_NAME__", args.model)
        parts.append((path.relative_to(MODEL_DIR).as_posix(), text))
    return parts


def step_model(ws, lh, args):
    item = upsert_item(ws["id"], "SemanticModel", args.model, model_parts(ws, lh, args), fmt="TMDL")
    model = item if item and "id" in item else find_item(ws["id"], "SemanticModel", args.model)
    log("Refreshing (framing) the Direct Lake model")
    base = f"{POWERBI_API}/groups/{ws['id']}/datasets/{model['id']}"
    request("POST", f"{base}/refreshes", scope="powerbi", json={"type": "full"})
    for _ in range(60):
        time.sleep(10)
        latest = request("GET", f"{base}/refreshes?$top=1", scope="powerbi").json()["value"]
        status = latest[0]["status"] if latest else "Unknown"
        log(f"  refresh status: {status}")
        if status == "Completed":
            return model
        if status == "Failed":
            raise RuntimeError(f"Model refresh failed: {latest[0].get('serviceExceptionJson')}")
    raise RuntimeError("Model refresh timed out")


def dax(ws, model, query):
    url = f"{POWERBI_API}/groups/{ws['id']}/datasets/{model['id']}/executeQueries"
    r = request("POST", url, scope="powerbi", json={"queries": [{"query": query}]})
    result = r.json()["results"][0]
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["tables"][0].get("rows", [])


def step_verify(ws, model, args):
    ok = True
    for table, expected in EXPECTED_ROWS.items():
        got = dax(ws, model, f'EVALUATE ROW("n", COUNTROWS({table}))')[0]["[n]"]
        flag = "OK " if got == expected else "DIFF"
        ok &= got == expected
        log(f"  {flag} {table}: {got} rows (expected {expected})")
    for rel in ("PSI90 -> HAI", "PSI90 -> HCAHPS"):
        left, right = [t.strip() for t in rel.split("->")]
        n = dax(
            ws, model,
            f'EVALUATE ROW("n", COUNTROWS(FILTER({right}, NOT ISBLANK(RELATED({left}[REPORTYEAR])))))',
        )[0]["[n]"]
        log(f"  relationship {rel}: {n} {right} rows match a {left} row")
    if not ok:
        log("Row counts differ from the expected values. This is normal if you added or removed data files.")


STEPS = ["lakehouse", "upload", "notebook", "run", "model", "verify"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", required=True, help="Display name of an existing Fabric workspace")
    ap.add_argument("--lakehouse", default="lh_amplify_hc")
    ap.add_argument("--notebook", default="nb_load_cms_tables")
    ap.add_argument("--model", default="CMS")
    ap.add_argument("--steps", default="all", help=f"comma separated subset of: {', '.join(STEPS)} (default: all)")
    args = ap.parse_args()
    steps = STEPS if args.steps == "all" else [s.strip() for s in args.steps.split(",")]
    unknown = set(steps) - set(STEPS)
    if unknown:
        sys.exit(f"Unknown steps: {unknown}")

    ws = find_workspace(args.workspace)
    log(f"Workspace '{ws['displayName']}' found")
    lh = find_item(ws["id"], "Lakehouse", args.lakehouse)
    if "lakehouse" in steps:
        lh = step_lakehouse(ws, args)
    if lh is None and any(s in steps for s in ("upload", "notebook", "model")):
        sys.exit(f"Lakehouse '{args.lakehouse}' does not exist; run the 'lakehouse' step first.")
    if "upload" in steps:
        step_upload(ws, lh, args)
    nb = find_item(ws["id"], "Notebook", args.notebook)
    if "notebook" in steps:
        nb = step_notebook(ws, lh, args)
    if "run" in steps:
        step_run(ws, nb, args)
    model = find_item(ws["id"], "SemanticModel", args.model)
    if "model" in steps:
        model = step_model(ws, lh, args)
    if "verify" in steps:
        step_verify(ws, model, args)
    log("Done")


if __name__ == "__main__":
    main()
