"""game/dialogue.py — NPC dialogue + quest-giver logic and DialogueSession."""
from typing import Dict, List, Optional, Tuple, Any, Set

from game.constants import BACKPACK_SLOT_COUNT
from game.data.quests import QUEST_DEFINITIONS


QUEST_GIVER_ROLE_BY_ID: Dict[str, str] = {
    # Intro chain
    "q_intro_meet_blacksmith": "Blacksmith",
    "q_intro_enter_wild": "Blacksmith",
    "q_intro_first_kill": "Blacksmith",
    "q_intro_loot": "Blacksmith",
    "q_intro_craft": "Alchemist",
    # Original chains
    "q_first_hunt": "Blacksmith",
    "q_gather_pelts": "Blacksmith",
    "q_blood_trail": "Blacksmith",
    "q_herbalist_brew": "Herbalist",
    "q_pack_leader": "Blacksmith",
    "q_master_crafter": "Blacksmith",
    "q_apex": "Blacksmith",
    # New wilderness quests
    "q_bear_problem": "Guard",
    "q_seasoned_fighter": "Blacksmith",
    "q_fortune_seeker": "Merchant",
    "q_survivalist": "Blacksmith",
    "q_alchemist_apprentice": "Alchemist",
    "q_armed_and_ready": "Blacksmith",
    "q_venom_harvester": "Alchemist",
    "q_predator_census": "Guard",
    "q_forged_in_fire": "Blacksmith",
    "q_iron_skin": "Blacksmith",
    "q_supply_run": "Leatherworker",
    "q_veteran": "Blacksmith",
    "q_shadow_stalkers": "Leatherworker",
    "q_invest_in_yourself": "Herbalist",
    "q_provisions": "Tailor",
}
DEFAULT_QUEST_GIVER_ROLE = "Blacksmith"


def quest_giver_role_for_id(quest_id: str) -> str:
    key = str(quest_id).strip()
    return str(QUEST_GIVER_ROLE_BY_ID.get(key, DEFAULT_QUEST_GIVER_ROLE))


def quest_marker_for_vendor_role(vendor_role: str, quest_states: Dict[str, str], quest_defs: List[Dict]) -> str:
    role = str(vendor_role).strip().lower()
    if not role:
        return ""
    has_available = False
    has_turn_in = False
    for qdef in quest_defs:
        qid = str(qdef.get("id", "")).strip()
        if not qid:
            continue
        giver_role = quest_giver_role_for_id(qid).strip().lower()
        if giver_role != role:
            continue
        state = str(quest_states.get(qid, "hidden")).strip().lower()
        if state == "complete":
            has_turn_in = True
        elif state == "available":
            has_available = True
    if has_turn_in:
        return "?"
    if has_available:
        return "!"
    return ""


def _quest_role_for_def(qdef: Dict) -> str:
    qid = str(qdef.get("id", "")).strip()
    if not qid:
        return ""
    return quest_giver_role_for_id(qid).strip().lower()


def vendor_has_quest_menu(vendor_role: str, quest_states: Dict[str, str], quest_defs: List[Dict]) -> bool:
    role = str(vendor_role).strip().lower()
    if not role:
        return False
    for qdef in quest_defs:
        if _quest_role_for_def(qdef) != role:
            continue
        qid = str(qdef.get("id", "")).strip()
        if quest_states.get(qid, "hidden") in ("available", "active", "complete"):
            return True
    return False


def normalize_vendor_available_quests(quest_states: Dict[str, str], quest_defs: List[Dict]) -> None:
    """Ensure only one available quest per vendor and none while another is active/complete."""
    blocked_roles: Set[str] = set()
    for qdef in quest_defs:
        qid = str(qdef.get("id", "")).strip()
        if not qid:
            continue
        state = str(quest_states.get(qid, "")).strip().lower()
        if state in ("active", "complete"):
            role = _quest_role_for_def(qdef)
            if role:
                blocked_roles.add(role)

    seen_available: Set[str] = set()
    for qdef in quest_defs:
        qid = str(qdef.get("id", "")).strip()
        if not qid:
            continue
        if str(quest_states.get(qid, "")).strip().lower() != "available":
            continue
        role = _quest_role_for_def(qdef)
        if not role:
            continue
        if role in blocked_roles or role in seen_available:
            quest_states.pop(qid, None)
            continue
        seen_available.add(role)

# ==================== DIALOGUE SYSTEM ====================

