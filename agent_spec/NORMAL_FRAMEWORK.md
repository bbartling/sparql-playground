# Normal Framework (NF) — edge context for this repo

**Audience:** AI agents + humans working `sparql-playground` / blog series
`blog/if-the-analyst-could-create-an-api/`.  
**No secrets** in this file (no API keys, `.env`, Slack, customer tickets).

**Product:** [normal.dev](https://normal.dev) · Portal: https://portal.normal-online.net ·
Installer: https://github.com/normalframework/nf-sdk (`install.sh`) · Auth tokens:
https://docs.normal.dev/howto/auth/ · Buf shapes: https://buf.build/normalframework/nf

**Blog companion:** [Part 2 — Edge sensors](../blog/if-the-analyst-could-create-an-api/part-02-nf-edge-sensors/)
(`checkpoint/read_sensors.py`: API key → Cloudflare tunnel → `latestValue`).

---

## How this fits *this* repo (long haul)

| Layer | Role |
|-------|------|
| **Edge — Normal Framework** | BACnet/IP (etc.), poll, Haystack tags, history, QualityRules, **Normal Online = Cloudflare** tunnel |
| **Part 2 client** | Thin Python app proves remote read over that tunnel (OAuth API key) |
| **Cloud — `bldgts` (Part 3+)** | Haystack RDF editor + SPARQL + opaque timeseries refs; later Timescale / FDD / security |

**Do not** re-bootstrap an old NF FastAPI sidecar here. Modeling stays **in NF**; cloud
apps discover via tags/APIs — never hard-code lab point UUIDs in product code.

Flat Haystack topology in the playground (site → AHU → points) matches NF’s “tag on
the model layer” discipline — `ARCHITECTURE.md` A15/A19 and Part 3
`HAYSTACK_MODELING.md`.

---

## What NF is (integrator view)

Normal Framework is an **edge gateway / OT runtime**:

1. Install on a Linux (or Docker Desktop) host near the field bus.  
2. Discover/import devices (lab: BACnet).  
3. Tag points on the Haystack-derived **`model`** layer (`equipRef`, `class`, markers as needed).  
4. Set **poll periods** so points actually historize.  
5. Optionally author **QualityRules** (range, stale, flatline, …) selected by those tags.  
6. Expose console + **HTTP JSON** that is the same surface as gRPC (`/api/v1/*` = gRPC-JSON).  
7. Remote access: licensed sites get **Normal Online**
   (`https://<instance-uuid>.normal-online.net` → local `:8080`) via bundled `cloudflared`.

GA images pull from `normal.azurecr.io`; enterprise/private registry paths exist for
air-gapped installs. Default portal licensing flow: run installer → browser sign-in →
site/license attaches when the box boots (no second sign-in in the happy path).

---

## Bootstrap (portal installer)

```bash
# Default console port 8080 — conflict with other stacks? pick another:
#   NF_PORT=8090 INSTALL_DIR="$HOME/nf" NF_ASSUME_YES=1 …
curl -fsSL https://raw.githubusercontent.com/normalframework/nf-sdk/master/install.sh | sh

# Wait for console
curl -sf -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:${NF_PORT:-8080}/"
docker ps   # nf compose under ~/nf or /opt/nf
```

Useful env (all optional): `NF_TAG` (default `3.10`), `NF_PORT`, `NF_DATA_DIR`,
`INSTALL_DIR`, `NF_ASSUME_YES=1`, `NF_PORTAL_URL`, offline flags
`--offline` / `NF_OFFLINE` + registry creds (`NF_USERNAME` / `NF_PASSWORD` /
`NF_REGISTRY`).

**Ops hygiene**

- Prefer `docker compose up -d` after edits; avoid `down -v` (wipes data).  
- Host networking is typical for BACnet/IP.  
- Free UDP **47808** on the LAN interface used for BACnet.  
- Persist console auth under the install dir (often `/opt/nf` or `~/nf`):
  `CONSOLE_USERNAME` / `CONSOLE_PASSWORD` / `TOKEN_SIGNING_SECRET`.  
- `ALLOW_ALL_LOCALHOST=true` can bypass Basic for true loopback — easy to mis-test auth.  
- Persisted gateway config can override compose `.env` — check the data dir when
  settings “don’t stick.”

---

## Lab story (tag → poll → DQ)

1. **Install + license** via portal `install.sh` (see OptiPlex notes below if sudo/docker fails).  
2. **BACnet scan/import** (example: JCI FEC device instance **5007**):

   ```bash
   NF=http://127.0.0.1:8090   # this lab uses 8090; stock install is often 8080
   curl -s -X POST "$NF/api/v1/bacnet/scan" \
     -H 'Content-Type: application/json' \
     -d '{"device":{"targets":[{"lowLimit":5007,"highLimit":5007}],"autoScan":true},"autoImport":true}'
   # Poll until object scan DONE + imported=true:
   curl -s "$NF/api/v1/bacnet/scan?status_filter=ANY"
   ```

3. Tag points on **`layer=model` / `indexLayer=default`**: at least `equipRef` + `class`
   (bare FEC → prefer `controller`).  
4. **Set poll period** or points stay idle after import (common footgun).  
5. Create **range** (etc.) QualityRules selected by those tags.  
6. Read live values via `POST /api/v1/point/query` (`latestValue`) — do **not** reinvent
   FDD outside NF for this exercise.

### Set / clear poll period (`point/copy`)

Working shape on GA 3.10.x (needs **both** `outputLayer` and `indexLayer`):

```bash
# Enable 60s on selected UUIDs
curl -s -X POST "$NF/api/v1/point/copy" -H 'Content-Type: application/json' \
  -d '{"outputLayer":"default","indexLayer":"default","period":{"seconds":60},"uuids":["…"]}'

# Disable polling
curl -s -X POST "$NF/api/v1/point/copy" -H 'Content-Type: application/json' \
  -d '{"outputLayer":"default","indexLayer":"default","period":{"seconds":0},"uuids":["…"]}'
```

**Bench policy (2026-10-18):** poll only temp/humidity AIs + physical HVAC I/O at **60s**;
leave Priority / I1 / O1 software points and FILE/DEVICE at **0**. Typical keep set on
device 5007 (`BENS BENCHTEST BOX`, MS-FEC2611-0 @ `192.168.204.200` / net 2000):

| Kind | Points |
|------|--------|
| Temp / humidity | `OA-T`, `OA-H`, `DUCT-T`, `SSPLATE-T`, `STAT ZN-T` |
| Basic I/O | `DUCT-P`, `ACTUATOR-POS`, `ACTUATOR-0`, `AO9-4-20MA-O`, `C06`/`C07`, `BI8-S`, `CURRENT-S`, `BO3-C`, `C04`/`C05`, RIB relays, `STAT ZN WC-ADJ` |

---

## HTTP API surface (generic)

Base: `$NF_BASE` — this lab **`http://127.0.0.1:8090`**. Stock docs often show
`:8080`. **NF remote access is Normal Online (Cloudflare)** —
`https://<uuid>.normal-online.net` — not Tailscale.

Auth on the CF tunnel: Clerk when `enableAuth: true` (`401` on `/api/v1/point/*`
until browser Sign-in, or Allow-unauthenticated / API token). Loopback on the
box is usually open for lab curls. Prefer a **read-only API key + bearer** for
unattended viewers when available.

| Call | Role |
|------|------|
| `POST /api/v1/bacnet/scan` | Discover / import |
| `GET /api/v1/bacnet/scan?status_filter=ANY` | Scan status |
| `POST /api/v1/point/query` | List points; `latestValue` = live sample |
| `POST /api/v1/point/copy` | Set `period` / static attrs; require `outputLayer` + `indexLayer` |
| `GET`/`POST /api/v1/point/data` | History (retention often ~days; shapes vary by version) |
| `POST /api/v1/point/quality-rules` | Upsert DQ rules (e.g. `detector.range`); use stable `id` + PUT to avoid duplicates |
| `/api/v1/auth/token` | Token issuance when configured |

Buf / protobuf messages == this HTTP JSON. Raw gRPC clients are optional for thin apps.

Console deep links: `/` console, `/object-explorer`, `/quality-rules`.

---

## Modeling notes (Haystack vs Brick inside NF)

- Prefer the Haystack **`model`** layer for `equipRef` / `class` workflows.  
- Enabling **Brick** in NF tends to be **either/or**, not an additive second tag set.  
- Setting `class` does **not** auto-emit Haystack markers — set markers explicitly if
  a workflow needs them.  
- First tag write is still UUID/UI oriented; after tags exist, automation can be
  tag-based.  
- OEM device type ≠ ontology class (a lab FEC is awkward as `vav`).

---

## QualityRules / FDD (known product shape)

**Works:** range, stale, dead, flatline-style detectors; flags land on points as
`quality_flags`; severity lives on the **rule**, not the point.

**Gaps to remember (don’t paper over in a sidecar):**

- No authorable **rate-of-change / spike** detector in 3.10.x GA paths we exercised.  
- Range behavior can consider **retained history**, not only “OOR right now.”  
- DQ sweep latency is often **minutes**, so flags lag fast polls.  
- Detector set is limited; confirm create payloads against the live version before
  treating field names as gospel.

---

## Remote access / Cloudflare

- **Prefer Normal Online** tunnel on licensed portals (`*.normal-online.net`).  
- DIY host `cloudflared` is possible for a custom hostname; keep BACnet LAN-only;
  put Cloudflare Access in front of Basic auth on public hostnames.  
- Long-haul with this playground: cloud app requests historian samples through the
  tunnel (or later into SQL/Timescale) using **opaque ids / tagged points**, never
  raw BMS column names in product code.

---

## Sidecar design rule (if you build a viewer)

Site-specific modeling lives **in NF**, not in app code:

1. Discover equipment/points/`equipRef`/`class` from NF APIs.  
2. Do not hard-code lab UUIDs, device names, or QualityRule ids in the happy path.  
3. Optional env filters are OK as runtime config.  
4. Talk NF over HTTP/JSON `/api/v1/*`.

The historical lab sidecar (`apps/bench-dashboard`) followed that rule; **do not**
port or run it as part of this repo’s bootstrap.

---

## Console footguns (sanitized)

- Imported points **do not poll** until a period is set.  
- Object Explorer can look empty when a device group is collapsed.  
- Some saved OE views crash if `object_selection_views` JSON is malformed
  (`columnSelection` / `layer*|*field` grouping). Safe recovery is often DELETE of
  that config key after backup — treat configkeys as **internal**, not a public API.  
- Built-in Dashboard configkeys are likewise internal/brittle.

---

## This machine checklist (OptiPlex test bench)

| Fact | Value |
|------|--------|
| Host | `ben-OptiPlex-7070` (Dell OptiPlex 7070) |
| Install dir | `~/nf` (`docker compose`, **host** network) |
| Console (local) | `http://127.0.0.1:8090/` |
| NF remote (product) | Cloudflare Normal Online — `https://<instance-uuid>.normal-online.net` (portal device page; browser Sign-in) |
| Host Tailscale (not NF) | `100.104.255.84` — Ben’s mesh VPN on this OptiPlex only; useful lab shortcut to hit `:8090`, **not** part of Normal Framework |
| LAN | `eno1` → `192.168.204.11` |
| BACnet FEC | device instance **5007**, JCI MS-FEC2611-0, `192.168.204.200` |
| Port conflict | open-fdd often owns `:8080` → always use **`NF_PORT=8090`** here |

```bash
docker --version
free -h
ss -ulpn | grep 47808 || echo "BACnet UDP free"
ss -tlnp | grep -E '8080|8090' || true

# Fresh install (interactive portal sign-in in browser):
NF_PORT=8090 NF_ASSUME_YES=1 INSTALL_DIR="$HOME/nf" \
  curl -fsSL https://raw.githubusercontent.com/normalframework/nf-sdk/master/install.sh | sh
```

### After reboot / “NF looks dead”

```bash
cd ~/nf && docker compose up -d
curl -sf http://127.0.0.1:8090/api/v1/platform/info | jq '{site:.siteName,ver:.version,lic:.license.name,type:.license.type}'
# Expect UDP 47808 on eno1; host network mode on nf-nf-1
docker inspect nf-nf-1 --format '{{.HostConfig.NetworkMode}}'
ss -ulpn | grep 47808
# Portal: tunnel should return to healthy once licensed box heartbeats outbound
```

Data + `license.jwt` live under `~/nf/data/` (compose volume). Prefer
`docker compose up -d`; **avoid** `down -v` (wipes the edge DB).

### License footgun (installer + sudo)

Portal can show **Activated!** while the box still has **no** `license.jwt` if
`install.sh` dies on `sudo docker` (user already in `docker` group). Fix:

1. Ensure images/containers are up via plain `docker compose` in `~/nf`.  
2. Run a license-only finish that **does not** `xdg-open` (spam) — e.g.
   `~/nf/finish-license.sh` with a PATH shim so `sudo` is a no-op:
   `printf '%s\n' '#!/bin/sh' 'exec "$@"' > /tmp/nf-bin/sudo && chmod +x /tmp/nf-bin/sudo`  
3. Approve **one** portal activate URL; script POSTs
   `/api/v1/license/device/complete` then `$NF/api/v1/platform/license`.  
4. Confirm: `ls ~/nf/data/license.jwt` and `license.name` on `/api/v1/platform/info`.

### Remote read: NF Cloudflare vs localhost (vs host Tailscale)

**Normal Framework’s** remote path is the bundled **cloudflared** tunnel →
`*.normal-online.net`. Tailscale on this PC is unrelated host networking.

```bash
# A) Localhost (on the OptiPlex) — lab API without Clerk
curl -s -X POST http://127.0.0.1:8090/api/v1/point/query -H 'Content-Type: application/json' \
  -d '{"pageSize":100}' | jq -r '.points[] | select(.name=="OA-T") | "\(.name) \(.latestValue)"'

# B) NF Cloudflare tunnel (product remote access)
# - Browser: open tunnel URL from portal → Sign in → Object Explorer (live points).
# - Bare curl often → CF Error 1010; send a browser User-Agent for public GETs.
# - /api/v1/platform/info OK with UA; /api/v1/point/* → 401 until Sign-in
#   (or device page: Allow unauthenticated / API token).
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
curl -s -A "$UA" "https://<uuid>.normal-online.net/api/v1/platform/info" | jq '{site:.siteName,auth:.enableAuth}'

# C) Optional lab only — host Tailscale IP:8090 (NOT an NF feature)
# curl -s -X POST http://100.104.255.84:8090/api/v1/point/query ...
```

Verified 2026-10-18: sensors polling locally; CF tunnel healthy + Sign-in gate;
`latestValue` on `OA-T` / `OA-H` / `DUCT-T` / `SSPLATE-T` / `STAT ZN-T`. Tunnel
hostname is on the portal device page.

Wire BACnet only when the bench switch/device is on the `192.168.204.0/24` LAN.

### Python: read sensors via tunnel (API key — not Clerk scrape)

Do **not** automate the portal “Sign in” button. Create an **API key** in the NF
console (`Settings → Authorization → API keys`), copy `client_id` /
`client_secret` once, then OAuth2 client-credentials against the **same** base
URL you use for API calls (`https://<uuid>.normal-online.net` or localhost).

Docs: [Tokens](https://docs.normal.dev/howto/auth/) · [examples](https://docs.normal.dev/examples/).

```bash
export NFURL='https://<uuid>.normal-online.net'   # or http://127.0.0.1:8090
export NF_CLIENT_ID='…'
export NF_CLIENT_SECRET='…'
# Preferred: blog Part 2 checkpoint (also accepts checkpoint/.env)
python3 blog/if-the-analyst-could-create-an-api/part-02-nf-edge-sensors/checkpoint/read_sensors.py
```

```python
import os, requests

NFURL = os.environ["NFURL"].rstrip("/")
SENSORS = ["OA-T", "OA-H", "DUCT-T", "SSPLATE-T", "STAT ZN-T"]

tok = requests.post(
    f"{NFURL}/api/v1/auth/token",
    json={
        "client_id": os.environ["NF_CLIENT_ID"],
        "client_secret": os.environ["NF_CLIENT_SECRET"],
        "grant_type": "client_credentials",
    },
    headers={"User-Agent": "nf-lab-script/1.0"},
    timeout=30,
)
tok.raise_for_status()
bearer = tok.json().get("accessToken") or tok.json().get("access_token")

r = requests.post(
    f"{NFURL}/api/v1/point/query",
    headers={
        "Authorization": f"Bearer {bearer}",
        "Content-Type": "application/json",
        "User-Agent": "nf-lab-script/1.0",
    },
    json={"pageSize": 100},
    timeout=60,
)
r.raise_for_status()
for p in r.json().get("points", []):
    if p.get("name") in SENSORS and (p.get("attrs") or {}).get("type") == "OBJECT_ANALOG_INPUT":
        lv = p.get("latestValue") or {}
        print(f"{p['name']:10} {lv.get('double')} {p.get('units')} @ {lv.get('ts')}")
```

Send a normal `User-Agent` on the tunnel (bare curl/python-requests default can
hit Cloudflare 1010). Keep secrets in env / user store — never in the graph or git.

---

## Revive an unhealthy portal node (lab notes)

Observed on this dual-boot box (2026-10-18):

- Portal still lists **ben-desktop** (`99256910`, NF `3.10.9-1`) as activated but
  **Unhealthy / Tunnel down / Last Heartbeat N/A**.
- Linux hostname is now `ben-OptiPlex-7070`. There is **no** local `/opt/nf`, `~/nf`,
  NF Docker images, or data volumes — the Oct 11 edge install is gone from this OS.
- Open-FDD CSV compose owns `127.0.0.1:8080`; prefer **`NF_PORT=8090`** for a new NF.
- A mid-install “activate?” link for a *new* hostname (`ben-OptiPlex-7070`) creates a
  **new** portal node — do **not** finish that if you only meant to revive ben-desktop.

### Recommended recovery

1. **Download the portal backup** from the ben-desktop device page (Backups — e.g.
   `2026-10-11 …`). Save the file somewhere durable (`~/Downloads/nf-ben-desktop.backup`
   or similar). Docs: [Backups](https://docs.normal.dev/howto/backup/).
2. **Install a fresh NF 3.10.x** on this host (`NF_PORT=8090`, `INSTALL_DIR=$HOME/nf`,
   rootless so no sudo). Complete **portal activate** in the browser (free-tier seats
   remain if you are under the org limit). Prefer naming/tags `freetier` + `dev` again.
3. Confirm local console: `http://127.0.0.1:8090/` and that the portal node shows a
   recent heartbeat / tunnel **up**. Tunnel URL form:
   `https://<uuid>.normal-online.net`.
4. **Restore configuration/points** onto the running box:
   - Portal device page → restore from the downloaded/cloud backup when offered, **or**
   - `nfcli restore path/to/nf.backup` against `http://127.0.0.1:8090`  
     (same **minor** version as the backup — pin `3.10.9-1` if possible; `--force` only
     if you accept risk).
5. Optionally **retire** the dead ben-desktop portal row after the new node is healthy
   so fleet view stays clean (does not delete the backup file you downloaded).

Tunnel stays down until a licensed instance is running and can heartbeat outbound.

---

## Pointers

| Doc | Where |
|-----|--------|
| Locked playground architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Haystack authoring / agent tagging | Part 3 `HAYSTACK_MODELING.md` |
| Part 2 sensor client | `blog/…/part-02-nf-edge-sensors/checkpoint/read_sensors.py` |
| Public NF product findings (upstream notes) | `docs/NF_PRODUCT_FINDINGS.md` in normal-framework-notes |
| Installer source | `normalframework/nf-sdk` `install.sh` |

Update this file when GA behavior changes; keep secrets and customer context out.
