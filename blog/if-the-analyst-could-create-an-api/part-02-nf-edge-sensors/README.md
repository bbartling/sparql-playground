# Part 2 — Edge sensors via Normal Framework

**Series:** [If the analyst could create an API](../README.md)  
**Builds on:** [Part 1](../part-01-bare-sparql-api/) (bare SPARQL API)  
**Status:** runnable client checkpoint (not the live `bldgts` package)

Before you invent a cloud historian UI, prove you can **read live OT** the way a real
app should: through Normal Framework’s HTTP API over the **Cloudflare Normal Online**
tunnel, with an **API key** — not scraped console cookies, not Tailscale-as-product.

Lab context (**bosspi** Pi = live edge, OptiPlex standby, FEC 5007, portal switch,
poll policy): [`agent_spec/NORMAL_FRAMEWORK.md`](../../../agent_spec/NORMAL_FRAMEWORK.md).

**Remote (internet server):** use the bosspi Cloudflare tunnel + API key — that is what
`read_sensors.py` is for.

1. Portal → device **bosspi** → Tunnel → **Allow unauthenticated** (not Require sign-in).  
2. Open console → **Settings → Authorization → API keys** → create; copy secret once.  
3. `checkpoint/.env`:

   ```bash
   NFURL=https://6639ffc3-4264-45d3-ba48-e81f451b33d1.normal-online.net
   NF_CLIENT_ID=…
   NF_CLIENT_SECRET=…
   ```

4. On any host with Python + `requests`: `python read_sensors.py`

LAN `http://192.168.204.12:8090` is optional for bench debugging (no key today). OptiPlex
keys / old tunnel UUID do **not** work.

## Story

1. NF on the LAN discovers BACnet (here: JCI FEC device **5007**).  
2. You set poll periods on temp/humidity + basic HVAC I/O only.  
3. Portal tunnel is healthy (`https://<uuid>.normal-online.net`).  
4. Console → **Settings → Authorization → API keys** → copy client id/secret once.  
5. This part’s Python client: token → `POST /api/v1/point/query` → print `latestValue`.

## Layout

```
checkpoint/
  read_sensors.py   # app-ready client
  .env.example      # NFURL + NF_CLIENT_ID + NF_CLIENT_SECRET
  requirements.txt  # requests
```

## Run

```bash
cd blog/if-the-analyst-could-create-an-api/part-02-nf-edge-sensors/checkpoint
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill from NF API key modal; chmod 600 .env
python read_sensors.py
```

Or point at a secrets file outside the repo (never commit secrets):

```bash
export NFURL='https://<uuid>.normal-online.net'
export NF_CLIENT_ID='…'
export NF_CLIENT_SECRET='…'
python read_sensors.py
```

Expected: lines for `OA-T`, `OA-H`, `DUCT-T`, `SSPLATE-T`, `STAT ZN-T` with
units and timestamps.

## Verify

```bash
cd checkpoint && python read_sensors.py
# exit 0 and at least one sensor line
```

## Next

[Part 3 — Haystack model CRUD + Vite UI](../part-03-model-crud-ui/) (live `bldgts` app base)
