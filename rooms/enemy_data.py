from entities.enemy import Enemy
from entities.enemy_moves import (
    move, damage_attack, poison_attack,
    enrage_self, apply_enemy_vulnerable, apply_enemy_weak,
    stun_attack, self_heal, volatile_self, disorient_attack,
    shield_allies, shield_self, slow_player, curse_player, soul_tax_player,
    haste_self, fortify_self,
    ranged_attack_ignore_block, double_hit,
)


def _guard_phase(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    from utils.status_effects import apply_block
    apply_block(enemy, 8)
    print_slow(f"  {enemy.name} enters phase 2 — raises a reinforced stance (+8 Block)!")


def _guard_counter(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    if not attacker or ctx.get("damage", 0) <= 0:
        return
    attacker.take_damage(2)
    print_slow(f"  {enemy.name} retaliates for 2 counter damage! (HP:{attacker.health})")


def _warden_phase(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    from utils.status_effects import apply_rage
    apply_rage(enemy, 2)
    print_slow("  Crypt Warden phase trigger — ancient sigils flare, Rage x2!")


def _tutorial_guard_intro(enemy, player, combat_session):
    from utils.helpers import print_slow
    print_slow('  Castle Guard: "First lesson. Guard, then strike."')


def _tutorial_guard_opening(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    print_slow('  Castle Guard: "Keep your stance. Strike when I overextend."')


def _tutorial_guard_phase(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    from utils.status_effects import apply_block
    apply_block(enemy, 6)
    print_slow('  Castle Guard: "Good. Now test my guard — watch for openings."')


def _tutorial_guard_counter(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    if not attacker or ctx.get("damage", 0) <= 0:
        return
    print_slow('  Castle Guard: "Again! Keep pressure on."')


def _tutorial_guard_desperation(enemy, attacker, combat_session, ctx):
    from utils.helpers import print_slow
    print_slow('  Castle Guard: "Final lesson — end this cleanly."')


def make_tutorial_guard():
    guard = Enemy(
        "Castle Guard", health=40, attack_power=8, xp_reward=12,
        max_ap=9,
        moves=[
            move("Shield Bash",  weight=5, effect_fn=damage_attack("1d6+2"), ap_cost=4),
            move("Leg Sweep",    weight=2, effect_fn=slow_player(stacks=1),   ap_cost=4, cooldown=3),
            move("Heavy Strike", weight=2, effect_fn=damage_attack("2d4+2", "HEAVY STRIKE"), ap_cost=6),
        ],
        drops=[("scrap", 0.5)],
        damage_type="bludgeoning",
        weaknesses={"force"},
        resistances={"piercing"},
        phase_triggers=[
            {"threshold": 0.85, "fn": _tutorial_guard_opening},
            {"threshold": 0.60, "fn": _tutorial_guard_phase},
            {"threshold": 0.25, "fn": _tutorial_guard_desperation},
        ],
        reactive_counters={"on_damaged": [_tutorial_guard_counter]},
        combo_scripts=[{"sequence": ["Shield Bash", "Heavy Strike"], "message": "A practiced one-two assault."}],
        combat_intro=_tutorial_guard_intro,
    )
    return guard

# ── Area 1 ────────────────────────────────────────────────────────────────────

def make_castle_guard():
    return Enemy(
        "Castle Guard", health=48, attack_power=10, xp_reward=15,
        max_ap=10,
        moves=[
            move("Shield Bash",    weight=5, effect_fn=damage_attack("1d6+3"),           ap_cost=4),
            move("Heavy Strike",   weight=3, effect_fn=damage_attack("2d6+2", "HEAVY STRIKE"), ap_cost=7, cooldown=0),
            move("Leg Sweep",      weight=2, effect_fn=slow_player(stacks=2),            ap_cost=4, cooldown=3),
        ],
        drops=[("scrap", 0.4)],
        damage_type="bludgeoning",
        weaknesses={"force"},
        resistances={"piercing"},
        phase_triggers=[{"threshold": 0.5, "fn": _guard_phase}],
        reactive_counters={"on_damaged": [_guard_counter]},
        combo_scripts=[{"sequence": ["Shield Bash", "Heavy Strike"], "message": "Shield Bash -> Heavy Strike!"}],
    )

def make_crossbowman():
    return Enemy(
        "Crossbowman", health=32, attack_power=8, xp_reward=12,
        max_ap=8,
        moves=[
            move("Piercing Shot", weight=5, effect_fn=ranged_attack_ignore_block("2d4"), ap_cost=4),
            move("Volley",        weight=2, effect_fn=double_hit("1d3+2"),           ap_cost=5, cooldown=2),
        ],
        drops=[("scrap", 0.4), ("bolt", 0.3)],
        damage_type="piercing",
        weaknesses={"lightning"},
        resistances={"piercing"},
    )


def make_goblin():
    return Enemy(
        "Goblin", health=30, attack_power=8, xp_reward=10,
        max_ap=7,
        moves=[
            move("Stab",        weight=5, effect_fn=damage_attack("1d6+2"),              ap_cost=4),
            move("Dirty Trick", weight=3, effect_fn=apply_enemy_weak(stacks=1),          ap_cost=3),
        ],
        drops=[("scrap", 0.4), ("gold coin", 0.2)],
    )


def make_goblin_guard():
    return Enemy(
        "Goblin Guard", health=40, attack_power=9, xp_reward=12,
        max_ap=8,
        moves=[
            move("Jab",         weight=5, effect_fn=damage_attack("1d6+3"),              ap_cost=4),
            move("Dirty Trick", weight=3, effect_fn=apply_enemy_weak(stacks=2),          ap_cost=3),
            move("Hex Chant",   weight=2, effect_fn=soul_tax_player(stacks=1),           ap_cost=6, cooldown=3),
        ],
        drops=[("scrap", 0.5), ("gold coin", 0.25)],
    )


def make_goblin_archer():
    return Enemy(
        "Goblin Archer", health=30, attack_power=8, xp_reward=10,
        max_ap=8,
        moves=[
            move("Quick Shot",     weight=5, effect_fn=damage_attack("1d4+4"),         ap_cost=3),
            move("Crippling Shot", weight=2, effect_fn=slow_player(stacks=3),         ap_cost=5, cooldown=3),
        ],
        drops=[("scrap", 0.5), ("gold coin", 0.2)],
    )


def make_giant_rat():
    return Enemy(
        "Giant Rat", health=26, attack_power=6, xp_reward=8,
        max_ap=6,
        moves=[
            move("Gnaw",       weight=6, effect_fn=damage_attack("1d4+3"), ap_cost=4),
            move("Feral Bite", weight=4, effect_fn=poison_attack(stacks=1, damage_expr="1d4+2"), ap_cost=5),
        ],
        damage_type="piercing",
        weaknesses={"fire", "bludgeoning"},
    )


def make_rat_swarm():
    return Enemy(
        "Rat Swarm", health=42, attack_power=8, xp_reward=12,
        max_ap=10,
        moves=[
            move("Surge",          weight=5, effect_fn=double_hit(damage_expr="1d4+3"), ap_cost=5),
            move("Gnaw Frenzy",    weight=3, effect_fn=damage_attack("1d6+2"),          ap_cost=4),
            move("Filthy Bite",    weight=2, effect_fn=poison_attack(stacks=2, damage_expr="1d6+2"), ap_cost=5),
            move("Frenzied Rush",  weight=1, effect_fn=haste_self(stacks=2),           ap_cost=3, cooldown=4),
        ],
    )


def make_skeleton_servant():
    return Enemy(
        "Skeleton Servant", health=32, attack_power=8, xp_reward=10,
        max_ap=8,
        moves=[
            move("Bone Strike",     weight=5, effect_fn=damage_attack("1d6+2"),          ap_cost=4),
        ],
        drops=[("bone", 1.0)],
        damage_type="bludgeoning",
        weaknesses={"bludgeoning", "force"},
        resistances={"piercing"},
    )


def make_skeleton():
    return Enemy(
        "Skeleton", health=36, attack_power=9, xp_reward=12,
        max_ap=8,
        moves=[
            move("Bone Strike",   weight=5, effect_fn=damage_attack("1d6+2"),          ap_cost=4),
        ],
        drops=[("bone", 1.0)],
    )


def make_skeleton_guard():
    return Enemy(
        "Skeleton Guard", health=46, attack_power=9, xp_reward=12,
        max_ap=9,
        moves=[
            move("Bone Strike",   weight=5, effect_fn=damage_attack("1d6+2"),          ap_cost=4),
            move("Shield Bash", weight=5, effect_fn=damage_attack("1d6+3"), ap_cost=4),
            move("Heavy Strike", weight=3, effect_fn=damage_attack("2d6+2", "HEAVY STRIKE"), ap_cost=7, cooldown=0),
        ],
        drops=[("bone", 1.0)],
    )


def make_wraith():
    return Enemy(
        "Wraith", health=48, attack_power=12, xp_reward=20,
        max_ap=10,
        moves=[
            move("Spectral Touch",  weight=4, effect_fn=damage_attack("1d6+4"),          ap_cost=4),
            move("Soul Drain",      weight=3, effect_fn=soul_tax_player(stacks=1),      ap_cost=7, cooldown=2),
        ],
    )


def make_bone_archer():
    return Enemy(
        "Bone Archer", health=38, attack_power=10, xp_reward=18,
        max_ap=8,
        moves=[
            move("Bone Arrow",     weight=5, effect_fn=damage_attack("1d6+5"),          ap_cost=3),
        ],
        drops=[("bone", 1.0)],
    )


def make_crypt_warden():
    return Enemy(
        "Crypt Warden", health=130, attack_power=18, xp_reward=50,
        max_ap=16,
        moves=[
            move("Spectral Slash",    weight=4, effect_fn=damage_attack("2d6+4"),     ap_cost=5),
            move("Barrier",  weight=2, effect_fn=shield_allies("1d8+5"), ap_cost=5, cooldown=2),
            move("Aegis",           weight=2, effect_fn=shield_self("1d8+6"),        ap_cost=4, cooldown=2),
            move("Iron Bastion",      weight=1, effect_fn=fortify_self(stacks=3),     ap_cost=5, cooldown=5),
        ],
        guaranteed_relic="wardens brand",
        damage_type="force",
        weaknesses={"lightning"},
        resistances={"slashing", "piercing"},
        phase_triggers=[{"threshold": 0.66, "fn": _warden_phase}, {"threshold": 0.33, "fn": _warden_phase}],
        combo_scripts=[{"sequence": ["Barrier", "Aegis"], "message": "Layered defenses empower its next action.", "grant_ap": 2}],
    )
