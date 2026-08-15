# Generated Module Quality Review - 2026-08-15

## Scope and verdict

Reviewed, without changing either module:

- `modules/The_Haunted_Watchtower` (Gemma 4 12B QAT)
- `modules/The_Haunted_Watchtower_v2` (Qwen 3.5 9B, with the proposed fresh-encounter stripping change)

Neither module is ready to ship as authored. Both load, satisfy the file-shape schemas, and
have fully reachable location graphs. Both nevertheless have defects that a schema-only check
does not detect. The Gemma build has the more serious state-integrity defect: it starts a new
campaign with 11 pre-authored, falsely dated encounter-history records. The Qwen build correctly
starts with no encounter history, but its physical area links contradict its plot order, one
location disagrees with its map, required key paths are absent, and several important plot beats
do not exist in the location content.

Qwen produced the better raw module, narrowly: its location prose is more developed, its main
plot has a clearer through-line, and its fresh-state fields are correct. Gemma is less likely to
block a player on a locked door, but its preplayed encounter history, generic first area, and
repeated climax are worse. This is a comparison between two non-shippable candidates, not a pass.

## What was actually validated

1. Every JSON-like artifact in both module directories was parsed.
2. Every live and backup area was checked against
   `schemas/locationfile_schema_strict.json`; every live and backup map, plot, and party tracker
   was checked against its production schema.
3. `core.validation.validate_module_files.ModuleValidator` was run directly with `strict=True`
   so it could not write a validation report. It passed the live area/map/plot/party schemas,
   internal connectivity, bidirectionality, and encounter-creature checks where applicable. It
   failed `module_context.json` in both modules.
4. Maps were independently cross-checked against live location IDs, coordinates, connections,
   directions, and layouts. Cross-area edges were checked in both directions, and every location
   was tested for reachability from A01 through the real `utils.location_path_finder.LocationGraph`.
5. Both modules were copied to disposable game directories and booted through the real headless
   `new-game` and `state` commands. Both selected and loaded a valid A01 start, the player sheet,
   party tracker, location, and full unified plot. This proves startup/loadability, not an
   end-to-end playthrough of every quest.

No product source, module artifact, credential file, or existing validation report was changed.
Only this audit was written.

## Schema coverage

### Gemma module

- PASS: 8 area payloads (2 live, 2 `_BU`, 2 `.bak`, 2 timestamp backups).
- PASS: 4 map payloads (2 live, 2 `_BU`).
- PASS: 2 plot payloads (live and `_BU`).
- PASS: 2 party payloads (live and `_BU`).
- PARSE PASS, but no JSON Schema exists for: 3 module-context payloads and 2 validation reports.
- NOT APPLICABLE: `characters/`, `monsters/`, and `encounters/` contain no JSON files.

### Qwen module

- PASS: 12 area payloads (3 live, 3 `_BU`, 3 `.bak`, 3 timestamp backups).
- PASS: 6 map payloads (3 live, 3 `_BU`).
- PASS: 2 plot payloads (live and `_BU`).
- PASS: 2 party payloads (live and `_BU`).
- PARSE PASS, but no JSON Schema exists for: 3 module-context payloads and 2 validation reports.
- NOT APPLICABLE: `characters/`, `monsters/`, and `encounters/` contain no JSON files.

There is intentionally no standalone `module.json`. The production validator disables that old
architecture at `core/validation/validate_module_files.py:123-126`; current modules use the area,
plot, party, and context files instead. The empty `.transaction.lock` files are runtime locks, not
JSON content.

### Important contract clarification: unified plot locations are area IDs

Both unified plots store area IDs in `plotPoints[].location` and
`sideQuests[].involvedLocations`. Although `schemas/plot_schema.json:30-33,67-72` still describes
those strings as location IDs, this is correct for the current runtime contract:

- T028 explicitly demands area IDs at `core/generators/module_builder.py:1328,1337,1351-1353`.
- Its code validator rejects anything outside the set of area IDs at
  `core/generators/module_builder.py:288-326`.
- Runtime selects current plot points by comparing that value to `current_area_id` at
  `main.py:5825-5836`.

Therefore the area IDs in these two final unified plots are not module defects. The stale schema
descriptions are a repository documentation/validation gap. Narrative text that names a specific
room still needs to agree with the actual room content, and several entries do not.

## Shared structural positives

- Location IDs are unique and follow the expected letter-plus-two-digit scheme.
- Every internal connection resolves and is reciprocal.
- Every cross-area destination resolves to a real location and is reciprocal.
- Every location is reachable from A01 in the production location graph.
- Every `nextPoints` reference resolves and both plot chains terminate.
- Root maps and embedded maps carry the same room sets and internal connection graphs.
- Each party tracker names a real start area and location. The real headless boot loaded those
  starts successfully.
