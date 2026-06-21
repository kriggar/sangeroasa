"""game/data/icons.py — spell-icon sheet/file maps and class palettes (pure data)."""
from typing import Dict, Tuple

SPELL_ICON_SHEETS: Dict[str, str] = {
    "items": "assets/items.png",
    "monsters": "assets/monsters.png",
    "ife": "assets/items food everything.png",
}

SPELL_ICON_FRAME_COLORS: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "default": {"bg": (26, 26, 30), "border": (84, 84, 96)},
    "mage": {"bg": (26, 30, 44), "border": (102, 126, 188)},
    "rogue": {"bg": (28, 30, 34), "border": (96, 106, 120)},
    "ranger": {"bg": (26, 34, 24), "border": (124, 154, 90)},
    "necromancer": {"bg": (34, 24, 42), "border": (136, 96, 158)},
    "warrior": {"bg": (40, 28, 22), "border": (168, 122, 84)},
    "paladin": {"bg": (44, 38, 24), "border": (194, 166, 90)},
}

# WoW-style per-class color palettes applied to action bars, spellbook, skill tree, etc.
CLASS_PALETTES: Dict[str, Dict[str, Tuple[int, ...]]] = {
    "mage": {
        "primary":    (105, 204, 240),   # icy cyan — WoW mage blue
        "secondary":  ( 64, 148, 210),   # deeper blue
        "accent":     (180, 230, 255),   # bright highlight
        "glow":       ( 64, 180, 240, 180),  # action bar slot glow (RGBA)
        "panel_bg":   ( 12,  20,  38),   # dark navy panel background
        "panel_border":(105, 204, 240),  # panel border
        "tab_active": ( 64, 148, 210),
        "tab_text":   (180, 230, 255),
    },
    "ranger": {
        "primary":    (155, 210,  85),   # hunter green — WoW hunter
        "secondary":  ( 96, 155,  50),   # dark olive
        "accent":     (210, 240, 140),   # bright lime highlight
        "glow":       (120, 190,  60, 170),
        "panel_bg":   ( 14,  22,  10),
        "panel_border":(155, 210,  85),
        "tab_active": ( 96, 155,  50),
        "tab_text":   (210, 240, 140),
    },
    "rogue": {
        "primary":    (255, 244,  92),   # rogue yellow — WoW rogue
        "secondary":  (200, 175,  50),   # dark gold
        "accent":     (255, 255, 160),   # bright yellow
        "glow":       (220, 195,  60, 160),
        "panel_bg":   ( 22,  20,  10),
        "panel_border":(220, 195,  60),
        "tab_active": (180, 150,  40),
        "tab_text":   (255, 255, 160),
    },
    "necromancer": {
        "primary":    (148,  86, 210),   # unholy purple — WoW warlock-ish
        "secondary":  ( 96,  50, 150),   # dark violet
        "accent":     (200, 160, 255),   # lavender highlight
        "glow":       (130,  70, 200, 170),
        "panel_bg":   ( 18,  10,  28),
        "panel_border":(148,  86, 210),
        "tab_active": ( 96,  50, 150),
        "tab_text":   (200, 160, 255),
    },
    "warrior": {
        "primary":    (198, 155, 109),   # plate tan — WoW warrior
        "secondary":  (150, 100,  60),   # dark bronze
        "accent":     (240, 210, 160),   # bright tan
        "glow":       (180, 130,  80, 160),
        "panel_bg":   ( 24,  16,  10),
        "panel_border":(198, 155, 109),
        "tab_active": (150, 100,  60),
        "tab_text":   (240, 210, 160),
    },
    "paladin": {
        "primary":    (244, 140, 186),   # holy pink — WoW paladin
        "secondary":  (200,  90, 140),   # deep rose
        "accent":     (255, 210, 230),   # bright pink-white
        "glow":       (220, 110, 160, 170),
        "panel_bg":   ( 28,  14,  20),
        "panel_border":(220, 110, 160),
        "tab_active": (200,  90, 140),
        "tab_text":   (255, 210, 230),
    },
    "default": {
        "primary":    (180, 180, 190),
        "secondary":  (110, 110, 130),
        "accent":     (220, 220, 235),
        "glow":       (140, 140, 160, 140),
        "panel_bg":   ( 18,  18,  22),
        "panel_border":(100, 100, 120),
        "tab_active": (100, 100, 120),
        "tab_text":   (220, 220, 235),
    },
}

