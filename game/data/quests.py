"""game/data/quests.py — QUEST_DEFINITIONS (pure quest data)."""
from typing import Dict, List, Any, Optional, Tuple

QUEST_DEFINITIONS: List[Dict] = [
    # ──────────────────────────────────────────────────────────────
    # INTRO CHAIN  (teaches core mechanics one at a time)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "q_intro_meet_blacksmith",
        "title": "A Stranger in Raven Hollow",
        "desc": "You've arrived in a town gripped by darkness. Seek out Garrick the Blacksmith — he seems to know more about the dangers lurking beyond the walls.",
        "objectives": [{"type": "talk_to", "vendor_role": "Blacksmith", "count": 1, "label": "Speak with the Blacksmith (0/1)"}],
        "rewards": {"gold": 10, "sp": 0},
        "requires": [],
        "chain_next": "q_intro_enter_wild",
    },
    {
        "id": "q_intro_enter_wild",
        "title": "Beyond the Gates",
        "desc": "The Blacksmith warned you about the wilderness. Step through the portal west of town and see for yourself what threatens Raven Hollow.",
        "objectives": [{"type": "visit_level", "level": "wilderness", "count": 1, "label": "Enter the Wilderness (0/1)"}],
        "rewards": {"gold": 10, "sp": 0},
        "requires": ["q_intro_meet_blacksmith"],
        "chain_next": "q_intro_first_kill",
    },
    {
        "id": "q_intro_first_kill",
        "title": "First Blood",
        "desc": "The wolves are aggressive and relentless. Prove you can defend yourself — slay your first predator.",
        "objectives": [{"type": "kill", "count": 1, "label": "Slay a predator (0/1)"}],
        "rewards": {"gold": 15, "sp": 1},
        "requires": ["q_intro_enter_wild"],
        "chain_next": "q_intro_loot",
    },
    {
        "id": "q_intro_loot",
        "title": "Spoils of the Hunt",
        "desc": "Every creature you fell leaves behind valuable materials. Collect wolf pelts and fangs from their corpses — click the glowing loot piles.",
        "objectives": [
            {"type": "gather", "item": "wolf_pelt", "count": 2, "label": "Collect Wolf Pelts (0/2)"},
            {"type": "gather", "item": "wolf_fang", "count": 2, "label": "Collect Wolf Fangs (0/2)"},
        ],
        "rewards": {"gold": 15, "sp": 1},
        "requires": ["q_intro_first_kill"],
        "chain_next": "q_intro_craft",
    },
    {
        "id": "q_intro_craft",
        "title": "The Healer's Craft",
        "desc": "The wilderness will break you without supplies. Visit the Alchemist in town and craft a Healing Salve from the pelts you've gathered.",
        "objectives": [{"type": "craft", "recipe_id": "craft_healing_salve", "count": 1, "label": "Craft a Healing Salve (0/1)"}],
        "rewards": {"gold": 20, "sp": 1, "item": {"effect": "hp_60", "name": "Health Potion", "color": (200, 80, 80)}},
        "requires": ["q_intro_loot"],
        "chain_next": None,
    },
    # ──────────────────────────────────────────────────────────────
    # ORIGINAL QUEST CHAINS  (preserved, now require intro completion)
    # ──────────────────────────────────────────────────────────────
    {
        "id": "q_first_hunt",
        "title": "First Hunt",
        "desc": "Prove your mettle by slaying wolves in the wilderness.",
        "objectives": [{"type": "kill", "count": 3, "label": "Slay wolves (0/3)"}],
        "rewards": {"gold": 20, "sp": 1},
        "requires": ["q_intro_craft"],
        "chain_next": "q_blood_trail",
    },
    {
        "id": "q_gather_pelts",
        "title": "The Tanner's Need",
        "desc": "The tanner in town needs wolf pelts to supply the market this season.",
        "objectives": [{"type": "gather", "item": "wolf_pelt", "count": 4, "label": "Collect Wolf Pelts (0/4)"}],
        "rewards": {"gold": 35, "sp": 1},
        "requires": ["q_intro_craft"],
        "chain_next": "q_herbalist_brew",
    },
    {
        "id": "q_blood_trail",
        "title": "Blood Trail",
        "desc": "The wolf pack grows bolder every night. Thin their numbers decisively.",
        "objectives": [{"type": "kill", "count": 10, "label": "Slay wolves (0/10)"}],
        "rewards": {"gold": 60, "sp": 2},
        "requires": ["q_first_hunt"],
        "chain_next": "q_pack_leader",
    },
    {
        "id": "q_herbalist_brew",
        "title": "Alchemist's Request",
        "desc": "The herbalist needs rare components from the wilderness for a powerful remedy.",
        "objectives": [
            {"type": "gather", "item": "venom_sac", "count": 3, "label": "Collect Venom Sacs (0/3)"},
            {"type": "gather", "item": "wolf_bone", "count": 5, "label": "Collect Wolf Bones (0/5)"},
        ],
        "rewards": {"gold": 80, "sp": 2, "item": {"effect": "hp_60", "name": "Health Potion", "color": (200, 80, 80)}},
        "requires": ["q_gather_pelts"],
        "chain_next": "q_master_crafter",
    },
    {
        "id": "q_pack_leader",
        "title": "Pack Leader",
        "desc": "The wilderness will not be safe until twenty-five wolves have fallen.",
        "objectives": [{"type": "kill", "count": 25, "label": "Slay wolves (0/25)"}],
        "rewards": {"gold": 150, "sp": 3},
        "requires": ["q_blood_trail"],
        "chain_next": "q_apex",
    },
    {
        "id": "q_master_crafter",
        "title": "Master Crafter",
        "desc": "The blacksmith wants proof of your crafting skill. Bring him a Bone Charm.",
        "objectives": [{"type": "craft", "recipe_id": "craft_bone_charm", "count": 1, "label": "Craft a Bone Charm (0/1)"}],
        "rewards": {"gold": 100, "sp": 3},
        "requires": ["q_herbalist_brew"],
        "chain_next": None,
    },
    {
        "id": "q_apex",
        "title": "Apex Predator",
        "desc": "You are the apex. Let the wilderness know your name. Slay sixty wolves total.",
        "objectives": [{"type": "kill", "count": 60, "label": "Slay wolves (0/60)"}],
        "rewards": {"gold": 300, "sp": 5},
        "requires": ["q_pack_leader"],
        "chain_next": None,
    },
    # ──────────────────────────────────────────────────────────────
    # 15 NEW WILDERNESS QUESTS  (each one mechanically unique)
    # ──────────────────────────────────────────────────────────────

    # ── BRANCH A: Combat path (Guard → Leatherworker) ──────────
    # 1 — Kill bears (unlocks after intro)
    {
        "id": "q_bear_problem",
        "title": "The Bear Problem",
        "desc": "Grizzly bears have been mauling travelers on the northern trails. The Guard captain needs someone brave — or foolish — enough to thin them out.",
        "objectives": [{"type": "kill_type", "enemy_name": "Grizzly Bear", "count": 3, "label": "Slay Grizzly Bears (0/3)"}],
        "rewards": {"gold": 65, "sp": 2},
        "requires": ["q_intro_craft"],
        "chain_next": "q_predator_census",
    },
    # 2 — Kill all 4 predator types (chains from bear problem)
    {
        "id": "q_predator_census",
        "title": "Predator Census",
        "desc": "The town's records are incomplete. The Guard needs proof that each type of predator in the wilderness has been confronted: bear, cougar, boar, and snake.",
        "objectives": [
            {"type": "kill_type", "enemy_name": "Grizzly Bear", "count": 1, "label": "Slay a Grizzly Bear (0/1)"},
            {"type": "kill_type", "enemy_name": "Cougar", "count": 1, "label": "Slay a Cougar (0/1)"},
            {"type": "kill_type", "enemy_name": "Boar", "count": 1, "label": "Slay a Boar (0/1)"},
            {"type": "kill_type", "enemy_name": "Snake", "count": 1, "label": "Slay a Snake (0/1)"},
        ],
        "rewards": {"gold": 90, "sp": 3},
        "requires": ["q_bear_problem"],
        "chain_next": "q_shadow_stalkers",
    },
    # 3 — Kill cougars (chains from predator census)
    {
        "id": "q_shadow_stalkers",
        "title": "Shadow Stalkers",
        "desc": "Cougars have been ambushing traders at dusk. They're fast, silent, and deadly. The Leatherworker is offering a bounty for every one you bring down.",
        "objectives": [{"type": "kill_type", "enemy_name": "Cougar", "count": 4, "label": "Slay Cougars (0/4)"}],
        "rewards": {"gold": 55, "sp": 2},
        "requires": ["q_predator_census"],
        "chain_next": None,
    },

    # ── BRANCH B: Gear path (Blacksmith) ──────────────────────
    # 4 — Equip a weapon (unlocks after intro)
    {
        "id": "q_armed_and_ready",
        "title": "Armed and Ready",
        "desc": "The Blacksmith refuses to let you leave unprepared again. Craft or find a weapon and equip it before venturing out.",
        "objectives": [{"type": "equip_slot", "slot": "weapon", "count": 1, "label": "Equip a Weapon (0/1)"}],
        "rewards": {"gold": 30, "sp": 1},
        "requires": ["q_intro_craft"],
        "chain_next": "q_forged_in_fire",
    },
    # 5 — Craft a Pack Blade (chains from armed & ready)
    {
        "id": "q_forged_in_fire",
        "title": "Forged in Fire",
        "desc": "The Blacksmith challenges you to forge a Pack Blade from wolf fangs and claws. It's a rite of passage for every fighter in Raven Hollow.",
        "objectives": [{"type": "craft", "recipe_id": "craft_pack_blade", "count": 1, "label": "Craft a Pack Blade (0/1)"}],
        "rewards": {"gold": 50, "sp": 2},
        "requires": ["q_armed_and_ready"],
        "chain_next": "q_iron_skin",
    },
    # 6 — Craft + equip armor (chains from forged in fire)
    {
        "id": "q_iron_skin",
        "title": "Iron Skin",
        "desc": "Garrick insists you'll die out there without proper armor. Craft the Pelt Cuirass and wear it — let the leather take the hits, not your ribs.",
        "objectives": [
            {"type": "craft", "recipe_id": "craft_pelt_cuirass", "count": 1, "label": "Craft a Pelt Cuirass (0/1)"},
            {"type": "equip_slot", "slot": "chest", "count": 1, "label": "Equip Chest Armor (0/1)"},
        ],
        "rewards": {"gold": 60, "sp": 2},
        "requires": ["q_forged_in_fire"],
        "chain_next": None,
    },

    # ── BRANCH C: Survival path (Guard → Tailor) ─────────────
    # 7 — Survive 5 min (unlocks after intro)
    {
        "id": "q_survivalist",
        "title": "Trial of Endurance",
        "desc": "The old Hunter by the gate says most newcomers flee the wilderness within a minute. Stay out there for five full minutes to earn his respect.",
        "objectives": [{"type": "survive_time", "count": 300, "label": "Survive 5 min in Wilderness (0/300)"}],
        "rewards": {"gold": 40, "sp": 1},
        "requires": ["q_intro_craft"],
        "chain_next": "q_provisions",
    },
    # 8 — Hunt passive animals (chains from survivalist)
    {
        "id": "q_provisions",
        "title": "Provisions for the Long Dark",
        "desc": "Winter is closing in. The Baker needs venison and poultry for the town stores, and the Tailor needs feathers and hides. Hunt the passive wildlife before the herds migrate.",
        "objectives": [
            {"type": "gather", "item": "venison", "count": 3, "label": "Collect Venison (0/3)"},
            {"type": "gather", "item": "bird_feather", "count": 4, "label": "Collect Bird Feathers (0/4)"},
            {"type": "gather", "item": "deer_hide", "count": 3, "label": "Collect Deer Hides (0/3)"},
        ],
        "rewards": {"gold": 60, "sp": 2},
        "requires": ["q_survivalist"],
        "chain_next": None,
    },

    # ── BRANCH D: Economy path (Herbalist → Merchant) ────────
    # 9 — Spend gold at vendors (unlocks after intro)
    {
        "id": "q_invest_in_yourself",
        "title": "Invest in Yourself",
        "desc": "The Herbalist insists that a good adventurer always keeps potions on hand. Spend at least 60 gold buying supplies from town vendors.",
        "objectives": [{"type": "spend_gold", "count": 60, "label": "Spend Gold at Vendors (0/60)"}],
        "rewards": {"gold": 40, "sp": 1},
        "requires": ["q_intro_craft"],
        "chain_next": "q_fortune_seeker",
    },
    # 10 — Accumulate 200 gold (chains from invest in yourself)
    {
        "id": "q_fortune_seeker",
        "title": "Fortune Seeker",
        "desc": "The Merchant has a proposition: prove you understand the value of coin by saving 200 gold. He may have a business opportunity for someone with means.",
        "objectives": [{"type": "gold_accumulate", "count": 200, "label": "Accumulate 200 Gold (0/200)"}],
        "rewards": {"gold": 0, "sp": 2, "item": {"effect": "hp_80", "name": "Greater Health Flask", "color": (180, 60, 60)}},
        "requires": ["q_invest_in_yourself"],
        "chain_next": None,
    },

    # ── BRANCH E: Alchemy path (Alchemist) ───────────────────
    # 11 — Reach alchemy skill 15 (unlocks after intro)
    {
        "id": "q_alchemist_apprentice",
        "title": "The Alchemist's Apprentice",
        "desc": "The Alchemist is overworked and understaffed. She will teach you her secrets if you prove dedication — raise your Alchemy skill to 15 through practice.",
        "objectives": [{"type": "profession_skill", "profession": "alchemy", "count": 15, "label": "Reach Alchemy Skill 15 (0/15)"}],
        "rewards": {"gold": 55, "sp": 2},
        "requires": ["q_intro_craft"],
        "chain_next": "q_venom_harvester",
    },
    # 12 — Gather venom sacs (chains from alchemy apprentice)
    {
        "id": "q_venom_harvester",
        "title": "Venom Harvester",
        "desc": "The Alchemist's antivenom supply is dangerously low. Venom sacs are rare and the extraction is grim work, but lives depend on it.",
        "objectives": [{"type": "gather", "item": "venom_sac", "count": 6, "label": "Collect Venom Sacs (0/6)"}],
        "rewards": {"gold": 70, "sp": 2, "item": {"effect": "mp_80", "name": "Mana Potion", "color": (80, 120, 220)}},
        "requires": ["q_alchemist_apprentice"],
        "chain_next": None,
    },

    # ── BRANCH F: Leveling path (Blacksmith → Elder) ─────────
    # 13 — Reach level 5 (unlocks after intro)
    {
        "id": "q_seasoned_fighter",
        "title": "Seasoned Fighter",
        "desc": "Raw talent is nothing without experience. The Blacksmith says no one in Raven Hollow will take you seriously until you've proven your growth in battle.",
        "objectives": [{"type": "reach_level", "count": 5, "label": "Reach Level 5 (0/5)"}],
        "rewards": {"gold": 50, "sp": 2},
        "requires": ["q_intro_craft"],
        "chain_next": "q_veteran",
    },
    # 14 — Reach level 10 (chains from seasoned fighter)
    {
        "id": "q_veteran",
        "title": "Veteran of the Hollow",
        "desc": "There are whispers of darker threats beyond what you've faced. The elders say only a warrior of level 10 or higher could hope to survive what comes next.",
        "objectives": [{"type": "reach_level", "count": 10, "label": "Reach Level 10 (0/10)"}],
        "rewards": {"gold": 120, "sp": 3},
        "requires": ["q_seasoned_fighter"],
        "chain_next": None,
    },

    # ── BRANCH G: Supply path (Leatherworker) ────────────────
    # 15 — Bulk material gathering (unlocks after first hunt from original chain)
    {
        "id": "q_supply_run",
        "title": "The War Effort",
        "desc": "Raven Hollow is fortifying its defenses. The Tanner needs pelts for shields, the Blacksmith needs bones for rivets, and the Alchemist needs claws for tinctures.",
        "objectives": [
            {"type": "gather", "item": "wolf_pelt", "count": 6, "label": "Collect Wolf Pelts (0/6)"},
            {"type": "gather", "item": "wolf_bone", "count": 6, "label": "Collect Wolf Bones (0/6)"},
            {"type": "gather", "item": "wolf_claw", "count": 4, "label": "Collect Wolf Claws (0/4)"},
        ],
        "rewards": {"gold": 80, "sp": 2},
        "requires": ["q_first_hunt"],
        "chain_next": None,
    },
]
