# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# ACTION_PREDICTOR.PY - INTELLIGENT MODEL SELECTION SYSTEM
# ============================================================================
#
# ARCHITECTURE ROLE: Token Optimization - Action Prediction Agent
#
# This module implements an intelligent action prediction system that analyzes
# user input to determine whether it will require game actions, enabling
# optimal model selection for token cost optimization.
#
# KEY RESPONSIBILITIES:
# - Analyze user input for action requirements
# - Predict whether JSON actions will be needed in AI response
# - Enable routing to appropriate model (mini vs full)
# - Track prediction accuracy for optimization
#
# OPTIMIZATION STRATEGY:
# - Use full model for action prediction (high accuracy)
# - Route simple conversations to mini model (cost savings)
# - Route action-requiring inputs to full model (quality maintenance)
# - Track accuracy metrics for continuous improvement
#
# TOKEN SAVINGS APPROACH:
# Small prediction cost + appropriate model routing = significant overall savings
# - Prediction: ~200 tokens (full model)
# - Savings: Route to mini model when no actions needed
# - Net Result: Major cost reduction for conversation-heavy gameplay
#
# ARCHITECTURAL INTEGRATION:
# - Called by main.py before get_ai_response()
# - Uses condensed prompt based on system_prompt.txt analysis
# - Provides boolean prediction with reasoning
# - Logs accuracy metrics for optimization tracking
# ============================================================================

import json
import config
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T082", "utils/action_predictor.py", 152)

