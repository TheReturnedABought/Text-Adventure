# rooms/enemy_data.py
"""
Enemy factory functions.

AP costs — design principle
────────────────────────────
Standard attack  : 4 AP     — enemy's basic action
Utility/debuff   : 3–4 AP   — cheap enough to chain after attacking
Heavy/special    : 6–9 AP   — usually exclusive (fills the budget alone)
Boss specials    : 7–9 AP

max_ap is set so enemies typically execute 1 strong action OR
2 cheaper ones per turn. Burden (–max_ap) meaningfully cuts this ceiling.

No move may be used twice in the same turn (enforced in CombatSession).
"""
from entities.enemy import Enemy
from entities.enemy_moves import (
    move, basic_attack, heavy_attack, poison_attack,
    enrage_self, apply_enemy_vulnerable, apply_enemy_weak,
    stun_attack, self_heal, double_hit, volatile_self, disorient_attack,
    shield_allies, slow_player, curse_player, soul_tax_player,
    haste_self, fortify_self,
)


# ── Area 1 ────────────────────────────────────────────────────────────────────

def make_castle_guard():
    """
    Methodical fighter. Can combo Shield Bash + Leg Sweep (4+4=8 of 10 AP),
    or spend almost all AP on a Heavy Strike (7). Burden cuts his ceiling fast.
    """
    return Enemy(
        "Castle Guard", health=35, attack_power=10, xp_reward=15,
        max_ap=10,
        moves=[
            move("Shield Bash",    weight=5, effect_fn=basic_attack(),         ap_cost=4),
            move("Heavy Strike",   weight=3, effect_fn=heavy_attack(1.6),      ap_cost=7, cooldown=0),
            move("Disorient Blow", weight=2, effect_fn=disorient_attack(),     ap_cost=5, cooldown=3),
            move("Leg Sweep",      weight=2, effect_fn=slow_player(stacks=2),  ap_cost=4, cooldown=3),
        ],
        drops=[("scrap", 0.4)],
    )


def make_goblin():
    """
    Fast and dirty. Stab(4) + Dirty Trick(3) = 7 AP — full combo every turn.
    Feels relentless despite low stats.
    """
    return Enemy(
        "Goblin", health=22, attack_power=8, xp_reward=10,
        max_ap=7,
        moves=[
            move("Stab",        weight=5, effect_fn=basic_attack(),              ap_cost=4),
            move("Dirty Trick", weight=3, effect_fn=apply_enemy_weak(stacks=1),  ap_cost=3),
        ],
        drops=[("scrap", 0.4), ("gold coin", 0.2)],
    )


def make_goblin_guard():
    """
    Can Jab(4) + Dirty Trick(3) = 7, or Hex Chant(6) alone.
    Hex Chant leaves 2 AP — not enough for anything, so it acts alone.
    """
    return Enemy(
        "Goblin Guard", health=28, attack_power=9, xp_reward=12,
        max_ap=8,
        moves=[
            move("Jab",         weight=5, effect_fn=basic_attack(),                    ap_cost=4),
            move("Dirty Trick", weight=3, effect_fn=apply_enemy_weak(stacks=2),        ap_cost=3),
            move("Hex Chant",   weight=2, effect_fn=soul_tax_player(stacks=1),         ap_cost=6, cooldown=3),
        ],
        drops=[("scrap", 0.5), ("gold coin", 0.25)],
    )


def make_goblin_archer():
    """
    Quick Shot(3) + Slow Shot(5) = 8 — a common deadly combo.
    Poison Arrow(5) alone uses most of the budget.
    """
    return Enemy(
        "Goblin Archer", health=20, attack_power=8, xp_reward=10,
        max_ap=8,
        moves=[
            move("Quick Shot",     weight=5, effect_fn=basic_attack(min_dmg=5, max_dmg=9), ap_cost=3),
            move("Poison Arrow",   weight=3, effect_fn=poison_attack(stacks=2),             ap_cost=5),
            move("Crippling Shot", weight=2, effect_fn=slow_player(stacks=3),               ap_cost=5, cooldown=3),
        ],
        drops=[("scrap", 0.5), ("gold coin", 0.2)],
    )


def make_giant_rat():
    """
    Simple. Usually one action per turn (Gnaw 4 or Feral Bite 5 of 6 AP).
    """
    return Enemy(
        "Giant Rat", health=18, attack_power=6, xp_reward=8,
        max_ap=6,
        moves=[
            move("Gnaw",       weight=6, effect_fn=basic_attack(),          ap_cost=4),
            move("Feral Bite", weight=4, effect_fn=poison_attack(stacks=1), ap_cost=5),
        ],
    )


def make_rat_swarm():
    """
    Frenzied multi-action. Surge(5) + Frenzied Rush(3) = 8,
    or Gnaw Frenzy(4) + Filthy Bite(5) = 9.
    """
    return Enemy(
        "Rat Swarm", health=24, attack_power=8, xp_reward=12,
        max_ap=10,
        moves=[
            move("Surge",          weight=5, effect_fn=double_hit(),                ap_cost=5),
            move("Gnaw Frenzy",    weight=3, effect_fn=basic_attack(),              ap_cost=4),
            move("Filthy Bite",    weight=2, effect_fn=poison_attack(stacks=2),     ap_cost=5),
            move("Frenzied Rush",  weight=1, effect_fn=haste_self(stacks=2),        ap_cost=3, cooldown=4),
        ],
    )


