# rooms/enemy_data.py
"""
Enemy factory functions.
Each call returns a fresh Enemy instance ready to be added to a room.
Import these in area files instead of constructing enemies inline.
"""
from entities.enemy import Enemy
from entities.enemy_moves import (
    move, basic_attack, heavy_attack, poison_attack,
    enrage_self, apply_enemy_vulnerable, apply_enemy_weak,
    stun_attack, self_heal, double_hit, volatile_self, disorient_attack,
)


# ── Area 1 ────────────────────────────────────────────────────────────────────

def make_castle_guard():
    return Enemy(
        "Castle Guard", health=35, attack_power=10, xp_reward=15,
        moves=[
            move("Shield Bash",    weight=5, effect_fn=basic_attack()),
            move("Heavy Strike",   weight=3, effect_fn=heavy_attack(1.6, "HEAVY STRIKE")),
            move("Disorient Blow", weight=2, effect_fn=disorient_attack(), cooldown=3),
        ]
    )


def make_goblin_guard():
    return Enemy(
        "Goblin Guard", health=28, attack_power=9, xp_reward=12,
        moves=[
            move("Jab",          weight=5, effect_fn=basic_attack()),
            move("Dirty Trick",  weight=3, effect_fn=apply_enemy_weak(stacks=2)),
            move("Poison Blade", weight=2, effect_fn=poison_attack(stacks=1)),
        ]
    )


def make_goblin_archer():
    return Enemy(
        "Goblin Archer", health=20, attack_power=8, xp_reward=10,
        moves=[
            move("Quick Shot",    weight=5, effect_fn=basic_attack(min_dmg=5, max_dmg=9)),
            move("Poison Arrow",  weight=3, effect_fn=poison_attack(stacks=2)),
            move("Weakening Hex", weight=2, effect_fn=apply_enemy_weak(stacks=2)),
        ]
    )


def make_giant_rat():
    return Enemy(
        "Giant Rat", health=18, attack_power=6, xp_reward=8,
        moves=[
            move("Gnaw",       weight=6, effect_fn=basic_attack()),
            move("Feral Bite", weight=4, effect_fn=poison_attack(stacks=1)),
        ]
    )


def make_rat_swarm():
    return Enemy(
        "Rat Swarm", health=24, attack_power=8, xp_reward=12,
        moves=[
            move("Surge",       weight=5, effect_fn=double_hit()),
            move("Gnaw Frenzy", weight=3, effect_fn=basic_attack()),
            move("Filthy Bite", weight=2, effect_fn=poison_attack(stacks=2)),
        ]
    )


def make_skeleton_servant():
    return Enemy(
        "Skeleton Servant", health=22, attack_power=8, xp_reward=10,
        moves=[
            move("Bony Claw",     weight=5, effect_fn=basic_attack()),
            move("Rattling Blow", weight=3, effect_fn=apply_enemy_weak(stacks=1)),
            move("Bone Splinter", weight=2, effect_fn=stun_attack(), cooldown=3),
        ]
    )


def make_skeleton():
    return Enemy(
        "Skeleton", health=25, attack_power=9, xp_reward=12,
        moves=[
            move("Bone Strike",     weight=5, effect_fn=basic_attack()),
            move("Rattling Blow",   weight=3, effect_fn=apply_enemy_weak(stacks=2)),
            move("Staggering Slam", weight=2, effect_fn=stun_attack()),
        ]
    )


def make_zombie():
    return Enemy(
        "Rotting Zombie", health=35, attack_power=8, xp_reward=14,
        moves=[
            move("Shambling Claw", weight=5, effect_fn=basic_attack()),
            move("Putrid Grasp",   weight=3, effect_fn=poison_attack(stacks=2)),
            move("Undying Surge",  weight=2, effect_fn=self_heal(8), cooldown=3),
        ]
    )


def make_wraith():
    return Enemy(
        "Wraith", health=30, attack_power=12, xp_reward=20,
        moves=[
            move("Spectral Touch", weight=5, effect_fn=basic_attack()),
            move("Soul Leech",     weight=3, effect_fn=poison_attack(stacks=2)),
            move("Phase Burst",    weight=2, effect_fn=volatile_self(), cooldown=3),
        ]
    )


def make_bone_archer():
    return Enemy(
        "Bone Archer", health=25, attack_power=10, xp_reward=18,
        moves=[
            move("Bone Arrow",      weight=5, effect_fn=basic_attack(min_dmg=6, max_dmg=11)),
            move("Venomous Shaft",  weight=3, effect_fn=poison_attack(stacks=3)),
            move("Vulnerable Shot", weight=2, effect_fn=apply_enemy_vulnerable(stacks=2)),
        ]
    )


def make_crypt_warden():
    return Enemy(
        "Crypt Warden", health=70, attack_power=18, xp_reward=50,
        moves=[
            move("Spectral Slash",    weight=4, effect_fn=basic_attack()),
            move("Death Grip",        weight=3, effect_fn=heavy_attack(2.0, "DEATH GRIP"), cooldown=2),
            move("Soul Drain",        weight=2, effect_fn=poison_attack(stacks=3)),
            move("Blood Frenzy",      weight=1, effect_fn=enrage_self(),                   cooldown=3),
            move("Disorienting Wail", weight=1, effect_fn=disorient_attack(),              cooldown=3),
        ]
    )