# Action prediction system prompt (condensed from full system analysis)
ACTION_PREDICTION_PROMPT = """You are an action prediction agent for the world's most popular 5th edition roleplaying game AI system. Analyze user input to determine if it requires JSON actions in the AI response.

RETURN TRUE if input requires any of these JSON actions:
- updateCharacterInfo: inventory changes, stat modifications, item use
- transitionLocation: moving to new locations
- createEncounter: combat initiation
- updatePlot: story progression, quest completion, plot status queries
- levelUp: character advancement
- exitGame: ending session
- storageInteraction: item storage/retrieval
- updatePartyTracker: module travel
- updatePartyNPCs: NPCs joining/leaving the party (recruitment requests, asking for help/backup, NPCs volunteering, dismissing companions)

ALWAYS RETURN TRUE for:
- Questions about plot status ("are all plots resolved?", "what quests remain?")
- Requests to complete quests or plot points
- Any mention of quest/plot completion or resolution
- Questions about module completion status
- Questions about inventory, currency, or equipment ("how much gold?", "what's in my inventory?", "check my equipment")

NOTE: updateTime is excluded from prediction as it's called for almost every interaction.

SPECIAL: Return FALSE for simple rest requests ("I take a long rest", "short rest", "we rest") - these have formulaic responses the mini model can handle.

RETURN FALSE for pure roleplay:
- Questions about lore/NPCs/world
- Simple dialogue ("I say...", "Tell me about...")
- Planning discussions without action commitment
- Describing surroundings/situations
- Character conversations

KEY PATTERNS:

TRUE INDICATORS:
- "I pick up/take/grab" → inventory change
- "I go to/travel to/enter" → location change
- "I cast/use/drink" → character update
- "I attack/fight" → combat encounter
- "I store/retrieve" → storage action
- "I give/trade/exchange" → inventory transfer
- Activities with time duration → time update
- Dice roll reports ("I rolled a X") → often trigger character/plot updates based on success
- Investigation actions ("search for", "look for", "examine") → may update plot with discoveries
- Error corrections that reference specific mechanics → often require re-doing actions
- Story-advancing dialogue that triggers responses → often updates plot
- Calling out or initiating contact at new locations → often triggers NPC encounters and plot updates
- Agreement to story directions ("let's do it", "aye") → often commits to plot advancement
- NPC recruitment requests ("who can you spare?", "can anyone help?", "we need backup", "join us") -> party composition changes
- Responses accepting NPC offers ("yes", "sure", "that would be helpful") when context suggests NPC joining -> updatePartyNPCs
- Inventory/currency/equipment queries ("how much gold?", "what's in my inventory?", "check equipment") -> requires full model for data synthesis

CRITICAL PATTERNS TO CATCH:
- Dice roll outcomes ("natural 20", "I rolled") → Usually leads to updateCharacterInfo/updatePlot
- Active investigations ("search for signs", "look for tracks") → Often updates plot with findings
- Error correction notes about game mechanics → Typically require action updates when corrected
- Dialogue with spirits/NPCs that seeks information → Often triggers plot updates with responses
- Location-based calls ("anyone home?", "hello?") → Often initiates NPC encounters and plot progression
- Commitment statements in story contexts → Often advances plot when player commits to direction

FALSE INDICATORS:
- "What do you think?"
- "Tell me about..."
- "How are you feeling?"
- "I say [dialogue]"
- "What can you see?"
- "Describe the..."
- Pure narrative descriptions without player action commitment

RESPOND: {"requires_actions": true/false, "reason": "brief explanation"}

Examples:
- "I pick up the sword" → TRUE (inventory change)
- "I go to the tavern" → TRUE (location change)
- "What's in this room?" → FALSE (asking for description)
- "I tell the guard about the bandits" → FALSE (pure dialogue)
- "I take a long rest" → FALSE (simple rest - mini model can handle)
- "I rolled a natural 20!" → TRUE (dice outcomes typically trigger character/plot updates)
- "I search for signs of danger" → TRUE (investigation actions often update plot with discoveries)
- "Error Note: Your previous response failed validation" → TRUE (error corrections often require re-doing actions)
- "I ask the spirits about the darkness" → TRUE (dialogue seeking information often triggers plot updates)
- "I call out, anyone home?" → TRUE (location-based contact often initiates NPC encounters)
- "Aye, let's do it" → TRUE (commitment statements often advance plot when in story context)
- "Not all the main plot points are resolved" → TRUE (plot status query needs full model)
- "Are all quests complete?" → TRUE (quest/plot status always needs full model)
- "What plots remain?" → TRUE (plot queries require full model for proper updatePlot handling)
- "Who can you spare?" → TRUE (NPC recruitment request requires updatePartyNPCs action)
- "Can anyone help us?" → TRUE (asking for NPC assistance likely results in party composition change)
- "Join us, Kira" → TRUE (direct recruitment requires updatePartyNPCs action)
- "How much gold do I have?" -> TRUE (inventory/currency query requires cross-referencing character data)
- "What's in my inventory?" -> TRUE (inventory status needs full model for accurate data synthesis)
- "Check Kira's equipment" -> TRUE (party member inventory query needs full model)"""

def predict_actions_required(user_input):
    """
    Predict whether user input will require JSON actions in the AI response.
    
    Args:
        user_input (str): The user's input message
        
    Returns:
        dict: {
            "requires_actions": bool,
            "reason": str,
            "confidence": str
        }
    """
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        pred_config = config.ACTION_PRED_GPT5MINI_LOW
    elif MODEL_PROVIDER == "gemini":
        pred_config = config.ACTION_PRED_GEMINI_FLASH_MINIMAL
    elif MODEL_PROVIDER == "lmstudio":
        pred_config = config.ACTION_PRED_LMSTUDIO
    else:  # legacy
        pred_config = config.ACTION_PRED_LEGACY

    try:
        # Call action prediction model
        response = capture_and_fanout("T082", api_client.create_completion,
            messages=[
                {"role": "system", "content": ACTION_PREDICTION_PROMPT},
                {"role": "user", "content": f"Analyze this user input: '{user_input}'"}
            ],
            model=pred_config["model"],
            temperature=0.1,
            **{k: v for k, v in pred_config.items() if k != "model"})
        
        # Parse the prediction response
        prediction_text = response.choices[0].message.content.strip()
        
        # Try to parse as JSON
        try:
            prediction = json.loads(prediction_text)
            requires_actions = prediction.get("requires_actions", False)
            reason = prediction.get("reason", "No reason provided")
        except json.JSONDecodeError:
            # Fallback parsing if JSON format is malformed
            requires_actions = "true" in prediction_text.lower()
            reason = "Fallback parsing due to JSON error"
        
        return {
            "requires_actions": requires_actions,
            "reason": reason,
            "confidence": "high" if len(reason) > 10 else "low"
        }
        
    except Exception as e:
        # Fallback to conservative prediction (assume actions required)
        return {
            "requires_actions": True,
            "reason": f"Error in prediction: {str(e)}",
            "confidence": "error"
        }