def make_skeleton_servant():
    """
    Defensive attrition. Bony Claw(4) + Bone Fortify(4) = 8 (full budget).
    Rattling Blow(5) leaves only 3 AP — nothing fits so it acts alone.
    """
    return Enemy(
        "Skeleton Servant", health=22, attack_power=8, xp_reward=10,
        max_ap=8,
        moves=[
            move("Bony Claw",     weight=5, effect_fn=basic_attack(),                   ap_cost=4),
            move("Rattling Blow", weight=3, effect_fn=apply_enemy_weak(stacks=1),       ap_cost=5),
            move("Bone Fortify",  weight=2, effect_fn=fortify_self(stacks=2),           ap_cost=4, cooldown=4),
        ],
        drops=[("bone", 1.0)],
    )


def make_skeleton():
    return Enemy(
        "Skeleton", health=25, attack_power=9, xp_reward=12,
        max_ap=8,
        moves=[
            move("Bone Strike",   weight=5, effect_fn=basic_attack(),                   ap_cost=4),
            move("Rattling Blow", weight=3, effect_fn=apply_enemy_weak(stacks=2),       ap_cost=5),
            move("Bone Fortify",  weight=2, effect_fn=fortify_self(stacks=2),           ap_cost=4, cooldown=4),
        ],
        drops=[("bone", 1.0)],
    )


def make_zombie():
    return Enemy(
        "Rotting Zombie", health=35, attack_power=8, xp_reward=14,
        max_ap=9,
        moves=[
            move("Shambling Claw", weight=5, effect_fn=basic_attack(),              ap_cost=4),
            move("Putrid Grasp",   weight=3, effect_fn=poison_attack(stacks=2),     ap_cost=5),
            move("Undying Surge",  weight=2, effect_fn=self_heal(8),                ap_cost=4, cooldown=3),
            move("Foul Curse",     weight=1, effect_fn=curse_player(stacks=2),      ap_cost=5, cooldown=4),
        ],
    )


def make_wraith():
    """
    Soul-eater. Soul Drain(7) + Spectral Haste(3) = 10 (full budget, deadly).
    Spectral Touch(4) + Phase Burst(5) = 9.
    Haste now adds AP instead of bonus turn — still dangerous.
    """
    return Enemy(
        "Wraith", health=30, attack_power=12, xp_reward=20,
        max_ap=10,
        moves=[
            move("Spectral Touch",  weight=4, effect_fn=basic_attack(),                    ap_cost=4),
            move("Soul Drain",      weight=3, effect_fn=soul_tax_player(stacks=1),         ap_cost=7, cooldown=2),
            move("Phase Burst",     weight=2, effect_fn=volatile_self(),                   ap_cost=5, cooldown=3),
            move("Spectral Haste",  weight=1, effect_fn=haste_self(stacks=2),              ap_cost=3, cooldown=4),
        ],
    )


def make_bone_archer():
    """
    Bone Arrow(3) + Slow Shot(5) = 8 (full budget snipe-and-cripple combo).
    Venomous Shaft(6) alone dominates most of the budget.
    """
    return Enemy(
        "Bone Archer", health=25, attack_power=10, xp_reward=18,
        max_ap=8,
        moves=[
            move("Bone Arrow",     weight=5, effect_fn=basic_attack(min_dmg=6, max_dmg=11), ap_cost=3),
            move("Venomous Shaft", weight=3, effect_fn=poison_attack(stacks=3),              ap_cost=6),
            move("Slow Shot",      weight=2, effect_fn=slow_player(stacks=2),                ap_cost=5, cooldown=3),
        ],
        drops=[("bone", 1.0)],
    )


def make_crypt_warden():
    """
    Elite. 14 AP budget allows fearsome combos:
      Death Grip(9) + Blood Frenzy(4) = 13
      Spectral Slash(5) + Spectral Barrier(5) + Blood Frenzy(4) = 14
      Cursed Brand(7) + Spectral Slash(5) = 12
    Burden is especially punishing — drops from 14 to ≤8 quickly.
    """
    return Enemy(
        "Crypt Warden", health=70, attack_power=18, xp_reward=50,
        max_ap=14,
        moves=[
            move("Spectral Slash",    weight=4, effect_fn=basic_attack(),                    ap_cost=5),
            move("Death Grip",        weight=3, effect_fn=heavy_attack(2.0, "DEATH GRIP"),   ap_cost=9, cooldown=2),
            move("Blood Frenzy",      weight=2, effect_fn=enrage_self(),                     ap_cost=4, cooldown=3),
            move("Disorienting Wail", weight=1, effect_fn=disorient_attack(),                ap_cost=6, cooldown=3),
            move("Spectral Barrier",  weight=2, effect_fn=shield_allies(block_amount=8),     ap_cost=5, cooldown=2),
            move("Cursed Brand",      weight=2, effect_fn=curse_player(stacks=3),            ap_cost=7, cooldown=4),
            move("Iron Bastion",      weight=1, effect_fn=fortify_self(stacks=3),            ap_cost=5, cooldown=5),
        ],
        guaranteed_relic="wardens brand",
    )