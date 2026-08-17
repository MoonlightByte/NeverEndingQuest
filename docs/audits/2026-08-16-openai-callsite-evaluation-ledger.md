# OpenAI callsite evaluation ledger

Date: 2026-08-16  
Rebased integration tip: `362996004e4bf26ba9242eaccb8cdbdd715d48e5`  
Decision scope: all 75 registered T-IDs plus enabled T104 (76/76)

## How to read this ledger

Every row has a production recommendation. “Pass” means the candidate satisfied
the available production-shaped contract/scenario checks. Persistent scaffold
comparisons are development evidence; the acceptance evidence is the complete
headless story-first build, complete headless classic build, and inspection of
the generated game-state files. A recommendation is not a claim that every
creative call received ten blinded samples: evidence strength is stated rather
than hidden.

Prices used for selection are the official 2026-08-16 snapshots: Luna
$0.20 input / $0.02 cached input / $1.20 output per million tokens; Terra
$2.00 / $0.20 / $12.00. Thus Terra is 10x Luna at the same token counts and is
selected only where Luna failed or retried materially. All selected calls use
explicit IDs; the unsuffixed Sol-routing alias is excluded.

Evidence abbreviations:

- `P`: current-production strict persistent scaffold.
- `H`: historical original-refactor scenario scaffold, rerun against the candidate.
- `R`: current captured production request replay.
- `SF`: complete story-first headless build and generated-file validation.
- `CL`: complete classic headless build and generated-file validation.
- `Q`: focused semantic/quality comparison.

Raw prompts and responses are owner-local and ignored under
`model_eval_captures/openai-callsite-optimization/`. Durable aggregate evidence
is summarized here without secrets or model-authored raw content.