SPELL_ICON_FILES: Dict[str, str] = {
    # ── MAGE FOOZLE (active bar) ──────────────────────────────────────────────
    "mage_foozle_fireball":       "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile002.png",
    "mage_foozle_water_geyser":   "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile008.png",
    "mage_foozle_portal_blink":   "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile004.png",
    "mage_foozle_explosion":      "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile001.png",
    "mage_foozle_molten_spear":   "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile003.png",
    "mage_foozle_rocks":          "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile005.png",
    "mage_foozle_earth_spike":    "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile000.png",
    "mage_foozle_water":          "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile007.png",
    "mage_foozle_tornado":        "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile006.png",
    "mage_foozle_wind":           "assets/Foozle_2DE0001_Pixel_Magic_Effects/Icons/tile009.png",
    # ── MAGE ───────────────────────────────────────────────────────────────────
    "mage_searing_bolt":          "assets/spell icons/3.png",    # fire bolt
    "mage_fireball":              "assets/spell icons/4.png",    # fire comet
    "mage_dragons_breath":        "assets/spell icons/42.png",   # fire wings burst
    "mage_living_bomb":           "assets/spell icons/5.png",    # fire explosion small
    "mage_flame_strike":          "assets/spell icons/218.png",  # fire pillar
    "mage_frostbolt":             "assets/spell icons/125.png",  # frost bolt
    "mage_frost_nova":            "assets/spell icons/33.png",   # frost ring nova
    "mage_blizzard":              "assets/spell icons/137.png",  # blizzard storm
    "mage_frozen_orb":            "assets/spell icons/203.png",  # frozen orb
    "mage_ice_lance":             "assets/spell icons/127.png",  # ice lance
    "mage_arcane_missile":        "assets/spell icons/14.png",   # arcane missile
    "mage_arcane_explosion":      "assets/spell icons/110.png",  # arcane explosion
    "mage_gale_whip":             "assets/spell icons/20.png",   # wind/gale
    "mage_stone_pillar":          "assets/spell icons/144.png",  # stone rune pillar
    "mage_time_warp":             "assets/spell icons/142.png",  # time warp rune
    "mage_meteor":                "assets/spell icons/12.png",   # meteor
    "mage_arcane_surge":          "assets/spell icons/79.png",   # arcane surge
    "mage_elemental_cataclysm":   "assets/spell icons/153.png",  # elemental cataclysm
    # ── RANGER ─────────────────────────────────────────────────────────────────
    "ranger_quick_shot":          "assets/spell icons/29.png",   # quick arrow
    "ranger_power_shot":          "assets/spell icons/4.png",    # power shot (fire)
    "ranger_aimed_shot":          "assets/spell icons/Icon6.png",# aimed crosshair
    "ranger_concussive_shot":     "assets/spell icons/215.png",  # concussive shot
    "ranger_serpent_sting":       "assets/spell icons/114.png",  # serpent/poison
    "ranger_black_arrow":         "assets/spell icons/7.png",    # dark arrow
    "ranger_explosive_shot":      "assets/spell icons/139.png",  # explosive shot
    "ranger_volley":              "assets/spell icons/31.png",   # arrow volley
    "ranger_bear_trap":           "assets/spell icons/231.png",  # bear paw/trap
    "ranger_freezing_trap":       "assets/spell icons/216.png",  # freezing trap
    "ranger_explosive_trap":      "assets/spell icons/11.png",   # explosive trap
    "ranger_predators_rain":      "assets/spell icons/196.png",  # predator's rain
    "ranger_multi_shot":          "assets/spell icons/30.png",   # multi-shot arrows
    "ranger_hunters_mark":        "assets/spell icons/246.png",  # hunter's mark eye
    "ranger_barrage":             "assets/spell icons/202.png",  # barrage
    "ranger_kill_shot":           "assets/spell icons/234.png",  # kill shot
    "ranger_chimera_shot":        "assets/spell icons/45.png",   # chimera shot
    "ranger_aspect_of_hawk":      "assets/spell icons/23.png",   # hawk aspect
    # ── ROGUE ──────────────────────────────────────────────────────────────────
    "rogue_sinister_strike":      "assets/spell icons/Icon4.png",# sinister strike dagger
    "rogue_shadow_knife":         "assets/spell icons/166.png",  # shadow knife
    "rogue_backstab":             "assets/spell icons/Icon9.png",# backstab
    "rogue_hemorrhage":           "assets/spell icons/115.png",  # hemorrhage bleed
    "rogue_ambush":               "assets/spell icons/163.png",  # ambush
    "rogue_garrote":              "assets/spell icons/16.png",   # garrote
    "rogue_smoke_burst":          "assets/spell icons/Icon7.png",# smoke burst
    "rogue_cheap_shot":           "assets/spell icons/162.png",  # cheap shot stun
    "rogue_blood_lance":          "assets/spell icons/8.png",    # blood lance
    "rogue_envenom":              "assets/spell icons/71.png",   # envenom poison
    "rogue_fan_of_knives":        "assets/spell icons/51.png",   # fan of knives
    "rogue_venom_trap":           "assets/spell icons/66.png",   # venom trap
    "rogue_shadow_dance":         "assets/spell icons/70.png",   # shadow dance
    "rogue_rupture":              "assets/spell icons/62.png",   # rupture
    "rogue_viper_nest":           "assets/spell icons/Icon23.png",# viper nest
    "rogue_kidney_shot":          "assets/spell icons/161.png",  # kidney shot
    "rogue_marked_for_death":     "assets/spell icons/106.png",  # marked for death
    "rogue_evasion_sigil":        "assets/spell icons/61.png",   # evasion sigil
    # ── NECROMANCER ────────────────────────────────────────────────────────────
    "necro_bone_spear":           "assets/spell icons/64.png",   # bone spear
    "necro_shadow_bolt":          "assets/spell icons/10.png",   # shadow bolt
    "necro_death_coil":           "assets/spell icons/174.png",  # death coil
    "necro_death_grip":           "assets/spell icons/189.png",  # death grip
    "necro_plague_cone":          "assets/spell icons/192.png",  # plague cone
    "necro_soul_harvest":         "assets/spell icons/Icon14.png",# soul harvest
    "necro_grave_chill":          "assets/spell icons/32.png",   # grave chill frost
    "necro_bone_nova":            "assets/spell icons/190.png",  # bone nova
    "necro_corpse_explosion":     "assets/spell icons/138.png",  # corpse explosion
    "necro_epidemic":             "assets/spell icons/69.png",   # epidemic disease
    "necro_wraith_orb":           "assets/spell icons/172.png",  # wraith orb
    "necro_soul_well":            "assets/spell icons/67.png",   # soul well
    "necro_anti_magic":           "assets/spell icons/200.png",  # anti-magic shell
    "necro_ossuary_gate":         "assets/spell icons/176.png",  # ossuary gate
    "necro_pestilence":           "assets/spell icons/65.png",   # pestilence
    "necro_dark_pact":            "assets/spell icons/157.png",  # dark pact
    "necro_death_and_decay":      "assets/spell icons/Icon11.png",# death and decay
    "necro_unholy_ground":        "assets/spell icons/9.png",    # unholy ground
    # ── WARRIOR ────────────────────────────────────────────────────────────────
    "warrior_heroic_strike":      "assets/spell icons/Icon4.png",# heroic strike
    "warrior_iron_javelin":       "assets/spell icons/3.png",    # iron javelin
    "warrior_slam":               "assets/spell icons/162.png",  # slam
    "warrior_overpower":          "assets/spell icons/167.png",  # overpower
    "warrior_mortal_strike":      "assets/spell icons/169.png",  # mortal strike
    "warrior_execute":            "assets/spell icons/168.png",  # execute
    "warrior_shield_slam":        "assets/spell icons/59.png",   # shield slam
    "warrior_charge":             "assets/spell icons/249.png",  # charge
    "warrior_cleave":             "assets/spell icons/50.png",   # cleave
    "warrior_shockwave":          "assets/spell icons/196.png",  # shockwave
    "warrior_war_stomp":          "assets/spell icons/43.png",   # war stomp
    "warrior_thunder_clap":       "assets/spell icons/13.png",   # thunder clap
    "warrior_demo_shout":         "assets/spell icons/183.png",  # demoralizing shout
    "warrior_whirling_axe":       "assets/spell icons/170.png",  # whirling axe
    "warrior_bladestorm":         "assets/spell icons/111.png",  # bladestorm
    "warrior_valor_banner":       "assets/spell icons/233.png",  # valor banner
    "warrior_recklessness":       "assets/spell icons/238.png",  # recklessness bull
    "warrior_avatar":             "assets/spell icons/48.png",   # avatar
    # ── PALADIN ────────────────────────────────────────────────────────────────
    "paladin_crusader_strike":    "assets/spell icons/162.png",  # crusader strike
    "paladin_shield_of_righteous":"assets/spell icons/59.png",   # shield of righteous
    "paladin_templars_verdict":   "assets/spell icons/Icon4.png",# templar's verdict
    "paladin_divine_storm":       "assets/spell icons/56.png",   # divine storm
    "paladin_judgment_spear":     "assets/spell icons/13.png",   # judgment
    "paladin_holy_shock":         "assets/spell icons/236.png",  # holy shock
    "paladin_exorcism":           "assets/spell icons/199.png",  # exorcism
    "paladin_hammer_of_justice":  "assets/spell icons/241.png",  # hammer of justice
    "paladin_holy_burst":         "assets/spell icons/85.png",   # holy burst
    "paladin_holy_wrath":         "assets/spell icons/108.png",  # holy wrath
    "paladin_word_of_glory":      "assets/spell icons/73.png",   # word of glory
    "paladin_light_of_dawn":      "assets/spell icons/235.png",  # light of dawn
    "paladin_blinding_light":     "assets/spell icons/30.png",   # blinding light
    "paladin_radiant_orb":        "assets/spell icons/80.png",   # radiant orb
    "paladin_consecration":       "assets/spell icons/143.png",  # consecration
    "paladin_execution_sentence": "assets/spell icons/214.png",  # execution sentence
    "paladin_avenging_wrath":     "assets/spell icons/18.png",   # avenging wrath
    "paladin_divine_hammer":      "assets/spell icons/234.png",  # divine hammer
}

# Empty — all icons now loaded from SPELL_ICON_FILES above