DIALOGUE_DEFINITIONS: List[Dict] = [
    {
        "id": "blacksmith_intro",
        "npc_role": "Blacksmith",
        "nodes": {
            "start": {
                "text": "Ah, a traveler! You look like you've seen your fair share of battles. The name's Garrick. I've been hammering steel in Sangeroasa for thirty winters now.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "What can you tell me about this town?", "next": "town_info"},
                    {"text": "I need my equipment repaired.", "next": "repair"},
                    {"text": "Do you have any work for me?", "next": "work", "condition": {"type": "quest_not_started", "quest_id": "q_gather_pelts"}},
                    {"text": "Goodbye.", "next": None}
                ]
            },
            "town_info": {
                "text": "Sangeroasa's been here longer than anyone can remember. The cathedral at the center? Built on foundations older than the kingdom itself. We get all sorts passing through — merchants, pilgrims, and lately... hunters seeking glory in the wilderness.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "What's in the wilderness?", "next": "wilderness_info"},
                    {"text": "Tell me more about yourself.", "next": "personal"},
                    {"text": "I should go.", "next": None}
                ]
            },
            "wilderness_info": {
                "text": "Wolf packs, mostly. Nasty creatures that have grown bold enough to attack caravans on the roads. Some say a greater beast prowls the deep woods, but that's just campfire tales. If you're thinking of heading out there, bring a good blade — and a better shield.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "Thanks for the advice.", "next": "start"},
                    {"text": "Goodbye.", "next": None}
                ]
            },
            "personal": {
                "text": "Thirty years I've stood at this forge. Made swords for kings and nails for farmers — both equally important in their own way. My father was a smith, and his father before him. It's in the blood, I suppose.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "That's impressive dedication.", "next": "dedication_response"},
                    {"text": "Let's talk about something else.", "next": "start"}
                ]
            },
            "dedication_response": {
                "text": "Dedication? Aye, I suppose. But it's more than that. Every blade I forge could save a life — or end one. That weight... it keeps you honest. Keeps you focused.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "I understand.", "next": "start"},
                    {"text": "Goodbye.", "next": None}
                ]
            },
            "repair": {
                "text": "Let me take a look... *inspects your gear* The steel's holding up well enough, but I can see some nicks that'll become cracks if left alone. Bring me materials from the wilderness — wolf bones make excellent reinforcement — and I can forge you something proper.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "What materials do you need?", "next": "materials"},
                    {"text": "I'll be back.", "next": None}
                ]
            },
            "materials": {
                "text": "Wolf pelts for leather backing, bones for pins and reinforcement, claws for decorative work if you're feeling fancy. The hunters bring me these regularly, but demand outstrips supply. Help me out, and I'll teach you a thing or two about working metal yourself.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "I'll see what I can find.", "next": None, "action": {"type": "set_flag", "flag": "blacksmith_materials_discussed"}}
                ]
            },
            "work": {
                "text": "Actually, there is something. The tanner — Marta, over by the west market — she's been complaining about wolf pelts drying up. Caravans are too afraid to gather them. If you could bring her some quality pelts, it'd help the whole town's economy.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "I'll do it.", "next": "quest_accept", "action": {"type": "start_quest", "quest_id": "q_gather_pelts"}},
                    {"text": "I need more details.", "next": "work_details"},
                    {"text": "Not interested right now.", "next": None}
                ]
            },
            "work_details": {
                "text": "Marta's stall is in the western market district. She needs four good pelts to fill her current orders. The wolves in the wilderness aren't particularly dangerous if you keep your wits about you, but don't get cocky. Even a lone wolf can bring down an unwary traveler.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "I understand. I'll help.", "next": "quest_accept", "action": {"type": "start_quest", "quest_id": "q_gather_pelts"}},
                    {"text": "I need more time to think.", "next": None}
                ]
            },
            "quest_accept": {
                "text": "Good luck out there. And remember — the wolves may be beasts, but they're not mindless. Respect the danger, and you'll come back in one piece.",
                "speaker": "Garrick",
                "choices": [
                    {"text": "Thanks, Garrick.", "next": None}
                ]
            }
        },
        "default_node": "start"
    },
    {
        "id": "vendor_generic",
        "npc_role": "Vendor",
        "nodes": {
            "start": {
                "text": "Welcome, traveler! What can I help you with today?",
                "speaker": None,
                "choices": [
                    {"text": "Tell me about yourself.", "next": "about"},
                    {"text": "What do you sell?", "next": "wares"},
                    {"text": "Goodbye.", "next": None}
                ]
            },
            "about": {
                "text": "I'm just a simple merchant trying to make an honest living. The roads can be dangerous, but meeting interesting people like you makes it worthwhile.",
                "speaker": None,
                "choices": [
                    {"text": "What's the most interesting thing you've seen?", "next": "stories"},
                    {"text": "I see. Goodbye.", "next": None}
                ]
            },
            "stories": {
                "text": "Once, I saw a wolf pack take down a deer right on the road ahead of my cart. Terrifying at first, but also... natural. The wilderness has its own laws, and we're just visitors there.",
                "speaker": None,
                "choices": [
                    {"text": "Thank you for sharing.", "next": None}
                ]
            },
            "wares": {
                "text": "A bit of everything, really. Supplies for travelers, basic tools, some preserved foods. Nothing fancy, but reliable. Quality matters more than flash when you're out on the road.",
                "speaker": None,
                "choices": [
                    {"text": "I'll take a look.", "next": None},
                    {"text": "Maybe later. Goodbye.", "next": None}
                ]
            }
        },
        "default_node": "start"
    }
]