| ID | Invocation path | Status | Incumbent | Tested candidates / result | Recommendation | Retries / observed speed-cost | Evidence |
|---|---|---|---|---|---|---|---|
| T012 | `core/ai/action_handler.py` | active | `gpt-5-mini` | Luna-none exercised at the real shared boundary and in CL; valid structured output | `gpt-5.6-luna` none | Accepted; low-cost default | CL |
| T013 | `core/ai/action_handler.py` | active | `gpt-5-mini` low | Stale historical capture was rejected and replaced with the current production request; Luna-none and incumbent both passed | `gpt-5.6-luna` none | 1.848s / $0.000539 vs incumbent 9.242s / $0.001625 | R, CL |
| T014 | `core/ai/action_handler.py` | active | `gpt-5.4-mini` none | Luna-none exact scenarios pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T015 | `core/ai/adv_summary.py` | active | `gpt-5.4-mini` none | Luna-none clean | `gpt-5.6-luna` none | No retry increase observed | H |
| T016 | `core/ai/adv_summary.py` | active | `gpt-5.4-mini` none | Luna-none clean | `gpt-5.6-luna` none | No retry increase observed | H |
| T017 | `core/ai/combat_compression_engine.py` | active | `gpt-5-mini` low | Full source-aware set: incumbent 5/6; Luna none 1/6, low 2/6, medium 6/6; Terra none 3/6, low 6/6, medium 5/6; Luna/Terra high 5/6 | `gpt-5.6-luna` medium | Full pass in ~36.6s total vs incumbent ~94.8s; Luna is 10x cheaper than equal-quality Terra-low | P |
| T018 | `core/ai/cumulative_summary.py` | active | `gpt-5.4-mini` none | Luna-none clean | `gpt-5.6-luna` none | No retry increase observed | H |
| T019 | `core/ai/cumulative_summary.py` | active | `gpt-5.4-mini` none | Luna-none clean | `gpt-5.6-luna` none | No retry increase observed | H |
| T020 | `core/ai/incremental_compression.py` | active | `gpt-5.4-mini` none | Luna-none 3/3 JSON | `gpt-5.6-luna` none | median 2.823s; $0.016852 total | R |
| T021 | `core/ai/transition_validator.py` | active | `gpt-5.2` none | Luna-none 2/2 JSON | `gpt-5.6-luna` none | median 2.348s; $0.001374 total | R |
| T022 | `core/generators/area_generator.py` | active | `gpt-5.2` none | Luna-none 4/4 and complete CL | `gpt-5.6-luna` none | First-attempt CL calls ~0.9–1.1s | H, CL |
| T023 | `core/generators/area_generator.py` | active | `gpt-5.2` none | Luna-none 5/5 and complete CL | `gpt-5.6-luna` none | CL calls ~1.7–1.9s | H, CL |
| T024 | `core/generators/area_generator.py` | dormant | `gpt-5.2` none | Direct helper comparison only; Luna-none contract pass | `gpt-5.6-luna` none if reactivated | No production call while dormant | H |
| T025 | `core/generators/location_generator.py` | active | `gpt-5.2` none | Exercised as the T026 repair seam; Luna-none structured repair compatible | `gpt-5.6-luna` none | No accepted-result penalty observed | H / T026 seam |
| T026 | `core/generators/location_generator.py` | active | Luna-high | Luna none/medium, Terra none/low, and historical controls; lower profiles did not match blind module quality | `gpt-5.6-luna` high | Two CL calls, 34.9s and 42.7s; prior blind winner; current official-price calls ~$0.0063 and ~$0.0063 | blind Q, CL |
| T027 | `core/generators/location_summarizer.py` | active | `gpt-5.4-mini` none | Luna-none current strict pass | `gpt-5.6-luna` none | 3.477s, first attempt | P |
| T028 | `core/generators/module_builder.py` | active | `gpt-5.2` none | Luna-none strict pass and complete CL | `gpt-5.6-luna` none | 7.604s strict case; CL accepted two area-level calls | P, CL |
| T029 | `core/generators/module_builder.py` | active | `gpt-5.2` none | Luna-none pass and complete CL | `gpt-5.6-luna` none | CL first attempts, 4.3–5.3s | H, CL |
| T030 | `core/generators/module_builder.py` | active | `gpt-5.4-mini` none | Luna-none pass and complete CL | `gpt-5.6-luna` none | CL first request ~1.6s | H, CL |
| T031 | `core/generators/module_generator.py` | active | `gpt-5.2` none | Luna-none 5/5 and complete CL field sequence | `gpt-5.6-luna` none | Nine distinct field calls, not retries; complete module accepted | H, CL |
| T032 | `core/generators/module_stitcher.py` | active | `gpt-5.4-mini` none | Luna-none pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T033 | `core/generators/module_stitcher.py` | active | `gpt-5.4-mini` none | Luna-none pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T034 | `core/generators/monster_builder.py` | active | `gpt-5.2` none | Luna-none 3/3 JSON | `gpt-5.6-luna` none | median 2.193s; $0.001653 total | R |
| T035 | `core/generators/npc_builder.py` | active | `gpt-5.2` none | Luna-none 3/3 complete character objects; old wrapper validator was stale | `gpt-5.6-luna` none | median 10.788s; $0.012054 total | R + shape review |
| T036 | `core/generators/plot_generator.py` | active | `gpt-5.2` none | Luna-none pass and complete CL | `gpt-5.6-luna` none | CL short field calls accepted | H, CL |
| T037 | `core/generators/plot_generator.py` | active | `gpt-5.2` none | Luna-none pass and complete CL | `gpt-5.6-luna` none | CL two area calls ~14s each | H, CL |
| T038 | `core/managers/campaign_manager.py` | active | `gpt-5.4-mini` none | Luna-none pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T039 | `core/managers/campaign_manager.py` | active | `gpt-5-mini` | Luna-none and incumbent both violate the unstated object-type contract and take the identical code-owned fallback | `gpt-5.6-luna` none | Focused fallback reached in 1.615s / $0.000208 vs 15.638s / $0.002607; live completion also safely fell back | R, headless completion |
| T040 | `core/managers/combat_manager.py` | active | `gpt-5.4` none | Broad referee set: incumbent 4/4; Luna none 2/4, low 3/4, medium 2/4, high 2/4; Terra none/low/medium 3/4, high 2/4 | retain `gpt-5.4` none | No Luna/Terra profile through high met the no-regression gate | P |
| T041 | `core/managers/combat_manager.py` | active | `gpt-5.4-mini` none | Luna-none outputs passed scenario review | `gpt-5.6-luna` none | No retry increase observed | H |
| T042 | `core/managers/combat_manager.py` | active | `gpt-5.4-mini` none | Luna-none 3/3 | `gpt-5.6-luna` none | No retry increase observed | H |
| T043 | `core/managers/combat_manager.py` | active | `gpt-5.4` none | Current combat request contract and complete legacy-combat headless state path exercised; no independent replay capture | `gpt-5.6-luna` none | Lowest-cost recommendation; evidence weaker than T040 | headless + contract |
| T044 | `core/managers/combat_manager.py` | active | `gpt-5.4` none | Luna-none 5/5 | `gpt-5.6-luna` none | No retry increase observed | H |
| T045 | `core/managers/combat_manager.py` | active | `gpt-5.4` none | Luna-none 3/3 | `gpt-5.6-luna` none | No retry increase observed | H |
| T046 | `core/managers/initiative_tracker_ai.py` | active | `gpt-5.2` none | Correct baseline and Terra-none both 4/4; Luna none/low/medium and Terra low/medium each 3/4 | retain `gpt-5.2` none | Terra averaged 1.95s vs incumbent 2.07s: only ~0.12s faster and no material efficiency win | H-special |
| T047 | `core/managers/level_up_manager.py` | active | `gpt-5.2` none | Luna-none extended scaffold plus complete real interview; interrupted input saved no partial changes and completed retry persisted the correct level-up | `gpt-5.6-luna` none | Final generation 3.885s / $0.002649 vs incumbent 4.963s / $0.010550 | H, headless disk state |
| T048 | `core/managers/level_up_manager.py` | active | `gpt-5.2` none | Earlier incomplete candidate deltas were rejected; the complete Luna-none delta passed and was the one persisted, while the paired incumbent validator rejected it | `gpt-5.6-luna` none | Accepted validation 2.485s / $0.001772 vs incumbent 6.465s / $0.008926 | R, headless disk state |
| T049 | `core/managers/storage_processor.py` | active | `gpt-5-mini` | Current production create-storage and exact-inventory store-item operations both passed on first attempt | `gpt-5.6-luna` none | 1.366-2.340s / $0.000390 or less vs incumbent 5.515-7.141s / $0.001130 or more | R |
| T050 | `core/validation/character_effects_validator.py` | active | `gpt-5.2` none | Luna-none 3/3 JSON | `gpt-5.6-luna` none | median 2.166s; $0.001019 total | R |
| T051 | `core/validation/character_validator.py` | active | `gpt-5.2` none | Luna-none 3/3 strict validator | `gpt-5.6-luna` none | First-attempt passes | R |
| T052 | `core/validation/character_validator.py` | active | `gpt-5.2` none | Luna-none 3/3 JSON | `gpt-5.6-luna` none | median 1.928s; $0.000706 total | R |
| T053 | `core/validation/character_validator.py` | active | `gpt-5.2` none | Current complete Lux character passed the production parser/reconciler with the same authoritative no-change result | `gpt-5.6-luna` none | 2.135s / $0.001700 vs incumbent 2.942s / $0.015281 | R |
| T054 | `core/validation/character_validator.py` | active | `gpt-5.2` none | Luna-none 3/3 strict validator | `gpt-5.6-luna` none | median 1.950s; $0.001721 total | R |
| T059 | `core/validation/npc_codex_generator.py` | active | `gpt-5.2` none | Luna-none 3/3 | `gpt-5.6-luna` none | No retry increase observed | H |
| T063 | `main.py` | active | `gpt-5.4-mini` none | Luna-none 3/3 | `gpt-5.6-luna` none | No retry increase observed | H |
| T064 | `main.py` | active | `gpt-5.4-mini` none | Luna-none 3/3 | `gpt-5.6-luna` none | No retry increase observed | H |
| T065 | `main.py` | active | `gpt-5.2` low | Full 13-case validator: incumbent 7/13; Luna none 7/13, low 11/13, medium 8/13; Terra none 5/13, low 9/13, medium 6/13 | `gpt-5.6-luna` low | ~45.8s full set vs incumbent ~59.8s, with the best correctness and Luna pricing | P, headless |
| T066 | `main.py` | active | `gpt-5.4-mini` none | Luna-none pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T067 | `main.py` | active | `gpt-5.2` none | Luna-none production requests passed; identical-state solo test entered and persisted combat after one validation retry, matching incumbent | `gpt-5.6-luna` none | Lower exact cost/latency; real combat and transition exercised | R, headless |
| T077 | `updates/plot_update.py` | active | `gpt-5.2` none | Luna-none 2/2 strict validator | `gpt-5.6-luna` none | median 1.782s; $0.000227 total | R |
| T078 | `core/ai/effects_agent.py`; `updates/update_character_effects.py` | active | `gpt-5.2` none | Shared binding replay 3/3; both implementations reviewed for same contract | `gpt-5.6-luna` none | median 1.088s; $0.000692 total | R + source review |
| T079 | `updates/update_character_info.py` | active | `gpt-5-mini` low | Luna-none 6/6 strict pass | `gpt-5.6-luna` none | 1.09-1.84s, first attempts | P |
| T081 | `updates/update_encounter.py` | active | `gpt-5.2` none | Luna-none 3/3 JSON | `gpt-5.6-luna` none | median 1.267s; $0.000310 total | R |
| T082 | `utils/action_predictor.py` | active | `gpt-5-mini` low | Luna-none 3/3 strict validator | `gpt-5.6-luna` none | median 1.379s; $0.001225 total | R |
| T083 | `utils/bestiary_updater.py` | active | `gpt-5.4-mini` none | Incumbent and Luna-low preserved 4/4 explicit taxonomy values; Luna-none changed Beast to Monstrosity; Terra-none also passed | `gpt-5.6-luna` low | Luna-low is 10x cheaper than Terra-none; quality gate rules out Luna-none | H |
| T084 | `utils/compression/ai_narrative_compressor_agentic.py` | active | `gpt-5.4-mini` none | Luna-none 3/3 JSON | `gpt-5.6-luna` none | median 2.910s; $0.002633 total | R |
| T085 | `utils/compression/location_compressor.py` | active | `gpt-5.2` none | Luna-none 2/2 JSON | `gpt-5.6-luna` none | median 11.687s; $0.010313 total | R |
| T086 | `utils/level_up.py` | active | `gpt-5.2` none | Direct production NPC level-up validated level, HP bounds, XP reset/threshold, feature merge, and Action Surge | `gpt-5.6-luna` none | 1.318s / $0.000993 vs incumbent 1.892s / $0.009513 | R |
| T087 | `utils/npc_name_canonicalizer.py` | active | `gpt-5.4-mini` none | Luna-none scenario pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T088 | `utils/npc_reconciler.py` | active | `gpt-5.4-mini` none | Two broad runs: Luna-none and Luna-low each 11/12, equal to incumbent 11/12; all had one ambiguous-name error, while the complete classic repair remained valid | `gpt-5.6-luna` none | Equal aggregate accuracy; choose lower-effort Luna under the tie rule | H, CL |
| T089 | `utils/prompt_sanitizer.py` | active | `gpt-5.4-mini` none | Luna-none scenario pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T090 | `utils/quest_player_formatter.py` | active | `gpt-5.4-mini` none | Luna-none scenario pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T091 | `utils/reconcile_location_state.py` | active | `gpt-5.4-mini` none | Luna-none exact scenarios pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T092 | `utils/startup_wizard.py` | active | `gpt-5.2` none | Luna-none 3/3 current production, including production-valid final character | `gpt-5.6-luna` none | 1.861–8.642s by wizard phase | P |
| T093 | `utils/startup_wizard.py` | active | `gpt-5.4-mini` none | Luna-none scaffold pass | `gpt-5.6-luna` none | No retry increase observed | H |
| T094 | `web/web_interface.py` | active | `gpt-5.4-mini` none | Luna-none 8/8 combined web helper scenarios | `gpt-5.6-luna` none | No retry increase observed | H |
| T095 | `web/web_interface.py` | active | `gpt-5.4-mini` none | Luna-none 8/8 combined web helper scenarios | `gpt-5.6-luna` none | No retry increase observed | H |
| T096 | `core/ai/combat_agent.py` | active, opt-in path | `gpt-5.4` none | Luna-none intent extraction was exercised in a complete opt-in intent -> code commit -> narration sequence; combat state persisted | `gpt-5.6-luna` none | Same retry count as isolated incumbent; lower exact request cost | R, headless |
| T097 | `core/ai/combat_agent.py` | active, opt-in path | `gpt-5.4-mini` none/low/medium | Complete opt-in sequence exercised; Luna none->low->medium attempt propagation and bounded fallback were verified | `gpt-5.6-luna` none, then low, then medium | Three bounded attempts; code commits state before narration | R, headless |
| T098 | `core/generators/story_first/execution.py` | active | `gpt-5.2` none | Luna-none complete SF pass | `gpt-5.6-luna` none | 16.535s / $0.002545 vs incumbent 44.749s / $0.045029 | SF |
| T099 | `core/generators/story_first/execution.py` | active | `gpt-5.2` none | Luna-none/low failed graph, reachability, reciprocity, and connection gates; Terra-low passed semantic validation, compile, and map checks | `gpt-5.6-terra` low | 7.964s / $0.016048 vs incumbent 9.836s / $0.018252; premium required for correctness | SF, semantic Q |
| T100 | `core/generators/story_first/execution.py` | active | `gpt-5.2` none | Luna-none complete SF pass | `gpt-5.6-luna` none | 4.818s / $0.001543 vs incumbent 14.364s / $0.020613 | SF |
| T101 | `core/generators/story_first/execution.py` | active | `gpt-5.2` none | Luna-none left a duplicate NPC placement; Luna-low conserved the identity and removed the duplicate | `gpt-5.6-luna` low | 7.467s / $0.003075 vs incumbent 14.760s / $0.033231 | SF, semantic Q |
| T102 | `core/generators/story_first/execution.py` | active | `gpt-5.2` none | Luna-none complete SF pass | `gpt-5.6-luna` none | 3.596s / $0.000916 vs incumbent 6.299s / $0.009853 | SF |
| T103 | `core/generators/story_first/execution.py` | active | `gpt-5.2` none | Luna-none compiled every generated creature in complete SF; two calls were distinct creatures, not retries | `gpt-5.6-luna` none | 5.523s / $0.002437 vs incumbent 11.569s / $0.028721 for both calls | SF |
| T104 | `core/generators/module_builder.py` | active and enabled, 120s heal-forward timeout | Luna-high provisional | Luna-none, Terra-none, and Luna-high all passed the exact classic-build request and published one conserved `kira_vale` across `BGF001/A01` and `EAE001/B01`; the rebased timeout wrapper leaves request assembly unchanged | `gpt-5.6-luna` none | 5.128s / $0.002229 vs Terra 13.708s / $0.040100 and Luna-high 42.148s / $0.009561 | R, CL |

## Final distribution

- Luna-none: 68 callsites.
- Luna-low: T065, T083, T101.
- Luna-medium: T017.
- Luna-high: T026.
- Terra-low: T099.
- Retained incumbents: T040 (`gpt-5.4` none), T046 (`gpt-5.2` none).
- T097 additionally escalates Luna none → low → medium only on retry.

The recommendations cover 76/76 IDs. T024 is the only dormant callsite and its
recommendation applies if the helper is reactivated. Shared architecture defects
found during headless acceptance (T039's prompt/type mismatch, stale transition
validation context, campaign/party current-module disagreement, and the T109
storage persistence failure) are documented in the summary and are not
misrepresented as model-quality passes.
