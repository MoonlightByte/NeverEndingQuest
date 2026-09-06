/**
 * FROZEN SOCKET CONTRACT — extracted from web/web_interface.py (2026-07-16 workflow
 * p4-frontend-inventory: 31 client->server handlers, 56 server->client emits;
 * 2026-08 map-tab workflow added request_map_data/map_data_response; the
 * server sends a spoiler-safe map projection, see types/map.ts).
 * This file is the single source of truth for every socket event the player app uses.
 * Do NOT add events here without verifying the server side exists.
 */

import type { MapDataPayload } from '../types/map'

// ---------- shared shapes ----------
export type MessageType =
  | 'narration'
  | 'user-input'
  | 'system'
  | 'info'
  | 'error'
  | 'startup'
  | 'debug';
export interface GameMessage {
  type: MessageType;
  content: string;
  timestamp?: string;
  /** Stable server identity used to merge cache/live/reconnect delivery. */
  message_id?: string;
}

export interface RequestMeta { request_id?: string }
export interface ResponseMeta { request_id?: string; revision?: number; server_instance_id?: string }

/**
 * Capabilities are additive and optional so a current player can still attach
 * to a server from before the React protocol existed.  In particular, the
 * client must not add a metadata argument to a historically zero-argument
 * event until the server explicitly advertises `request_metadata`.
 */
export interface UiProtocolCapabilities {
  protocol_version?: number;
  request_metadata?: boolean;
}

export type PlayerDataResponse =
  | {
      dataType: 'stats' | 'inventory' | 'spells';
      data: Record<string, unknown> | null;
      error?: string;
      /** Benign empty state (no character created yet); never an error. */
      notice?: string;
      request_id?: string;
      revision?: number;
      server_instance_id?: string;
    }
  | {
      dataType: 'npcs';
      data: Array<Record<string, unknown>> | null;
      error?: string;
      request_id?: string;
      revision?: number;
      server_instance_id?: string;
    };

// ---------- client -> server (31) ----------
export interface ClientEvents {
  user_input: { input: string };
  action: {
    action: 'listSaves' | 'saveGame' | 'restoreGame' | 'deleteSave' | 'nuclearReset' | 'recover_startup_handoff';
    parameters?: Record<string, unknown>;
  };
  start_game: undefined;
  user_exit: undefined;
  request_player_data: { dataType: 'stats' | 'inventory' | 'spells' | 'npcs'; request_id?: string };
  request_location_data: RequestMeta | undefined;
  request_party_data: RequestMeta | undefined;
  request_initiative_data: RequestMeta | undefined;
  request_plot_data: RequestMeta | undefined;
  request_storage_data: RequestMeta | undefined;
  request_ui_snapshot: RequestMeta | undefined;
  request_map_data: RequestMeta | undefined;
  request_npc_saves: { npcName: string };
  request_npc_skills: { npcName: string };
  request_npc_spells: { npcName: string };
  request_npc_inventory: { npcName: string };
  generate_image: { prompt: string; request_id?: string; source_message_id?: string };
  request_module_list: undefined;
  // --- local-edition operator settings (hidden when VITE_EDITION=hosted) ---
  get_model_provider: undefined;
  set_model_provider: { provider: 'legacy' | 'openai' | 'gemini' | 'lmstudio' };
  get_local_endpoint: undefined;
  set_local_endpoint: { base_url: string; api_key?: string; model: string };
  get_openai_key: undefined;
  set_openai_key: { api_key: string };
  get_gemini_key: undefined;
  set_gemini_key: { api_key: string };
  test_local_endpoint: { base_url: string; api_key?: string; model?: string };
  // --- operator/toolkit scope: NOT bound in the player app (toolkit page owns these) ---
  start_build: { module_name: string; narrative: string; num_areas: number; locations_per_area: number; per_area_locations?: number[] };
  cancel_build: undefined;
  generate_unified_assets: { module_name: string; assets: unknown[]; options: { overwrite: boolean; generate_images: boolean; generate_descriptions: boolean } };
  test_module_progress: undefined;
  trigger_update: undefined;
}