def get_dialogue_for_npc(npc_role: str) -> Optional[dict]:
    for dialogue in DIALOGUE_DEFINITIONS:
        if dialogue.get("npc_role", "").lower() == npc_role.lower():
            return dialogue
    for dialogue in DIALOGUE_DEFINITIONS:
        if dialogue.get("npc_role", "").lower() == "vendor":
            return dialogue
    return None

def check_dialogue_condition(condition: dict, character_state: dict) -> bool:
    if not condition:
        return True
    cond_type = condition.get("type", "")
    if cond_type == "quest_not_started":
        quest_id = condition.get("quest_id", "")
        return character_state.get("quest_states", {}).get(quest_id) is None
    elif cond_type == "quest_active":
        quest_id = condition.get("quest_id", "")
        return character_state.get("quest_states", {}).get(quest_id) == "active"
    elif cond_type == "flag_set":
        flag = condition.get("flag", "")
        return flag in character_state.get("dialogue_flags", set())
    return True

def execute_dialogue_action(action: dict, character_state: dict, game_state: dict) -> Optional[str]:
    if not action:
        return None
    action_type = action.get("type", "")
    
    if action_type == "start_quest":
        quest_id = action.get("quest_id", "")
        if quest_id and character_state.get("quest_states", {}).get(quest_id) is None:
            qs = character_state.setdefault("quest_states", {})
            sel_role = quest_giver_role_for_id(quest_id).strip().lower()
            for qdef in QUEST_DEFINITIONS:
                qid = str(qdef.get("id", "")).strip()
                if not qid or qid == quest_id:
                    continue
                if _quest_role_for_def(qdef) != sel_role:
                    continue
                if qs.get(qid) in ("active", "complete"):
                    return "Finish your current quest for this vendor first."
            qs[quest_id] = "active"
            quest_def = next((q for q in QUEST_DEFINITIONS if q["id"] == quest_id), None)
            if quest_def:
                character_state.setdefault("quest_progress", {})[quest_id] = [0] * len(quest_def.get("objectives", []))
            normalize_vendor_available_quests(qs, QUEST_DEFINITIONS)
            return f"Quest started: {quest_def['title'] if quest_def else quest_id}"
            
    elif action_type == "give_item":
        item = action.get("item", {})
        if item:
            inv = character_state.setdefault("backpack_inventory", [])
            if len(inv) < BACKPACK_SLOT_COUNT:
                inv.append(dict(item))
                return f"Received: {item.get('name', 'Item')}"
            return "Inventory full!"
            
    elif action_type == "give_gold":
        amount = action.get("amount", 0)
        character_state["gold"] = character_state.get("gold", 0) + amount
        return f"Received {amount} gold"
        
    elif action_type == "give_xp":
        amount = action.get("amount", 0)
        character_state["player_xp"] = character_state.get("player_xp", 0) + amount
        return f"Gained {amount} experience"
        
    elif action_type == "set_flag":
        flag = action.get("flag", "")
        character_state.setdefault("dialogue_flags", set()).add(flag)
        
    return None

class DialogueSession:
    def __init__(self, dialogue_def: dict, character_state: dict, game_state: dict):
        self.dialogue_def = dialogue_def
        self.character_state = character_state
        self.game_state = game_state
        self.current_node_id = dialogue_def.get("default_node", "start")
        self.history: list[str] = []
        
    def get_current_node(self) -> Optional[dict]:
        nodes = self.dialogue_def.get("nodes", {})
        return nodes.get(self.current_node_id)
    
    def get_available_choices(self) -> list[dict]:
        node = self.get_current_node()
        if not node:
            return []
        available = []
        for choice in node.get("choices", []):
            condition = choice.get("condition")
            if check_dialogue_condition(condition, self.character_state):
                available.append(choice)
        return available
    
    def select_choice(self, choice_index: int) -> Tuple[bool, Optional[str]]:
        choices = self.get_available_choices()
        if choice_index < 0 or choice_index >= len(choices):
            return False, "Invalid choice"
        choice = choices[choice_index]
        action = choice.get("action")
        status = execute_dialogue_action(action, self.character_state, self.game_state)
        next_node = choice.get("next")
        if next_node:
            self.history.append(self.current_node_id)
            self.current_node_id = next_node
            return True, status
        else:
            return True, status
