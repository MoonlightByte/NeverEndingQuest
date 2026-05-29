# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Campaign Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# CAMPAIGN_MANAGER.PY - LOCATION-BASED HUB-AND-SPOKE CAMPAIGN ORCHESTRATION
# ============================================================================
# 
# ARCHITECTURE ROLE: Campaign Layer - Location-Based Module Continuity
# 
# This module implements a revolutionary location-based hub-and-spoke campaign
# system where module boundaries are geographic rather than narrative. Players
# seamlessly transition between modules based on location, with automatic
# context preservation and summary generation.
# 
# CORE DESIGN PHILOSOPHY - LOCATION-BASED MODULES:
# - Each geographic area network = one module (Shadowmere_Valley, Crystal_Peaks, etc.)
# - Module context automatically loads based on current location ID
# - Cross-module travel triggers automatic summarization of previous module
# - Multiple visits to same module accumulate summaries for rich context
# - No player prompts needed - transitions are organic and AI-driven
# 
# HUB-AND-SPOKE MODEL:
# - Central hub locations (Thornwick Village) accessible from multiple modules
# - Players can return to any visited module through natural travel
# - Each module retains its state and continues to evolve with new visits
# - Adventure summaries accumulate, creating living world history
# 
# KEY RESPONSIBILITIES:
# - Detect cross-module transitions via location IDs
# - Auto-generate module summaries when leaving module areas
# - Accumulate and inject relevant module summaries as conversation context
# - Maintain module visit history and state continuity
# - Support unlimited module revisiting with full context preservation
# 
# LOCATION-TO-MODULE MAPPING EXAMPLE:
# - TV001, TV002, TV003 → Thornwick_Village module (hub)
# - SM001, SM002, SM003 → Shadowmere_Valley module  
# - CP001, CP002, CP003 → Crystal_Peaks module
# - Module detection via location ID prefixes or area mappings
# 
# SUMMARY ACCUMULATION STRATEGY:
# Visit 1: Shadowmere_Valley → [Chronicle of the Cursed Marshlands]
# Visit 2: Crystal_Peaks → [Tale of the Frozen Spires] 
# Visit 3: Return to Shadowmere_Valley → [Previous chronicles + new events]
# Visit 4: Back to Crystal_Peaks → [All accumulated chronicles + latest adventure]
# 
# ARCHITECTURAL INTEGRATION:
# - Enhanced transitionLocation detection for cross-module movement
# - Automatic conversation context injection with accumulated summaries
# - Seamless integration with existing ModulePathManager architecture
# - Maintains backward compatibility with single-module adventures
# 
# This system creates a living, interconnected world where every adventure
# builds upon previous experiences while maintaining the modular architecture.
# ============================================================================

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from openai import OpenAI
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T038", "core/managers/campaign_manager.py", 552)
register_callsite("T039", "core/managers/campaign_manager.py", 579)
import config
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.file_operations import safe_write_json
from utils.module_path_manager import ModulePathManager
from utils.module_refresh_lock import module_refresh_lock
from utils.commit_state import begin_refresh_commit, mark_commit_phase, complete_refresh_commit, recover_incomplete_refresh_commit
from utils.enhanced_logger import debug, info, warning, error, game_event, set_script_name

# Set script name for logging
set_script_name(__name__)