/**
 * Exact legacy Socket.IO packet arity for every client event.  Keep this table
 * exhaustive: Socket.IO distinguishes `emit("event")` from
 * `emit("event", {})`, and older Flask handlers with no `data` parameter will
 * raise a TypeError when handed the latter.
 */
export const CLIENT_EVENT_ARITY = {
  user_input: 1,
  action: 1,
  start_game: 0,
  user_exit: 0,
  request_player_data: 1,
  request_location_data: 0,
  request_party_data: 0,
  request_initiative_data: 0,
  request_plot_data: 0,
  request_storage_data: 0,
  request_ui_snapshot: 0,
  request_map_data: 0,
  request_npc_saves: 1,
  request_npc_skills: 1,
  request_npc_spells: 1,
  request_npc_inventory: 1,
  generate_image: 1,
  request_module_list: 0,
  get_model_provider: 0,
  set_model_provider: 1,
  get_local_endpoint: 0,
  set_local_endpoint: 1,
  get_openai_key: 0,
  set_openai_key: 1,
  get_gemini_key: 0,
  set_gemini_key: 1,
  test_local_endpoint: 1,
  start_build: 1,
  cancel_build: 0,
  generate_unified_assets: 1,
  test_module_progress: 0,
  trigger_update: 0,
} as const satisfies Record<keyof ClientEvents, 0 | 1>;

// ---------- server -> client (56) ----------
export interface RestoreResult {
  message: string;
  pending?: boolean;
  restore_outcome?: 'selected_applied' | 'previous_restored' | 'unchanged' | 'recovery_required';
  can_resume?: boolean;
  restart_required?: boolean;
}