- The exact repair-floor string `To be detailed by the module doctor` occurs nowhere.

## Gemma: `The_Haunted_Watchtower`

### G1 - BLOCKER: a fresh module contains false, preplayed encounter history

Eleven of twelve locations contain authored `encounters` records. Their years are 1200 or 1204,
while `party_tracker.json:$.worldConditions.year` is 1492. A newly created module has not played
these scenes, and runtime owns the authoritative clock.

- `areas/SP001.json:$.locations[0..5].encounters`
- `areas/OR001.json:$.locations[0,2,3,4,5].encounters`
- Representative runtime authority:
  `core/managers/combat_manager.py:1843-1847` constructs encounter world conditions from the
  party tracker, then appends the encounter at `:1869`.

This is precisely what the proposed encounter-stripping change prevents. It is not cosmetic:
these records claim that play already happened, use the wrong campaign dates, and can affect
history supplied to the DM and subsequent encounter numbering.

### G2 - HIGH: plot progression and physical travel do not line up

The plot runs SP001 PP001-PP004, then OR001 PP005-PP008. The only physical bridge is
`SP001/A01 <-> OR001/B06`:

- `areas/SP001.json:$.locations[0].areaConnectivityId[0]` is B06.
- `areas/OR001.json:$.locations[5].areaConnectivityId[0]` is A01.

This lets a new party enter the other area's final lookout immediately. Conversely, completing
the first arc at SP001/A06 does not lead to OR001/B01 as PP005 implies; the party must return to
A01, enter OR001 backwards at B06, and traverse toward B01. The graph is connected, but the
designed story route is not encoded in it.

### G3 - HIGH: `module_context.json` is stale and fails production validation

The production semantic validator reports:

- `module_context.json:$.locations.A01.connections` omits B06.
- `module_context.json:$.locations.B06.connections` omits A01.

Additional drift the validator does not report:

- `$.areas.SP001.name` is `Shadowed Pass`, not live `The Shaded Highlands`.
- `$.areas.OR001.name` is `Oakhaven Ridge`, not live `The Shadowed Oak-Ridges`.
- `$.areas.OR001.plot_points` repeats PP001-PP004 instead of PP005-PP008.
- `$.plot_scopes` contains only PP001-PP004 and assigns them to OR001, although those four final
  plot points belong to SP001; PP005-PP008 are absent.
- `validation_report.json:$.context_summary.plot_points` consequently says 4 while the final plot
  has 8, and `$.issues` incorrectly says there are no issues.

### G4 - HIGH: most authored monster names have no existing stat source

`monsters/` is empty. Of seven unique lazy location-monster names, only `Shadow`,
`Will-O'-Wisp`, and `Skeleton` resolve to the global compendium. These do not:

- `areas/OR001.json:$.locations[0,3,4].monsters[0].name`: Shadow Stalker
- `areas/OR001.json:$.locations[2,5].monsters[0].name`: Ghostly Soldier
- `areas/SP001.json:$.locations[2].monsters[0].name`: Twig Blight
- `areas/SP001.json:$.locations[3].monsters[0].name`: Wolf

This does not make the JSON invalid. The production validator explicitly treats
`locations[].monsters` as lazy spawn descriptors and exempts them from prebuilt-stat resolution
at `core/validation/validate_module_files.py:799-801`; combat can ask the runtime model to build a
missing stat card. It does mean most of the authored combat is not self-contained and is exposed
to another model call at play time.

### G5 - HIGH: NPC identity and quest support drift

All seven NPC names are declared in module context, but the same identities are placed in both
areas with incompatible roles and no explanation of travel, projection, or duplication:

- Mother Marrow is a neutral grove tender at `SP001:$.locations[2].npcs[0]` and a hostile cult
  leader at `OR001:$.locations[4].npcs[0]`.
- Silas is a hermit/adviser in locations, while `MODULE_SUMMARY.md:13` calls him the Bandit King.
- Captain Valerius appears as both `Captain Valerius Thorne` and `Spirit of Captain Valerius
  Thorne`, sometimes together, across A02/A06/B06.
- Elara, the ghostly soldiers, and the cultists are likewise duplicated across areas.

Most side quests also lack the thing or scene they ask the player to use: the merchant crate,
rare pine resin, captured scout, ancient crest, and Silas's riddles are absent. SQ005 sends the
party to B02 for tools, but `OR001:$.locations[1].lootTable` contains rotten rations, a coin, and
a waterskin. PP003 describes a Shrine of Mourning in SP001, but the only location with that name
is OR001/B05.

### G6 - MEDIUM: the first area is largely generator scaffolding

All SP001 descriptions and DM instructions repeat short `Shadowed Pass` templates rather than
developing the accepted watchtower premise. Several features contain grammar-floor phrases such
as `A fallen logs`, `A animal tracks`, and `A unusual plants`. Every map room has
`purpose: "unknown"`. This is not the exact module-doctor floor string, but it is visibly
unfinished content.