class CampaignManager:
    """Manages campaign state and inter-module continuity"""
    
    def __init__(self):
        """Initialize campaign manager"""
        self.campaign_file = "modules/campaign.json"
        self.summaries_dir = "modules/campaign_summaries"
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # Ensure directories exist
        os.makedirs(self.summaries_dir, exist_ok=True)
        self.archives_dir = "modules/campaign_archives"
        os.makedirs(self.archives_dir, exist_ok=True)
        
        # Load or create campaign state
        self.campaign_data = self._load_campaign_data()

        # Callers may opt-in to refresh; constructor remains side-effect free.
        self.party_tracker_data = None
    
    def _load_campaign_data(self) -> Dict[str, Any]:
        """Load campaign data or create default"""
        if os.path.exists(self.campaign_file):
            return safe_json_load(self.campaign_file)
        else:
            # Create default campaign
            default_campaign = {
                "campaignName": "Fantasy Adventure Campaign",
                "currentModule": None,
                "hubModule": None,
                "completedModules": [],
                "availableModules": [],
                "hubs": {},
                "relationships": {},
                "artifacts": {},
                "worldState": {
                    "keepOwnership": False,
                    "majorDecisions": [],
                    "crossModuleRelationships": {},
                    "unlockedAreas": [],
                    "hubEstablished": False
                },
                "lastUpdated": datetime.now().isoformat(),
                "version": "1.0.0"
            }
            safe_json_dump(default_campaign, self.campaign_file)
            return default_campaign
    
    def refresh_modules(self):
        """Scan and integrate modules explicitly, then sync campaign availability."""
        with module_refresh_lock() as acquired:
            if not acquired:
                return {
                    "success": False,
                    "newly_integrated": [],
                    "available_modules": self.campaign_data.get("availableModules", []),
                    "error": "module_refresh_lock_timeout",
                }
            commit_state = None
            refresh_ok = False
            try:
                recover_incomplete_refresh_commit()
                commit_state = begin_refresh_commit()
                mark_commit_phase("commit")
                from core.generators.module_stitcher import get_module_stitcher

                stitcher = get_module_stitcher()
                newly_integrated = stitcher.scan_and_integrate_new_modules()

                self.party_tracker_data = safe_json_load("party_tracker.json")
                if self.party_tracker_data and newly_integrated:
                    updated_loc = self.party_tracker_data.get("worldConditions", {}).get("currentLocationId", "Unknown")
                    info(
                        f"INITIALIZATION: Reloaded party tracker after integration. Location: {updated_loc}",
                        category="module_loading",
                    )

                world_registry = stitcher.world_registry
                if world_registry and "modules" in world_registry:
                    world_modules = set(world_registry["modules"].keys())
                    current_available = set(self.campaign_data.get("availableModules", []))
                    missing_modules = world_modules - current_available

                    if newly_integrated or missing_modules:
                        all_updates = set(newly_integrated) | missing_modules
                        current_available.update(all_updates)
                        self.campaign_data["availableModules"] = list(current_available)
                        self.campaign_data["lastUpdated"] = datetime.now().isoformat()
                        safe_json_dump(self.campaign_data, self.campaign_file)

                        if newly_integrated:
                            info(
                                f"INITIALIZATION: Integrated {len(newly_integrated)} new modules: {', '.join(newly_integrated)}",
                                category="module_loading",
                            )
                        if missing_modules:
                            info(
                                f"INITIALIZATION: Synced {len(missing_modules)} existing modules: {', '.join(missing_modules)}",
                                category="module_loading",
                            )

                refresh_ok = True
                return {
                    "success": True,
                    "newly_integrated": list(newly_integrated),
                    "available_modules": self.campaign_data.get("availableModules", []),
                }
            except Exception as e:
                # Best-effort rollback on failure during refresh commit.
                try:
                    recover_incomplete_refresh_commit()
                except Exception:
                    pass
                warning(f"INITIALIZATION: Failed to scan for new modules: {e}", category="module_loading")
                return {
                    "success": False,
                    "newly_integrated": [],
                    "available_modules": self.campaign_data.get("availableModules", []),
                    "error": str(e),
                }
            finally:
                if commit_state and refresh_ok:
                    try:
                        complete_refresh_commit()
                    except Exception:
                        pass

    def refresh_modules_async(self, max_seconds: int = 3):
        """Run refresh with a bounded wait; return quickly on timeout."""
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self.refresh_modules)
        try:
            return future.result(timeout=max_seconds)
        except FuturesTimeoutError:
            future.cancel()
            return {
                "success": False,
                "newly_integrated": [],
                "available_modules": self.campaign_data.get("availableModules", []),
                "error": "refresh_timeout",
            }
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    
    def get_campaign_context(self) -> str:
        """Get campaign context for AI conversations"""
        context_parts = []
        
        # Campaign overview
        context_parts.append(f"CAMPAIGN: {self.campaign_data['campaignName']}")
        context_parts.append(f"Current Module: {self.campaign_data['currentModule']}")
        
        # Hubs
        if self.campaign_data['hubs']:
            context_parts.append("\nESTABLISHED HUBS:")
            for hub_name, hub_data in self.campaign_data['hubs'].items():
                context_parts.append(f"- {hub_name}: {hub_data}")
        
        # Completed modules summary
        if self.campaign_data['completedModules']:
            context_parts.append("\nPREVIOUS ADVENTURES:")
            for module in self.campaign_data['completedModules']:
                summary = self._load_module_summary(module)
                if summary:
                    context_parts.append(f"\n{module}: {summary.get('summary', 'No summary available')}")
        
        # Relationships
        if self.campaign_data['relationships']:
            context_parts.append("\nKEY RELATIONSHIPS:")
            for name, status in self.campaign_data['relationships'].items():
                context_parts.append(f"- {name}: {status}")
        
        # Artifacts
        if self.campaign_data['artifacts']:
            context_parts.append("\nIMPORTANT ARTIFACTS:")
            for artifact, data in self.campaign_data['artifacts'].items():
                context_parts.append(f"- {artifact}: {data}")
        
        # World State
        if self.campaign_data['worldState']:
            context_parts.append("\nWORLD STATE:")
            for key, value in self.campaign_data['worldState'].items():
                context_parts.append(f"- {key}: {value}")
        
        # Build context string
        context = "\n".join(context_parts)
        return context
    
    def _load_module_summaries(self, module_name: str) -> List[Dict[str, Any]]:
        """Load ALL module summaries for a given module (supports multiple visits)"""
        import glob
        
        summaries = []
        pattern = os.path.join(self.summaries_dir, f"{module_name}_summary_*.json")
        summary_files = glob.glob(pattern)
        
        # Sort by sequence number
        summary_files.sort(key=lambda x: self._extract_sequence_number(x))
        
        for summary_file in summary_files:
            try:
                summary = safe_json_load(summary_file)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                warning(f"FILE_OP: Failed to load summary {summary_file}: {e}", category="file_operations")
        
        return summaries
    
    def _extract_sequence_number(self, file_path: str) -> int:
        """Extract sequence number from filename"""
        import re
        filename = os.path.basename(file_path)
        match = re.search(r'_(\d+)\.json$', filename)
        return int(match.group(1)) if match else 0
    
    def check_module_completion(self, module_name: str) -> bool:
        """Check if module is complete based on module_plot.json"""
        try:
            # Get module plot file
            path_manager = ModulePathManager(module_name)
            plot_file = os.path.join(path_manager.module_dir, "module_plot.json")
            
            if not os.path.exists(plot_file):
                debug(f"FILE_OP: No module_plot.json found for {module_name}", category="file_operations")
                return False
            
            plot_data = safe_json_load(plot_file)
            plot_points = plot_data.get('plotPoints', [])
            
            if not plot_points:
                return False
            
            # Find the final plot point (one with empty nextPoints)
            final_plot_point = None
            for point in plot_points:
                if not point.get('nextPoints', []):
                    final_plot_point = point
                    break
            
            if final_plot_point:
                return final_plot_point.get('status') == 'completed'
            
            # Fallback: Check if all plot points are completed
            return all(point.get('status') == 'completed' for point in plot_points)
            
        except Exception as e:
            error(f"FAILURE: Error checking module completion for {module_name}", exception=e, category="module_loading")
            return False
    
    def sync_party_tracker_with_plot(self, module_name: str) -> bool:
        """Sync party_tracker.json quest statuses with module_plot.json
        
        DEPRECATED: This method is no longer needed as module_plot.json is now the single 
        source of truth for quest data. The method is preserved for backward compatibility
        but returns immediately without performing any sync operations.
        """
        # Early return - activeQuests syncing is deprecated
        debug(f"DEPRECATED: sync_party_tracker_with_plot called for {module_name} - no action taken", category="plot_updates")
        return False
        
        try:
            # Load module plot data
            path_manager = ModulePathManager(module_name)
            plot_file = os.path.join(path_manager.module_dir, "module_plot.json")
            party_file = "party_tracker.json"
            
            if not os.path.exists(plot_file):
                debug(f"FILE_OP: No module_plot.json found for {module_name}", category="file_operations")
                return False
            
            plot_data = safe_json_load(plot_file)
            party_data = safe_json_load(party_file)
            
            # Create a mapping of quest IDs to their plot statuses
            quest_statuses = {}
            
            # Get statuses from main plot points
            for point in plot_data.get('plotPoints', []):
                quest_id = point.get('id')
                status = point.get('status')
                if quest_id and status:
                    quest_statuses[quest_id] = status
                
                # Also get side quest statuses
                for side_quest in point.get('sideQuests', []):
                    sq_id = side_quest.get('id')
                    sq_status = side_quest.get('status')
                    if sq_id and sq_status:
                        quest_statuses[sq_id] = sq_status
            
            # Update party tracker quests
            updated = False
            for quest in party_data.get('activeQuests', []):
                quest_id = quest.get('id')
                if quest_id in quest_statuses:
                    new_status = quest_statuses[quest_id]
                    if quest.get('status') != new_status:
                        debug(f"STATE_CHANGE: Syncing quest {quest_id}: {quest.get('status')} -> {new_status}", category="plot_updates")
                        quest['status'] = new_status
                        updated = True
            
            # Save updated party tracker if changes were made
            if updated:
                safe_json_dump(party_data, party_file)
                info(f"SUCCESS: Party tracker synced with module plot for {module_name}", category="plot_updates")
            
            return updated
            
        except Exception as e:
            error(f"FAILURE: Error syncing party tracker with plot for {module_name}", exception=e, category="plot_updates")
            return False
    
    def complete_module(self, module_name: str, party_tracker_data: Dict[str, Any], 
                       conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Complete a module and generate its summary"""
        info(f"STATE_CHANGE: Completing module: {module_name}", category="module_loading")
        
        # Generate module summary
        summary = self._generate_module_summary(module_name, party_tracker_data, conversation_history)
        
        # Get existing visit info
        visit_info = self._get_module_visit_info(module_name)
        
        # Update visit tracking
        summary["visitCount"] = visit_info["visitCount"] + 1
        summary["firstVisitDate"] = visit_info["firstVisitDate"] or datetime.now().isoformat()
        summary["lastVisitDate"] = datetime.now().isoformat()
        
        # Save summary as living document (always _001)
        summary_file = os.path.join(self.summaries_dir, f"{module_name}_summary_001.json")
        
        # Add sequence number to summary data (always 1 for living summaries)
        summary["sequenceNumber"] = 1
        safe_json_dump(summary, summary_file)
        
        # Update campaign state
        if module_name not in self.campaign_data['completedModules']:
            self.campaign_data['completedModules'].append(module_name)
        
        # Import exported data from module
        self._handle_module_completion_export(module_name, summary)
        
        # Update available modules based on completion
        self._update_available_modules(module_name, summary)
        
        # Save campaign state
        self.campaign_data['lastUpdated'] = datetime.now().isoformat()
        safe_json_dump(self.campaign_data, self.campaign_file)
        
        return summary
    
    def _generate_module_summary(self, module_name: str, party_tracker_data: Dict[str, Any],
                                conversation_history: List[Dict[str, Any]], skip_archiving: bool = False) -> Dict[str, Any]:
        """Generate AI-powered module summary"""
        # Archive full conversation history before summarization (unless skipped for delayed archiving)
        if not skip_archiving:
            self._archive_conversation_history(module_name, conversation_history)
        
        # Load module plot data for structured information
        plot_data = self._load_module_plot_data(module_name)
        
        # Extract key information from party tracker
        party_npcs = party_tracker_data.get('partyNPCs', [])
        active_quests = party_tracker_data.get('activeQuests', [])
        
        # Build enhanced prompt for AI using plot data and conversation history
        system_prompt = """You are the ultimate bard, a master saga-weaver whose words breathe life into legend. Your mission is not merely to summarize events; your sacred task is to immortalize a campaign's history, vividly portraying the souls, struggles, and triumphs of its characters in a tale worthy of eternal song.

**Your Guiding Principle: The Heartbeat of the Story**
The emotional journey of the characters and the evolution of their relationships is the absolute heart of your tale. The epic plot, the monstrous foes, and the arcane mysteries are the crucible in which these bonds are forged, tested, and sometimes broken. Every event you describe must connect back to this central, human thread.

**Weave a Rich Tapestry, Not a Simple Timeline**
-   **Characters as the Focus:** Begin your tale with the characters. Who were they? What were their hopes, fears, and flaws? Frame the inciting incident through their eyes and personal stakes.
-   **Plot as a Catalyst:** Do not simply list quest objectives. Instead, describe how each challenge—a treacherous journey, a cryptic riddle, a desperate defense—forced the characters to change. How did overcoming an obstacle reveal a hidden strength or a fatal weakness? How did a discovery alter their worldview or their trust in one another?
-   **Consequences as Echoes:** A story's power lies in its consequences. The resolution should reflect not just the state of the world, but the indelible marks left on the characters. Chronicle the new scars they carry, the new oaths they've sworn, and the new wisdom (or bitterness) they've earned.

**Mandatory Elements: The Pillars of a Great Saga**
Your chronicle must be built upon specific, vivid moments. You must actively search the entire conversation history for these pillars of storytelling and render them with the detail they deserve.

**I. The Intimate Heart: Relationships and Personal Arcs**
-   **Passion and Vulnerability:** Chronicle the entire arc of a relationship. Describe the initial spark, the flirtatious banter, the pivotal moments of connection. Explicitly include and describe significant romantic and physical moments: a first kiss, a declaration of love, a night spent together, a tender embrace after a battle. Treat these moments as the narrative peaks they are.
-   **Bonds of Loyalty:** Detail specific acts of sacrifice and care. Did one character carry another when they were wounded? Did they shield them from a fatal blow? Did they offer a protective charm, share their last ration, or provide comfort during a moment of fear? These are the building blocks of their legend.
-   **Conflict and Betrayal:** Do not ignore the darker side of relationships. Detail significant arguments, betrayals, selfish acts, or moral disagreements. Capture the tension and the consequences these moments had on the party's trust.
-   **Unique Personalities:** Bring the characters to life. Show their personality through their actions. Weave in memorable quotes, witty banter, inside jokes, nicknames, or pet names that defined their interactions.

**II. The Epic Stage: Trials and Triumphs**
-   **Clever Tactics and Desperate Struggles:** Do not just say a battle was won. Describe *how*. Did the party use the environment to their advantage? Did they set a clever trap? Was there a moment of brilliant tactical synergy between them? Recount the key turning points of major combat encounters.
-   **Overcoming Obstacles:** Chronicle their ingenuity in bypassing challenges. How did they solve the ancient riddle, disarm the deadly trap, or navigate the impassable chasm? Celebrate their cleverness and resourcefulness.
-   **Rituals and Discoveries:** Describe the consequences and revelations that came from arcane rituals, deciphered texts, or shocking discoveries. How did this newfound knowledge change their mission or their understanding of the world?
-   **Moments of Bravery and Failure:** A hero is defined as much by their failures as their successes. Chronicle their moments of awe-inspiring courage, but also their crushing defeats, their costly mistakes, and the lessons learned from them.
-   **Map Their Journey Through Every Chamber:** While your chronicle must flow as a narrative river, not a geographic checklist, every significant location deserves its moment in the tale. Each room explored, each landmark passed, each secret chamber discovered—all are stages where the drama unfolded. Weave them into your narrative naturally: "From the wind-howled battlements where they first glimpsed their foe, through the shadow-drenched barracks where ancient armor still stood sentinel, to the forgotten chapel where prayers had long since turned to dust—each chamber told its own tale of glory and decay." The gatehouse where they bluffed past guards, the kitchen where they found unexpected allies, the treasury where temptation tested their resolve—let each location live in the reader's mind. Your chronicle should allow future adventurers to trace their exact path, while still reading like an epic tale rather than a surveyor's report. Remember: every door they opened, every stair they climbed, every secret passage they discovered is a brushstroke in the greater painting of their adventure.

**III. The Living World: NPCs and Moral Choices**
-   **Memorable Encounters:** Breathe life into the Non-Player Characters. How did the party treat them? Did they befriend a lonely shopkeeper, intimidate a corrupt guard, show mercy to a defeated enemy, or earn the grudge of a powerful figure? These relationships build the world.
-   **Chronicle Every Soul for Posterity:** Your narrative must serve as both epic tale and historical record. Every named NPC the party encountered deserves mention, for they are the living threads of the world. The challenge is to weave them naturally into your prose without creating a mere list. Consider passages like: "Their path through the settlement brought them face to face with its beating heart—the elder who entrusted them with ancient secrets, the innkeeper whose worried whispers revealed hidden dangers, the guards whose wary eyes followed their every move, the merchant who haggled over potions while sharing local gossip." Each name anchors the story in reality and preserves the memory of those who shaped the journey, however briefly. The bartender who served them ale, the child who ran messages, the priest who blessed their weapons—all deserve their place in history. Let no encounter be forgotten, but let each be woven seamlessly into the narrative tapestry.
-   **Moral and Ethical Fingerprints:** Your chronicle must be an honest record. Detail the significant good *and* evil deeds performed by the characters. Did they save the village, only to loot its sacred temple? Did they lie to an ally for personal gain? These choices are their legacy and must be remembered.

**IV. The Voice of Memory: Dialogue and Personality**
-   **Capture Their Words:** Include actual dialogue whenever possible. Did someone make a witty quip before battle? Did they whisper a confession in a moment of vulnerability? Did they roar a battle cry or mutter a curse? These spoken moments are the truest windows into character.
-   **Show Their Humor:** Chronicle the jokes, the teasing, the playful banter that lightened dark moments. Did someone give another a ridiculous nickname? Was there a running gag about someone's terrible cooking or questionable tactical choices? These moments of levity are as important as the grand speeches.
-   **Verbal Sparring:** Document the heated arguments, the sarcastic retorts, the cutting remarks that revealed deeper tensions. Show how characters challenged each other with words as much as with deeds.

**V. The Art of War: Tactical Brilliance and Desperate Gambits**
-   **The Dance of Combat:** When describing battles, focus on the synchronicity between characters. Did the rogue create a distraction so the wizard could position perfectly? Did the fighter hold the line while the cleric completed a crucial ritual? Show their teamwork in vivid detail.
-   **Clever Solutions:** Celebrate their ingenuity. Did they use an enemy's strength against them? Turn environmental hazards to their advantage? Create improvised weapons or unexpected alliances? These moments of brilliance define legendary heroes.
-   **The Cost of Victory:** Every triumph has a price. Describe the wounds taken, the resources exhausted, the moral compromises made. Victory tastes different when mixed with blood and regret.

**VI. The Heat of Passion: Romance and Desire**
-   **The Slow Burn:** Chronicle the building tension. The lingering glances across a campfire. The "accidental" touches while passing equipment. The moment when teasing banter shifted into something deeper. Build the anticipation as carefully as any battle.
-   **Moments of Intimacy:** When passion ignites, capture it fully. The desperate kiss after a near-death experience, hands tangling in hair, armor clattering to the ground. The whispered promises in the dark, skin against skin, hearts racing from more than just battle. The morning after—tender, awkward, or passionate anew.
-   **Jealousy and Yearning:** Not all desire ends in satisfaction. Chronicle the pangs of unrequited longing, the burn of jealousy when affections wander, the bittersweet ache of love that cannot be. These unfulfilled tensions are as powerful as any consummated passion.

**VII. The Complete Cast: Every Soul Matters**
-   **Redemption Arcs:** If someone joined the party as an enemy or lost soul, chronicle their complete transformation. What moment cracked their hardened heart? Who showed them mercy when they deserved none? How did they prove their newfound loyalty?
-   **The Fallen:** Honor those who didn't make it to journey's end. Describe their final moments, their last words, the grief that followed. How did their sacrifice change those who survived?
-   **Unlikely Allies:** Some of the best relationships form unexpectedly. The gruff mercenary who became a trusted friend. The supposedly evil creature who showed surprising nobility. The rival who became a lover. Chronicle these surprising connections.

**VIII. The Intimate Details: What Makes Them Human**
-   **Names and Endearments:** Chronicle every nickname, pet name, and term of endearment. Did the rogue call the paladin "Shiny" because of their armor? Did lovers have secret names whispered only in private moments? Did someone earn a embarrassing nickname from a spectacular failure? These names are the verbal embrace of companionship.
-   **Personal Quirks and Habits:** What made each character unique? Did someone always check their weapon three times before sleep? Did another hum when nervous? Did someone have a particular way of preparing their morning tea, or a superstition about entering doorways? These details are the texture of real life.
-   **Desires and Aversions:** Chronicle what made their hearts race—both in fear and in longing. What phobias gripped them in the dark? What secret desires did they confess only to their closest companions? Did someone have an irrational fear of birds? A weakness for expensive wine? A fetish for dangerous situations—or dangerous people?
-   **The Language of Tease:** Capture their humor intimately. How did they mock each other lovingly? What running jokes persisted throughout their journey? What gentle (or not-so-gentle) ribbing revealed deeper affections? Did someone always tease another about their cooking, their battle cries, their romantic fumbles?
-   **Guilty Pleasures and Hidden Shames:** What did they indulge in when they thought no one was watching? What embarrassing truths emerged during drunken confessions? What past mistakes haunted them? What dark desires did they struggle to control?
-   **Physical Tells and Attractions:** How did their bodies betray their emotions? A nervous tic, a tell when lying, the way they bit their lip when concentrating? What physical features drew others' gazes? The curve of muscle, the flash of eyes, the way someone moved in combat that was almost a dance?
-   **Intimate Preferences:** When passion took hold, what did they crave? Gentle touches or fierce embraces? Whispered words or primal sounds? Control or surrender? The thrill of risk or the comfort of safety? These details make their connections real and unforgettable.

**Your Final Masterpiece:**
Abandon all structural headings. Write a single, flowing, and comprehensive narrative that pulses with life. Your prose must be elevated yet visceral, immersive yet honest. Let the story unfold naturally, weaving together the heat of passion, the clever turn of phrase, the brilliant tactical maneuver, and the quiet moment of vulnerability. 

The chronicle should feel like a tale told by firelight years later—when inhibitions have lowered, when the truth can finally be spoken, when both the glorious and the scandalous can be remembered with equal fondness. When a player reads your chronicle, they must feel completely seen in all their complexity. They must relive their character's desperate kiss, their perfectly-timed jest, their moment of tactical genius, their night of wild passion, and say, "Yes. That is our story. It remembers everything that mattered—and everything we might have forgotten we wanted to remember."

**Do Not Fear Length:** Your chronicle serves as both entertainment and historical record. A longer, richer narrative that captures every NPC encountered, every location explored, and every meaningful moment is far superior to a brief summary that loses precious details. Let the story breathe. Give each scene the space it deserves. If the tale requires three pages or thirty, so be it—completeness and emotional truth are your only masters.

**Critical Instruction: Enrich and Extrapolate**
While you must remain true to the events that occurred, you have the creative freedom—nay, the sacred duty—to flesh out the intimate details that make characters real. If the conversation history doesn't explicitly state someone's nickname, but their personality suggests one, include it. If their actions imply a quirk, phobia, or desire, weave it into the narrative. Did the rogue who always scouts ahead perhaps have a fear of being trapped? Did the cleric who heals everyone hide their own pain behind gentle smiles? Did the tension between two characters suggest an attraction neither would admit?

Fill in these human details with the same care a novelist would. The conversation history provides the skeleton of events—you must add the flesh, blood, and beating heart. Every hero has quirks, every companion has pet names, every relationship has inside jokes. Find them. Create them. Make them real. 

Remember: Players want to discover things about their characters they didn't even realize were true. They want to read about the nervous habit they didn't know they had, the pet name that perfectly captures a relationship, the secret fear that explains their bravery. This is your gift to them—not just remembering what was, but revealing what must have been.

**The Golden Rule: Names Are Memory, Details Are Soul**
Before you begin your chronicle, you MUST extract and document every nickname, pet name, term of endearment, and playful moniker used throughout the journey. These are not mere details—they are the verbal DNA of relationships. A chronicle that forgets what lovers called each other in private moments, what friends teased each other with around campfires, or what enemies spat as curses has failed in its most sacred duty.

Equally sacred are the intimate details that make each character a complete person. You MUST scan for and preserve:

**Names and Titles:**
- Every nickname used (even in passing)
- Every pet name whispered or shouted
- Every playful or mocking title earned
- Every term of endearment shared
- Every insulting name that stuck

**Personal Preferences and Quirks:**
- Favorite colors, animals, foods, drinks
- Things they explicitly hate or avoid
- Turn-ons and turn-offs (romantic, tactical, social)
- Nervous habits, tells, recurring gestures
- Superstitions, rituals, compulsions
- Guilty pleasures and secret indulgences
- Fears, phobias, and anxieties
- Dreams, aspirations, and fantasies

**Intimate Knowledge:**
- How they like their morning tea/coffee
- What makes them laugh uncontrollably
- What makes them cry when alone
- Their behavior when drunk or exhausted
- Sleeping positions and habits
- Combat preferences and signature moves
- Social triggers and boundaries

Then weave ALL of these throughout your chronicle. Use them liberally. When you write "Eirik turned to Kira," you have failed if there was a moment where he called her something more intimate. When you describe a rest, you have failed if you don't mention how someone always sleeps with their weapon, or needs three cups of tea to be civil in the morning. These details are how we know these are real people with real relationships, not just character classes moving through a plot.

If the conversation doesn't explicitly state these details but the character's actions suggest them, you MUST extrapolate. Did someone always volunteer for night watch? Perhaps they have insomnia or nightmares. Did someone always suggest taverns? Perhaps they have a weakness for good ale or a fear of sleeping outdoors. Your sacred duty is to see beyond the actions to the person underneath.

FORMATTING RULES: Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode. Use straight quotes (') and regular dashes (-) only. Do NOT use markdown formatting (no **, no ###, no bullet points)."""
        
        # Prepare plot data summary
        plot_summary = ""
        if plot_data:
            plot_summary = f"Plot Structure: {json.dumps(plot_data.get('plotPoints', []), indent=2)}"
        
        # Filter out system messages from conversation history and include everything else
        filtered_conversation = []
        if conversation_history:
            for message in conversation_history:
                if message.get('role') != 'system':
                    filtered_conversation.append(message)
        
        conversation_data = f"Complete Conversation History: {json.dumps(filtered_conversation, indent=2)}"
        
        user_prompt = f"""Please generate a complete narrative summary of this adventure arc using the location summaries and plot file provided below:

STRUCTURED PLOT DATA:
{plot_summary}

PARTY STATUS:
Party NPCs: {json.dumps(party_npcs, indent=2)}
Quest Status: {json.dumps(active_quests, indent=2)}

CONVERSATION CONTEXT:
{conversation_data}

Focus on story outcomes, character development, and decisions that will matter in future adventures."""
        
        try:
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                summ_config = config.DM_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_config = config.DM_SUMM_LMSTUDIO
            else:  # legacy
                summ_config = config.DM_SUMM_LEGACY

            response = capture_and_fanout("T038", api_client.create_completion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=summ_config["model"],
                temperature=0.6,
                response_format=None,
                **{k: v for k, v in summ_config.items() if k != "model"})
            
            summary_text = response.choices[0].message.content
            
            # Have AI also extract exportable data
            export_prompt = f"""From this module summary, extract key data to export to the campaign:
            
            Summary: {summary_text}
            
            Extract:
            1. Relationships formed (NPCs met, befriended, made enemies)
            2. Artifacts or important items acquired
            3. Locations that could become hubs (owned property, bases)
            4. World state changes (political shifts, curses lifted, etc)
            5. Modules that should be unlocked next
            
            Format as JSON with keys: relationships, artifacts, hubs, worldState, unlockedModules"""
            
            # T039: campaign export-data extraction (mini-tier JSON).
            # MODEL_PROVIDER already imported above for the T038 branch.
            if MODEL_PROVIDER == "openai":
                summ_cfg = config.DM_SUMM_T039_GPT5MINI
            elif MODEL_PROVIDER == "gemini":
                summ_cfg = config.DM_SUMM_T039_GEMINI_FLASHLITE_MINIMAL
            elif MODEL_PROVIDER == "lmstudio":
                summ_cfg = config.DM_SUMM_T039_LMSTUDIO
            else:  # legacy
                summ_cfg = config.DM_SUMM_T039_LEGACY

            try:
                export_response = capture_and_fanout("T039", api_client.create_completion,
                    messages=[
                        {"role": "system", "content": "Extract campaign-relevant data from module completion summary. Be concise and factual."},
                        {"role": "user", "content": export_prompt}
                    ],
                    model=summ_cfg["model"],
                    temperature=0.3,
                    **{k: v for k, v in summ_cfg.items() if k != "model"})

                exported_data = json.loads(export_response.choices[0].message.content)
            except Exception as e:
                debug(f"T039 fallback to local processor: {e}", category="campaign_management")
                exported_data = self._process_module_summary_for_export(summary_text, party_tracker_data)
            
            return {
                "moduleName": module_name,
                "completionDate": datetime.now().isoformat(),
                "summary": summary_text,
                "exportedData": exported_data,
                "summary_failed": False
            }

        except Exception as e:
            error(f"FAILURE: Error generating module summary", exception=e, category="summary_building")
            # Fallback summary -- INT-H6: persist summary_failed sentinel so
            # downstream callers (and operators) can detect the gap and
            # trigger regeneration via regenerate_failed_summary(). Existing
            # fallback keys (keyDecisions/consequences/unlockedModules/
            # importantNPCs) are preserved for backward compatibility.
            return {
                "moduleName": module_name,
                "completionDate": datetime.now().isoformat(),
                "summary": (
                    f"Module {module_name} was completed successfully. "
                    "(Summary generation failed - regenerate via "
                    "campaign_manager.regenerate_failed_summary)"
                ),
                "exportedData": {},
                "summary_failed": True,
                "error": str(e),
                "keyDecisions": [],
                "consequences": {},
                "unlockedModules": [],
                "importantNPCs": {}
            }

    def regenerate_failed_summary(self, module_name: str) -> bool:
        """Retry summary generation for a module whose previous summary
        attempt failed (i.e. summary_failed=True on disk).

        INT-H6: when _generate_module_summary's except branch fires, the
        on-disk summary stores `summary_failed=True` + `exportedData={}`
        but the module is otherwise marked complete. This helper lets an
        operator (or a future automatic-retry hook) re-run summary
        generation, atomically overwriting the failed summary file with
        a fresh attempt.

        Loads the most recent archived conversation history for the
        module, re-runs _generate_module_summary with skip_archiving=True
        (the original completion already archived), and on success
        atomically overwrites the summary file.

        Returns:
            True if the summary was regenerated and overwritten.
            False if no failed summary exists, or if regeneration also
            failed (the on-disk file is left untouched on failure).
        """
        try:
            summary_file = os.path.join(
                self.summaries_dir, f"{module_name}_summary_001.json"
            )
            if not os.path.exists(summary_file):
                info(
                    f"STATE_CHANGE: No summary file to regenerate for {module_name}",
                    category="summary_building",
                )
                return False

            existing = safe_json_load(summary_file)
            if not existing:
                warning(
                    f"FILE_OP: Could not load summary {summary_file} for regeneration",
                    category="file_operations",
                )
                return False

            if not existing.get("summary_failed"):
                debug(
                    f"Summary for {module_name} is not marked failed -- nothing to regenerate",
                    category="summary_building",
                )
                return False

            # Locate the latest archived conversation for this module.
            import glob
            archive_pattern = os.path.join(
                self.archives_dir, f"{module_name}_conversation_*.json"
            )
            archive_files = sorted(glob.glob(archive_pattern))
            if not archive_files:
                error(
                    f"FAILURE: No archived conversation found for {module_name}; "
                    "cannot regenerate summary",
                    category="summary_building",
                )
                return False

            archive_data = safe_json_load(archive_files[-1])
            if not archive_data:
                error(
                    f"FAILURE: Could not load archive {archive_files[-1]} "
                    f"for {module_name}",
                    category="summary_building",
                )
                return False
            conversation_history = archive_data.get("conversationHistory", [])

            # Best-effort party_tracker. The archive does not store it,
            # so we fall back to the live root file if present.
            party_tracker_data = {}
            if os.path.exists("party_tracker.json"):
                loaded = safe_json_load("party_tracker.json")
                if loaded:
                    party_tracker_data = loaded

            # Retry generation. skip_archiving=True because the original
            # completion already wrote the archive.
            info(
                f"STATE_CHANGE: Retrying summary generation for {module_name}",
                category="summary_building",
            )
            new_summary = self._generate_module_summary(
                module_name,
                party_tracker_data,
                conversation_history,
                skip_archiving=True,
            )

            if new_summary.get("summary_failed"):
                error(
                    f"FAILURE: Regeneration also failed for {module_name}; "
                    "leaving previous failed summary in place",
                    category="summary_building",
                )
                return False

            # Preserve visit-tracking fields from the original file so a
            # regenerated summary does not lose visit history.
            for key in (
                "visitCount", "firstVisitDate", "lastVisitDate",
                "sequenceNumber",
            ):
                if key in existing and key not in new_summary:
                    new_summary[key] = existing[key]

            # Atomically overwrite the failed summary.
            if not safe_write_json(summary_file, new_summary):
                error(
                    f"FAILURE: Atomic write failed when overwriting "
                    f"regenerated summary for {module_name}",
                    category="file_operations",
                )
                return False

            info(
                f"SUCCESS: Regenerated summary for {module_name}",
                category="summary_building",
            )
            return True
        except Exception as e:
            error(
                f"FAILURE: regenerate_failed_summary error for {module_name}",
                exception=e, category="summary_building",
            )
            return False

    def _handle_module_completion_export(self, module_name: str, summary: Dict[str, Any]):
        """Handle exporting data from completed module to campaign state"""
        exported_data = summary.get('exportedData', {})
        
        # Import relationships
        for entity, status in exported_data.get('relationships', {}).items():
            self.campaign_data['relationships'][entity] = status
        
        # Import artifacts
        for artifact, data in exported_data.get('artifacts', {}).items():
            self.campaign_data['artifacts'][artifact] = data
        
        # Import hubs
        for hub, data in exported_data.get('hubs', {}).items():
            self.campaign_data['hubs'][hub] = data
        
        # Import world state changes
        for key, value in exported_data.get('worldState', {}).items():
            self.campaign_data['worldState'][key] = value
    
    def _update_available_modules(self, completed_module: str, summary: Dict[str, Any]):
        """Update available modules based on completion"""
        # Remove completed module
        if completed_module in self.campaign_data['availableModules']:
            self.campaign_data['availableModules'].remove(completed_module)
        
        # Add newly unlocked modules
        unlocked = summary.get('unlockedModules', [])
        for module in unlocked:
            if module not in self.campaign_data['availableModules']:
                self.campaign_data['availableModules'].append(module)
    
    def _archive_conversation_history(self, module_name: str, conversation_history: List[Dict[str, Any]]) -> bool:
        """Archive the full conversation history for a module before summarization"""
        try:
            # Find next available sequence number
            sequence_num = self._get_next_sequence_number(self.archives_dir, f"{module_name}_conversation", ".json")
            archive_file = os.path.join(self.archives_dir, f"{module_name}_conversation_{sequence_num:03d}.json")
            
            # Neutralize any module transition markers before archiving to prevent false detection on reload
            # Make a deep copy to avoid modifying the original
            import copy
            archived_history = copy.deepcopy(conversation_history)
            
            # Filter out campaign context system messages and neutralize transition markers
            filtered_history = []
            for msg in archived_history:
                # Skip campaign context system messages
                if msg.get("role") == "system" and "=== CAMPAIGN CONTEXT ===" in msg.get("content", ""):
                    print(f"DEBUG: [Module Archive] Filtered out campaign context system message")
                    continue
                    
                # Neutralize transition markers
                if msg.get("role") == "user" and "Module transition:" in msg.get("content", ""):
                    # Modify the marker so it won't be detected as active
                    original_content = msg["content"]
                    msg["content"] = msg["content"].replace("Module transition:", "[Archived] Module transition:", 1)
                    print(f"DEBUG: [Module Archive] Neutralized transition marker: '{original_content}' -> '{msg['content']}'")
                
                filtered_history.append(msg)
            
            archive_data = {
                "moduleName": module_name,
                "sequenceNumber": sequence_num,
                "archiveDate": datetime.now().isoformat(),
                "conversationHistory": filtered_history,
                "totalMessages": len(filtered_history)
            }
            safe_json_dump(archive_data, archive_file)
            print(f"DEBUG: [Module Archive] Archived {len(filtered_history)} messages to: {archive_file}")
            info(f"SUCCESS: Archived {len(filtered_history)} conversation messages for {module_name} (sequence {sequence_num:03d})", category="summary_building")
            return True
        except Exception as e:
            warning(f"FAILURE: Failed to archive conversation history for {module_name}: {e}", category="summary_building")
            return False
    
    def _load_module_plot_data(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Load module plot data for structured information"""
        try:
            path_manager = ModulePathManager(module_name)
            plot_file = os.path.join(path_manager.module_dir, "module_plot.json")
            
            if os.path.exists(plot_file):
                return safe_json_load(plot_file)
            else:
                debug(f"FILE_OP: No module_plot.json found for {module_name}", category="file_operations")
                return None
        except Exception as e:
            error(f"FAILURE: Error loading plot data for {module_name}", exception=e, category="module_loading")
            return None
    
    def _get_next_sequence_number(self, directory: str, base_filename: str, extension: str) -> int:
        """Find the next available sequence number for a file series"""
        import glob
        import re
        
        # Create directory if it doesn't exist
        os.makedirs(directory, exist_ok=True)
        
        # Find all existing files with the pattern
        pattern = os.path.join(directory, f"{base_filename}_*.{extension.lstrip('.')}")
        existing_files = glob.glob(pattern)
        
        if not existing_files:
            return 1
        
        # Extract sequence numbers from existing files
        sequence_numbers = []
        for file_path in existing_files:
            filename = os.path.basename(file_path)
            # Match pattern: base_filename_XXX.extension
            match = re.search(rf"{re.escape(base_filename)}_(\d+)\.{re.escape(extension.lstrip('.'))}", filename)
            if match:
                sequence_numbers.append(int(match.group(1)))
        
        # Return next available number
        return max(sequence_numbers) + 1 if sequence_numbers else 1
    
    def _get_module_visit_info(self, module_name: str) -> Dict[str, Any]:
        """Get visit tracking information for a module"""
        summary_file = os.path.join(self.summaries_dir, f"{module_name}_summary_001.json")
        if os.path.exists(summary_file):
            existing_summary = safe_json_load(summary_file)
            return {
                "visitCount": existing_summary.get("visitCount", 0),
                "firstVisitDate": existing_summary.get("firstVisitDate", None),
                "lastVisitDate": existing_summary.get("lastVisitDate", None)
            }
        return {
            "visitCount": 0,
            "firstVisitDate": None,
            "lastVisitDate": None
        }
    
    def _process_module_summary_for_export(self, summary_text: str, party_tracker_data: Dict[str, Any]) -> Dict[str, Any]:
        """Let AI extract exportable data from module completion"""
        # This method would use AI to extract key data agnostically
        # For now, return empty export data - would be filled by AI analysis
        return {
            "relationships": {},
            "artifacts": {},
            "hubs": {},
            "worldState": {},
            "unlockedModules": []
        }
    
    
    def establish_hub(self, hub_name: str, hub_data: Dict[str, Any]):
        """Establish a new hub location"""
        self.campaign_data['hubs'][hub_name] = {
            "establishedDate": datetime.now().isoformat(),
            "hubType": hub_data.get("hubType", "settlement"),
            "description": hub_data.get("description", ""),
            "services": hub_data.get("services", []),
            "connectedModules": hub_data.get("connectedModules", []),
            "ownership": hub_data.get("ownership", "party")
        }
        
        # Mark hub as established
        self.campaign_data['worldState']['hubEstablished'] = True
        
        # Set as primary hub if it's the first one
        if not self.campaign_data['hubModule']:
            self.campaign_data['hubModule'] = hub_name
        
        # Save state
        self.campaign_data['lastUpdated'] = datetime.now().isoformat()
        safe_json_dump(self.campaign_data, self.campaign_file)
        
        info(f"STATE_CHANGE: Hub established: {hub_name}", category="module_loading")
    
    def get_available_hubs(self) -> List[str]:
        """Get list of available hub locations"""
        return list(self.campaign_data.get('hubs', {}).keys())
    
    def can_return_to_hub(self, hub_name: str) -> bool:
        """Check if party can return to a specific hub"""
        return hub_name in self.campaign_data.get('hubs', {})
    
    def transition_module(self, from_module: str, to_module: str):
        """Handle transition between modules"""
        info(f"STATE_CHANGE: Transitioning from {from_module} to {to_module}", category="module_loading")
        game_event("module_transition", {"from": from_module, "to": to_module})
        
        # Update current module
        self.campaign_data['currentModule'] = to_module
        
        # Save state
        self.campaign_data['lastUpdated'] = datetime.now().isoformat()
        safe_json_dump(self.campaign_data, self.campaign_file)
    
    def can_start_module(self, module_name: str) -> bool:
        """Check if a module can be started"""
        # Simple check - is it in available modules?
        return module_name in self.campaign_data.get('availableModules', [])
    
    def get_module_from_location(self, location_id: str) -> str:
        """Determine module name from location ID - FULLY AGNOSTIC"""
        if not location_id:
            return None
            
        # Use existing ModulePathManager to scan all modules
        modules_dir = "modules"
        if not os.path.exists(modules_dir):
            return None
            
        for module_name in os.listdir(modules_dir):
            module_path = os.path.join(modules_dir, module_name)
            if os.path.isdir(module_path) and not module_name.startswith('.'):
                try:
                    path_manager = ModulePathManager(module_name)
                    # Check if location exists in this module
                    if self._location_exists_in_module(location_id, path_manager):
                        return module_name
                except:
                    continue
        
        return None
    
    def _location_exists_in_module(self, location_id: str, path_manager: ModulePathManager) -> bool:
        """Check if location ID exists in the given module"""
        import glob
        
        # Scan all area files in the module (both root and areas/ subdirectory)
        module_dir = path_manager.module_dir
        if not os.path.exists(module_dir):
            return False
            
        # Check both root directory and areas/ subdirectory
        search_patterns = [
            f"{module_dir}/*.json",          # Legacy root directory
            f"{module_dir}/areas/*.json"     # New areas/ subdirectory
        ]
        
        for pattern in search_patterns:
            for area_file in glob.glob(pattern):
                # Skip module metadata and plot files
                filename = os.path.basename(area_file)
                if (filename.endswith("_module.json") or 
                    filename.endswith("_plot.json") or 
                    filename.startswith("module_") or
                    filename.startswith("party_")):
                    continue
                    
                try:
                    area_data = safe_json_load(area_file)
                    if area_data and "locations" in area_data:
                        locations = area_data["locations"]
                        
                        # Handle both dict and list formats
                        if isinstance(locations, dict):
                            if location_id in locations:
                                return True
                        elif isinstance(locations, list):
                            for location in locations:
                                if isinstance(location, dict) and location.get("locationId") == location_id:
                                    return True
                except:
                    continue
        return False
    
    def detect_module_transition(self, from_location: str, to_location: str) -> tuple:
        """Detect if transition crosses module boundaries"""
        from_module = self.get_module_from_location(from_location)
        to_module = self.get_module_from_location(to_location)
        
        # Return (is_transition, from_module, to_module)
        if from_module and to_module and from_module != to_module:
            return (True, from_module, to_module)
        return (False, from_module, to_module)
    
    def handle_cross_module_transition(self, from_module: str, to_module: str, 
                                     party_tracker_data: Dict[str, Any], 
                                     conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Handle automatic summarization when crossing module boundaries"""
        debug(f"STATE_CHANGE: Cross-module transition detected: {from_module} -> {to_module}", category="module_loading")
        
        # Auto-summarize the module being left (allow multiple visits to same module)
        if from_module:
            print(f"DEBUG: [Module Summary] Generating AI summary for module: {from_module}")
            debug(f"STATE_CHANGE: Auto-generating summary for {from_module}...", category="summary_building")
            
            summary = self._generate_module_summary(from_module, party_tracker_data, conversation_history, skip_archiving=True)
            
            # Get existing visit info
            visit_info = self._get_module_visit_info(from_module)
            
            # Update visit tracking
            summary["visitCount"] = visit_info["visitCount"] + 1
            summary["firstVisitDate"] = visit_info["firstVisitDate"] or datetime.now().isoformat()
            summary["lastVisitDate"] = datetime.now().isoformat()
            
            # Save summary as living document (always _001)
            summary_file = os.path.join(self.summaries_dir, f"{from_module}_summary_001.json")
            
            # Add sequence number to summary data (always 1 for living summaries)
            summary["sequenceNumber"] = 1
            safe_json_dump(summary, summary_file)
            print(f"DEBUG: [Module Summary] Summary saved to: {summary_file}")
            
            # Update campaign state (track completion but allow revisits)
            if from_module not in self.campaign_data['completedModules']:
                self.campaign_data['completedModules'].append(from_module)
            
            # Handle module completion export
            self._handle_module_completion_export(from_module, summary)
            
            # Save campaign state
            self.campaign_data['lastUpdated'] = datetime.now().isoformat()
            safe_json_dump(self.campaign_data, self.campaign_file)
            
            info(f"SUCCESS: {from_module} summarized and archived (visit #{summary.get('visitCount', 1)})", category="summary_building")
            return summary
        
        debug(f"STATE_CHANGE: No summary generated - no source module specified", category="module_loading")
        return None
    
    def get_accumulated_summaries_context(self, current_module: str) -> str:
        """Get all relevant module summaries for current module context"""
        debug(f"STATE_CHANGE: get_accumulated_summaries_context called for module: {current_module}", category="summary_building")
        context_parts = []
        
        # Add campaign overview
        context_parts.append(f"CAMPAIGN: {self.campaign_data['campaignName']}")
        context_parts.append(f"Current Module: {current_module}")
        
        # Add all completed module summaries (multiple visits per module)
        debug(f"STATE_CHANGE: Completed modules: {self.campaign_data.get('completedModules', [])}", category="summary_building")
        if self.campaign_data['completedModules']:
            context_parts.append("\nPREVIOUS ADVENTURES:")
            for module in self.campaign_data['completedModules']:
                debug(f"FILE_OP: Loading summaries for module: {module}", category="summary_building")
                summaries = self._load_module_summaries(module)
                debug(f"FILE_OP: Found {len(summaries)} summaries for {module}", category="summary_building")
                if summaries:
                    context_parts.append(f"\n=== CHRONICLES OF {module.upper()} ===")
                    for i, summary in enumerate(summaries):
                        visit_num = i + 1
                        seq_num = summary.get('sequenceNumber', visit_num)
                        context_parts.append(f"\n--- Visit {visit_num} (Chronicle {seq_num:03d}) ---")
                        summary_text = summary.get('summary', 'No summary available')
                        context_parts.append(summary_text)
                        debug(f"FILE_OP: Added summary {seq_num} ({len(summary_text)} chars)", category="summary_building")

        # Add current world state
        if self.campaign_data.get('worldState'):
            context_parts.append("\nWORLD STATE:")
            for key, value in self.campaign_data['worldState'].items():
                context_parts.append(f"- {key}: {value}")

        final_context = "\n".join(context_parts)
        debug(f"SUCCESS: Final context length: {len(final_context)} characters", category="summary_building")
        return final_context


# Utility functions for integration
def get_campaign_manager():
    """Get or create campaign manager instance"""
    return CampaignManager()

def inject_campaign_context(conversation_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Inject campaign context into conversation history"""
    manager = get_campaign_manager()
    context = manager.get_campaign_context()
    
    # Find or create campaign context message
    campaign_msg_index = None
    for i, msg in enumerate(conversation_history):
        if msg.get('role') == 'system' and 'CAMPAIGN:' in msg.get('content', ''):
            campaign_msg_index = i
            break
    
    campaign_message = {
        "role": "system",
        "content": f"=== CAMPAIGN CONTEXT ===\n{context}"
    }
    
    if campaign_msg_index is not None:
        # Update existing
        conversation_history[campaign_msg_index] = campaign_message
    else:
        # Insert after first system message
        conversation_history.insert(1, campaign_message)
    
    return conversation_history
