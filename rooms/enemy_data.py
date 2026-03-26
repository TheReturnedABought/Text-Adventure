from entities.enemy import Enemy
from entities.enemy_moves import (
    move, damage_attack, poison_attack,
    enrage_self, apply_enemy_vulnerable, apply_enemy_weak,
    stun_attack, self_heal, volatile_self, disorient_attack,
    shield_allies, slow_player, curse_player, soul_tax_player,
    haste_self, fortify_self,
)


# ── Area 1 ────────────────────────────────────────────────────────────────────

def make_castle_guard():
    return Enemy(
        "Castle Guard", health=35, attack_power=10, xp_reward=15,
        max_ap=10,
        moves=[
            move("Shield Bash",    weight=5, effect_fn=damage_attack("1d6+3"),           ap_cost=4),
            move("Heavy Strike",   weight=3, effect_fn=damage_attack("2d6+2", "HEAVY STRIKE"), ap_cost=7, cooldown=0),
            move("Leg Sweep",      weight=2, effect_fn=slow_player(stacks=2),            ap_cost=4, cooldown=3),
        ],
        drops=[("scrap", 0.4)],
    )


def make_goblin():
    return Enemy(
        "Goblin", health=22, attack_power=8, xp_reward=10,
        max_ap=7,
        moves=[
            move("Stab",        weight=5, effect_fn=damage_attack("1d6+2"),              ap_cost=4),
            move("Dirty Trick", weight=3, effect_fn=apply_enemy_weak(stacks=1),          ap_cost=3),
        ],
        drops=[("scrap", 0.4), ("gold coin", 0.2)],
    )


def make_goblin_guard():
    return Enemy(
        "Goblin Guard", health=28, attack_power=9, xp_reward=12,
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
        "Goblin Archer", health=20, attack_power=8, xp_reward=10,
        max_ap=8,
        moves=[
            move("Quick Shot",     weight=5, effect_fn=damage_attack("1d4+4"),         ap_cost=3),
            move("Crippling Shot", weight=2, effect_fn=slow_player(stacks=3),         ap_cost=5, cooldown=3),
        ],
        drops=[("scrap", 0.5), ("gold coin", 0.2)],
    )


def make_giant_rat():
    return Enemy(
        "Giant Rat", health=18, attack_power=6, xp_reward=8,
        max_ap=6,
        moves=[
            move("Gnaw",       weight=6, effect_fn=damage_attack("1d4+3"), ap_cost=4),
            move("Feral Bite", weight=4, effect_fn=poison_attack(stacks=1, damage_expr="1d4+2"), ap_cost=5),
        ],
    )


def make_rat_swarm():
    return Enemy(
        "Rat Swarm", health=24, attack_power=8, xp_reward=12,
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
        "Skeleton Servant", health=22, attack_power=8, xp_reward=10,
        max_ap=8,
        moves=[
            move("Bone Strike",     weight=5, effect_fn=damage_attack("1d6+2"),          ap_cost=4),
        ],
        drops=[("bone", 1.0)],
    )


def make_skeleton():
    return Enemy(
        "Skeleton", health=25, attack_power=9, xp_reward=12,
        max_ap=8,
        moves=[
            move("Bone Strike",   weight=5, effect_fn=damage_attack("1d6+2"),          ap_cost=4),
        ],
        drops=[("bone", 1.0)],
    )


def make_skeleton_guard():
    return Enemy(
        "Skeleton", health=30, attack_power=9, xp_reward=12,
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
        "Wraith", health=30, attack_power=12, xp_reward=20,
        max_ap=10,
        moves=[
            move("Spectral Touch",  weight=4, effect_fn=damage_attack("1d6+4"),          ap_cost=4),
            move("Soul Drain",      weight=3, effect_fn=soul_tax_player(stacks=1),      ap_cost=7, cooldown=2),
        ],
    )


def make_bone_archer():
    return Enemy(
        "Bone Archer", health=25, attack_power=10, xp_reward=18,
        max_ap=8,
        moves=[
            move("Bone Arrow",     weight=5, effect_fn=damage_attack("1d6+5"),          ap_cost=3),
        ],
        drops=[("bone", 1.0)],
    )


def make_crypt_warden():
    return Enemy(
        "Crypt Warden", health=70, attack_power=18, xp_reward=50,
        max_ap=14,
        moves=[
            move("Spectral Slash",    weight=4, effect_fn=damage_attack("2d6+4"),     ap_cost=5),
            move("Barrier",  weight=2, effect_fn=shield_allies("1d8+5"), ap_cost=5, cooldown=2),
            move("Iron Bastion",      weight=1, effect_fn=fortify_self(stacks=3),     ap_cost=5, cooldown=5),
        ],
        guaranteed_relic="wardens brand",
    )