OR001 door prose also disagrees with its map at B03, B04, and B06 (for example, B03 calls the
B04/barracks edge east even though the map places B04 south). All doors are unlocked, so Gemma
has no missing key/passphrase blocker.

### Gemma verdict

Technically loadable, but not shippable. Strip the false encounters, rebuild the context, align
the inter-area gateway with plot progression, and repair the first area's content and quest
props before considering play-quality acceptance.

## Qwen: `The_Haunted_Watchtower_v2`

### Q1 - PASS: the encounter-stripping change produced the correct fresh state

All 18 live locations and all their copies contain:

- `encounters: []`
- `adventureSummary: ""`
- `explorationState.status: "unvisited"`

There are no authored encounter files. This matches the shipped starter templates: all 17
`The_Thornwood_Watch/*_BU.json` locations and all 36 `Keep_of_Doom/*_BU.json` locations have
empty `encounters` arrays. Their generic `randomEncounters` tables are authored possibilities,
not history, and are correctly retained.

The proposed code does this deterministically at
`core/generators/location_generator.py:192-210`. That behavior is correct.

### Q2 - BLOCKER: the plot order contradicts the physical area order

The final plot orders areas as IPA001 -> HWG001 -> STS001. The actual bridges are:

- `areas/IPA001.json:$.locations[0].areaConnectivityId[0]` A01 -> B06
- `areas/HWG001.json:$.locations[5].areaConnectivityId[0]` B06 -> A01
- `areas/IPA001.json:$.locations[5].areaConnectivityId[0]` A06 -> C01
- `areas/STS001.json:$.locations[0].areaConnectivityId[0]` C01 -> A06

From the start at A01, the player can jump directly into HWG's deepest vault (B06). Completing
IPA naturally reaches A06 and sends the party to STS, skipping HWG entirely. To follow the
written plot, the player must enter HWG backwards, return to the beginning of IPA, traverse IPA
again, then enter STS. All locations are reachable, but the intended campaign route is not.

### Q3 - HIGH: one live location disagrees with the map

`areas/IPA001.json:$.locations[3]` (A04) says `coordinates: "X2Y3"`, duplicating A02. Both the
embedded map and `map_IPA001.json:$.rooms[3].coordinates` place A04 at `X1Y2`, west of A01. All
other room IDs, coordinates, and internal edges agree. This is an issue-128-class consistency
failure that the JSON Schemas and current module validator miss.

### Q4 - HIGH: `module_context.json` is stale and fails production validation

The production validator reports missing cross-area connections at:

- `module_context.json:$.locations.B06.connections` (missing A01)
- `module_context.json:$.locations.A01.connections` (missing B06)
- `module_context.json:$.locations.A06.connections` (missing C01)
- `module_context.json:$.locations.C01.connections` (missing A06)

Additional drift:

- All three context area names are stale relative to the live `The ...lands` names.
- Every `$.areas.*.plot_points` list says PP001-PP004.
- `$.plot_scopes` contains only PP001-PP004 and incorrectly assigns all four to STS001.
- `$.npcs.spectral_guardians` has no appearance and wrongly treats a monster phrase as an NPC;
  `$.validation_issues[0]` admits that problem.
- `validation_report.json:$.context_summary.plot_points` says 4, not 12, and misses the other
  structural defects.

### Q5 - HIGH: most monster names do not resolve without runtime generation

The module has 11 unique lazy monster names. `Wraith`, `Wight`, `Specter`, and `Stone Golem`
resolve to the global compendium. These seven do not, and `monsters/` is empty:

- `IPA001:$.locations[3].monsters[0]`: Spectral Wraith
- `IPA001:$.locations[5].monsters[0]`: Skeletal Warrior
- `HWG001:$.locations[1].monsters[0]`: Spectral Guardian
- `HWG001:$.locations[4].monsters[0..1]`: Cursed Zombie, Phantom Archer
- `HWG001:$.locations[5].monsters[0..1]`: Ancient Evil Manifestation, Spectral Wraith
- `STS001:$.locations[4].monsters[0]`: Spectral Guardians

As with Gemma, runtime generation can make these playable, but the module is not self-contained.
The singular/plural split between `Spectral Guardian` and `Spectral Guardians` also risks two
different generated identities.

### Q6 - HIGH: locks have no authored key path

Five locked doors name keys that do not exist anywhere else in live module content:

- `IPA001:$.locations[0].doors[0].keyname`: Gate Key
- `IPA001:$.locations[1].doors[1].keyname`: Command Key
- `IPA001:$.locations[3].doors[0].keyname`: Ironwood Key
- `STS001:$.locations[0].doors[0].keyname`: Iron Key of Passage
- `STS001:$.locations[5].doors[0].keyname`: Ritual Key