def extract_actual_actions(ai_response):
    """
    Extract actions from AI response to compare with prediction.
    Excludes updateTime as it's called for almost every interaction.
    
    Args:
        ai_response (str): The AI's JSON response
        
    Returns:
        list: List of action types found in the response (excluding updateTime)
    """
    try:
        # Parse the AI response JSON
        response_data = json.loads(ai_response)
        actions = response_data.get("actions", [])
        
        # Extract action types, excluding updateTime
        action_types = []
        for action in actions:
            if isinstance(action, dict) and "action" in action:
                action_type = action["action"]
                # Exclude updateTime as it's called for almost every interaction
                if action_type != "updateTime":
                    action_types.append(action_type)
        
        return action_types
        
    except (json.JSONDecodeError, TypeError):
        # If we can't parse the response, assume no actions
        return []

def log_prediction_accuracy(user_input, prediction, actual_actions):
    """
    Log prediction vs actual results for accuracy tracking.
    
    Args:
        user_input (str): The original user input
        prediction (dict): The prediction result
        actual_actions (list): List of actual action types in response
    """
    predicted_actions = prediction["requires_actions"]
    actual_has_actions = len(actual_actions) > 0
    
    # Determine if prediction was correct
    is_correct = predicted_actions == actual_has_actions
    match_status = "✓" if is_correct else "✗"
    
    # Print debug information
    print(f"\nDEBUG: ACTION PREDICTION - Input: '{user_input[:60]}{'...' if len(user_input) > 60 else ''}'")
    print(f"DEBUG: ACTION PREDICTION - Predicted: {predicted_actions} ({prediction['reason']})")
    print(f"DEBUG: ACTION PREDICTION - Actual: {actual_has_actions} (actions: {actual_actions}) [excludes updateTime]")
    print(f"DEBUG: ACTION PREDICTION - MATCH: {match_status} ({'CORRECT' if is_correct else 'INCORRECT'})")
    
    # Log potential token savings
    if not predicted_actions and not actual_has_actions:
        print("DEBUG: ACTION PREDICTION - TOKEN SAVINGS: Could route to mini model")
    elif predicted_actions and actual_has_actions:
        print("DEBUG: ACTION PREDICTION - TOKEN USAGE: Correctly using full model")
    elif not predicted_actions and actual_has_actions:
        print("DEBUG: ACTION PREDICTION - MISS: Would need model escalation")
    else:  # predicted_actions and not actual_has_actions
        print("DEBUG: ACTION PREDICTION - OVERCAUTION: Could have used mini model")

# Example usage and testing
if __name__ == "__main__":
    # Test cases for validation
    test_cases = [
        # Should predict TRUE (require actions)
        "I pick up the golden sword",
        "I cast fireball at the goblins", 
        "I travel to the tavern",
        "I rest for 8 hours",
        "I give Elen my healing potion",
        "I store my gold in the chest",
        
        # Should predict FALSE (pure roleplay)
        "What do you see in the distance?",
        "Tell me about the local customs",
        "I ask the innkeeper about rumors",
        "How is Thane feeling?",
        "Describe the tavern's atmosphere",
        "I say 'We should be careful here'"
    ]
    
    for test_input in test_cases:
        prediction = predict_actions_required(test_input)
        print(f"\nInput: '{test_input}'")
        print(f"Prediction: {prediction}")