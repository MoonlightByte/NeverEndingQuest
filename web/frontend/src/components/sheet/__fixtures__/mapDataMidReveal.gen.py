#!/usr/bin/env python3
"""
Regenerates mapDataMidReveal.json by running the REAL server projection
(web/map_projection.py::project_map_payload) against a real area file --
NOT hand-written. Task 9 (e2e + hosted-mode verification for the Map tab).

This is the fixture shared by:
  - src/components/sheet/MapTab.integration.test.tsx (vitest, real mapper-lib)
  - e2e/mock-server.mjs's `request_map_data` handler (Playwright e2e)

Run from the repo root (/mnt/e/NEQ-design):
    python3 web/frontend/src/components/sheet/__fixtures__/mapDataMidReveal.gen.py

Regenerate only if HH001_BU.json's room set/ids change in a way that would
invalidate REDACTED_ROOM_ID/REDACTED_ROOM_REAL_NAME in
MapTab.integration.test.tsx or map-tab.spec.ts -- update those constants too
if so.
"""
import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
# __fixtures__ -> sheet -> components -> src -> frontend -> web -> repo root
REPO_ROOT = Path(HERE).parents[5]
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)  # AREA_PATH below is relative to the repo root, like project_map_payload's other callers expect

from web.map_projection import project_map_payload
AREA_PATH = os.path.join('modules', 'Keep_of_Doom', 'areas', 'HH001_BU.json')
OUT_PATH = os.path.join(HERE, 'mapDataMidReveal.json')

# Mid-reveal set: the party has explored the general store, town square, and
# east gate; the barracks/inn/smuggler's tunnel are still fogged.
REVEALED = {'A01', 'A02', 'A03'}
CURRENT_LOC = 'A02'


def main():
    with open(AREA_PATH) as f:
        area = json.load(f)
    payload = project_map_payload(area, REVEALED, CURRENT_LOC)
    with open(OUT_PATH, 'w') as f:
        json.dump(payload, f, indent=2)
        f.write('\n')
    print(f'wrote {OUT_PATH}')


if __name__ == '__main__':
    main()