A04 contains `Rusty iron key`, not the exact `Ironwood Key`, and it is inside the room behind the
locked Ironwood Door. Numerous other locked doors have an empty `keyname`. Lock-picking,
breaking, magic, or an agentic NPC decision may still provide a way through, so this is not a
guaranteed engine deadlock. It is nevertheless missing authored support for the key-based route,
including at the starting gate and final altar.

### Q7 - HIGH: important plot beats are absent or placed elsewhere

- `module_plot.json:$.plotPoints[6]` puts Morvath at the Cursed Command Deck (B05), but
  `HWG001:$.locations[4].npcs` contains only the Ghostly Specter.
- `$.plotPoints[7]` puts Morvath at the Atrium (B02) after already confronting her at A05 and
  B05; the module gives no projection/escape/relocation mechanism.
- `$.plotPoints[7].sideQuests[0]` says the B02 merchant holds an Altar Key, but neither the NPC,
  room loot, nor any other live content contains it.
- `$.plotPoints[10].sideQuests[0]` asks players to speak with fallen soldiers in C04, whose
  `npcs` array is empty.
- `$.plotPoints[11]` says Morvath is surrounded by spectral guardians, but C06 has no monsters;
  the unresolved plural guardians are at C05.
- `$.plotPoints[11].sideQuests[1]` introduces a required relic in distant B06 only at the finale
  and declares only STS001 as involved, forcing an unprepared major backtrack.
- SQ004's Lost Soul Totem is absent from A06 loot.
- `MODULE_SUMMARY.md` promises cultists, but no cultist NPC or monster exists.

Morvath herself is authored simultaneously in A05, B02, and C06 with conflicting attitudes
(hostile, fearful/help-seeking, and fanatical). Kaelen, the merchant, and the specter are also
repeated across areas without a continuity mechanism.

### Q8 - MEDIUM: visible scaffolding remains

There is no exact module-doctor floor string, but every map is named `Mixed Map`, every room has
`purpose: "unknown"`, climates/terrain use generic `varied` values, and random encounters contain
phrases such as `hostile creature appropriate for level 4 parties`. These are legal inputs for an
agentic DM but not polished authored content.

`map_HWG001.startRoom` is B02 even though the only external arrival is B06; `map_STS001.startRoom`
is C03 while the external arrival is C01. Those map-local start markers do not prevent traversal,
but they reinforce that map intent and module routing were generated independently.

### Qwen verdict

Technically loadable and correct on fresh encounter state, but not shippable. Repair the physical
area sequence, A04 coordinates, context projection, key/quest support, finale placement, and
creature identity provenance before treating this as a playable module.

## Gemma versus Qwen

| Dimension | Gemma | Qwen | Better |
|---|---|---|---|
| File-shape schemas | Pass | Pass | Tie |
| Fresh runtime state | 11 false dated encounters | 18/18 clean | Qwen |
| Load/start | Real headless boot passes | Real headless boot passes | Tie |
| Graph reachability | Complete | Complete | Tie |
| Plot-versus-route | Backwards second-area entry | Backwards HWG entry and IPA skips HWG | Gemma, slightly |
| Map consistency | Coordinates/edges agree | A04 coordinate conflict | Gemma |
| Authored access | No locked-door blocker | Five missing named keys plus blank-key locks | Gemma |
| Location prose | One rich area, one obvious template area | More consistently developed | Qwen |
| Plot cohesion | Clear cult/spirit core but repeated climax | Stronger top-level goal but repeated villain/finale | Qwen, slightly |
| Self-contained creatures | 3/7 resolve | 4/11 resolve | Neither |
| Context integrity | Fails and materially stale | Fails and materially stale | Neither |
| Overall | Not shippable | Better raw candidate, not shippable | Qwen, narrowly |

## Validator gaps exposed by this review

The existing validator does not currently prove:

- that a new module has empty runtime history;
- map coordinates/directions against live locations;
- plot order against physical cross-area routing;
- quest actors/items against location content;
- named key existence or reachability;
- lazy monster or NPC resolution before first use;
- most module-context fields (area names, plot ownership/scopes, NPC classification);
- truthfulness of `validation_report.json`;
- placeholder prose, repeated identities, or narrative continuity.

The current strict schema/validator pass therefore means "well-shaped and connected," not
"accurate, coherent, self-contained, and ready to play."

## Final recommendation

Do not ship either generated module as a finished adventure. Keep the Qwen encounter-stripping
change: it is correct and directly fixes the Gemma module's worst state-integrity failure. Treat
the Qwen output as the better repair candidate, then require a post-generation semantic pass for
route order, context synchronization, map/location agreement, lock support, creature identity,
and concrete quest/finale support before a generated module can be called playable.