export interface ServerEvents {
  connected: {
    data: string;
    capabilities?: UiProtocolCapabilities;
    server_instance_id?: string;
  };
  version_status: { update_available: boolean; local_version: string; remote_version: string; message: string };
  cached_messages: GameMessage[];
  game_resumed: { is_processing: boolean; message: string };
  game_output: GameMessage;
  debug_output: { type: 'debug'; content: string; timestamp: string };
  status_update: { message: string; is_processing: boolean; recovery_required?: boolean };
  startup_status: { status: 'in_progress' | 'ready' | 'failed'; phase: string; startupAttemptId?: string };
  game_started: { message: string };
  startup_recovery_response: { status: string; error?: string; retryAfterSeconds?: number; expectedStartupAttemptId?: string };
  ui_state_snapshot: {
    request_id?: string;
    revision: number;
    server_instance_id: string;
    game_running: boolean;
    is_processing: boolean;
    status_message: string;
    startup?: { status: 'idle' | 'in_progress' | 'ready' | 'failed'; phase: string; startupAttemptId?: string };
    operations?: {
      restore?: RestoreResult | null;
      compression?: (Record<string, unknown> & { event?: string; status?: string }) | null;
      module?: ServerEvents['module_creation_progress'] | null;
      update?: { status: string; log: string[]; error?: string | null; complete?: string | null } | null;
    };
  };
  system_message: { content: string };
  error: { message: string };
  save_list_response: Array<Record<string, unknown>>;
  restore_complete: RestoreResult;
  reset_complete: { message: string };
  player_data_response: PlayerDataResponse;
  location_data_response: { data: { currentLocation: string; currentArea: string; currentLocationId: string; currentAreaId: string; time: string; day: number | string; month: string; year: number | string } | null; error?: string; request_id?: string; revision?: number; server_instance_id?: string };
  npc_details_response: { npcName: string; data: Record<string, unknown> | null; modalType: 'saves' | 'skills' | 'spells'; error?: string };
  npc_inventory_response: { npcName: string; data: unknown[] | null; error?: string };
  party_data_response: { members: Array<Record<string, unknown>>; location_npcs?: Array<Record<string, unknown>>; error?: string; request_id?: string; revision?: number; server_instance_id?: string };
  initiative_data_response: { active: boolean; combatants: Array<Record<string, unknown>>; round?: number; recovery?: { required: boolean; message: string; actions: string[] } | null; error?: string; request_id?: string; revision?: number; server_instance_id?: string };
  plot_data_response: { data: { plotPoints: Array<{ id: string; title: string; description: string; status: string; sideQuests?: unknown[] }> } | null; error?: string; request_id?: string; revision?: number; server_instance_id?: string };
  storage_data_response: { data: Record<string, unknown>; error?: string; request_id?: string; revision?: number; server_instance_id?: string };
  map_data_response: { data: MapDataPayload | null; error?: string; request_id?: string; revision?: number; server_instance_id?: string };
  exit_acknowledged: { message: string };
  provider_changed: { provider: string };
  local_endpoint_changed: { base_url: string; model: string; has_key: boolean };
  openai_key_status: { has_key: boolean };
  gemini_key_status: { has_key: boolean };
  local_endpoint_test_result: { ok: boolean; detail: string };
  image_generated: { image_url: string; prompt: string; request_id?: string; source_message_id?: string };
  image_generation_error: { message: string; request_id?: string; source_message_id?: string };
  token_update: { tpm: number; rpm: number; total_tokens: number };
  /** #214 D-214-4=A: background startup-welcome liveness (never input-locking). */
  welcome_progress: { message: string };
  compression_start: { total_sections: number };
  compression_progress: { completed: number; total: number; from_cache: boolean };
  compression_complete: { reduction_percentage: number; original_size: number; compressed_size: number };
  compression_error: { error: string };
  episodic_upgrade_start: { completed: number; total: number; message: string; stage: string };
  episodic_upgrade_progress: { completed: number; total: number; message: string; stage: string };
  episodic_upgrade_complete: { completed: number; total: number; message: string; stage: string };
  module_list_response: Array<Record<string, unknown>>;
  // --- toolkit/operator scope (received only on toolkit page; typed for completeness) ---
  module_creation_progress: {
    build_id?: string;
    stage: number;
    total_stages: number;
    stage_name: string;
    percentage: number;
    message: string;
    status?: string;
    terminal?: boolean;
    success?: boolean;
    error?: string;
  };
  generation_progress: { current: number; total: number; monster: string; percent: number };
  generation_complete: Record<string, unknown>;
  generation_error: { error: string };
  npc_portrait_progress: { current: number; total: number; npc_name: string; status: string };
  npc_generation_complete: { module_name: string; pack_name: string; successful: string[]; failed: string[]; total: number };
  build_started: { message: string };
  module_progress: { stage: number; stage_name: string; percentage: number; message: string };
  module_complete: { module_name: string; message: string };
  module_error: { error: string };
  unified_generation_progress: { percent: number; message: string; asset_id?: string; asset_name?: string; status?: string };
  unified_generation_complete: { success: boolean; message?: string; generated_count?: number; error?: string };
  update_log: { message: string };
  update_error: { error: string };
  update_complete: { message: string };
  bestiary_update_progress: { status: 'started'; requested: number; message: string; job_id: string };
  bestiary_update_complete: { requested: number; added: number; skipped: number; failed: number; error: string | null; success: boolean; status: string; message: string; job_id: string };
  bestiary_update_error: { requested: number; added: number; skipped: number; failed: number; error: string; success: false; status: 'failed'; job_id: string };
  npc_description_progress: { current: number; total: number; npc_name: string; status: 'success' | 'error'; error?: string; job_id: string };
  npc_description_complete: { job_id: string; success: boolean; status: string; module_name: string; provider: string; completed: number; failed: number; total: number; error?: string; errors?: unknown[] };
}

export type ClientEventName = keyof ClientEvents;
export type ServerEventName = keyof ServerEvents;
