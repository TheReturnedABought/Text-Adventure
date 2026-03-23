# entities/enemy_moves.py
"""
Reusable move effect functions and the move() factory.

Each effect has signature: fn(enemy, player) -> None

The move() factory now accepts ap_cost so every call site in enemy_data.py
sets cost explicitly — no hidden defaults leak into the system.
"""
import random
from utils.helpers import print_slow
from utils.status_effects import (
    apply_poison, apply_stun, apply_vulnerable,
    apply_weak, apply_rage, apply_volatile, apply_disorient,
)


# ── Effect functions ──────────────────────────────────────────────────────────

def basic_attack(min_dmg=None, max_dmg=None):
    def effect(enemy, player):
        lo = min_dmg or 4
        hi = max_dmg or enemy.attack_power
        dmg = random.randint(lo, hi)
        from utils.status_effects import consume_block
        actual, absorbed = consume_block(player, dmg)
        if absorbed:
            print_slow(f"  {enemy.name} strikes for {dmg} — 🛡 blocked {absorbed}, taking {actual}!")
        else:
            print_slow(f"  {enemy.name} strikes for {dmg}!")
        if actual:
            player.take_damage(actual)
            print_slow(f"  Your HP: {player.health}")
    return effect


def heavy_attack(multiplier=1.8, label="HEAVY STRIKE"):
    def effect(enemy, player):
        dmg = int(random.randint(4, enemy.attack_power) * multiplier)
        from utils.status_effects import consume_block
        actual, absorbed = consume_block(player, dmg)
        print_slow(f"  {enemy.name} — {label} for {dmg}!"
                   + (f" 🛡 blocked {absorbed}, taking {actual}!" if absorbed else ""))
        if actual:
            player.take_damage(actual)
            print_slow(f"  Your HP: {player.health}")
    return effect


def poison_attack(stacks=2):
    def effect(enemy, player):
        dmg = random.randint(4, enemy.attack_power)
        from utils.status_effects import consume_block
        actual, absorbed = consume_block(player, dmg)
        print_slow(f"  {enemy.name} makes a venomous strike for {dmg}!")
        if actual:
            player.take_damage(actual)
            print_slow(f"  Your HP: {player.health}")
        apply_poison(player, stacks)
    return effect


def enrage_self():
    def effect(enemy, player):
        print_slow(f"  {enemy.name} enters a blood frenzy!")
        apply_rage(enemy, 2)
    return effect


def apply_enemy_vulnerable(stacks=2):
    def effect(enemy, player):
        print_slow(f"  {enemy.name} tears at your defenses!")
        apply_vulnerable(player, stacks)
    return effect


def apply_enemy_weak(stacks=2):
    def effect(enemy, player):
        print_slow(f"  {enemy.name} saps your strength!")
        apply_weak(player, stacks)
    return effect


def stun_attack():
    def effect(enemy, player):
        dmg = random.randint(4, enemy.attack_power)
        from utils.status_effects import consume_block
        actual, absorbed = consume_block(player, dmg)
        print_slow(f"  {enemy.name} delivers a stunning blow for {dmg}!")
        if actual:
            player.take_damage(actual)
        apply_stun(player, 1)
        print_slow(f"  Your HP: {player.health} — you are STUNNED!")
    return effect


def self_heal(amount=10):
    def effect(enemy, player):
        healed = min(amount, enemy.max_health - enemy.health)
        enemy.health = min(enemy.health + amount, enemy.max_health)
        print_slow(f"  {enemy.name} regenerates {healed} HP! (HP: {enemy.health}/{enemy.max_health})")
    return effect


def double_hit():
    def effect(enemy, player):
        from utils.status_effects import consume_block
        print_slow(f"  {enemy.name} attacks twice!")
        for i in range(2):
            dmg = random.randint(3, max(3, enemy.attack_power // 2))
            actual, absorbed = consume_block(player, dmg)
            print_slow(f"    Hit {i+1}: {dmg}" + (f" — blocked {absorbed}, taking {actual}" if absorbed else ""))
            if actual:
                player.take_damage(actual)
        print_slow(f"  Your HP: {player.health}")
    return effect


def volatile_self():
    def effect(enemy, player):
        print_slow(f"  {enemy.name} ignites with wild energy!")
        apply_volatile(enemy)
    return effect


def disorient_attack():
    def effect(enemy, player):
        dmg = random.randint(4, enemy.attack_power)
        from utils.status_effects import consume_block
        actual, absorbed = consume_block(player, dmg)
        print_slow(f"  {enemy.name} spins and slashes for {dmg}!")
        if actual:
            player.take_damage(actual)
        apply_disorient(player, 1)
        print_slow(f"  Your HP: {player.health} — you are DISORIENTED!")
    return effect


def shield_allies(block_amount=8):
    """Signals combat loop to grant block to all living enemies."""
    def effect(enemy, player):
        print_slow(f"  {enemy.name} raises a spectral barrier for all allies!")
        enemy.statuses["_shield_allies"] = block_amount
    return effect


def fortify_self(stacks=1):
    def effect(enemy, player):
        from utils.status_effects import apply_fortify
        print_slow(f"  {enemy.name} settles into an iron stance!")
        apply_fortify(enemy, stacks)
    return effect


def haste_self(stacks=2):
    """
    Grant the enemy bonus AP this turn.
    With the AP system, Speed on an enemy adds to current_ap at turn start
    (handled in CombatSession._enemy_act). Stacks are consumed there.
    """
    def effect(enemy, player):
        from utils.status_effects import apply_speed
        print_slow(f"  {enemy.name} surges with unnatural speed!")
        apply_speed(enemy, stacks)
    return effect


def slow_player(stacks=2):
    def effect(enemy, player):
        from utils.status_effects import apply_slow
        print_slow(f"  {enemy.name} drags at your movements!")
        apply_slow(player, stacks)
    return effect


def curse_player(stacks=2):
    def effect(enemy, player):
        from utils.status_effects import apply_cursed
        print_slow(f"  {enemy.name} lays a withering curse upon you!")
        apply_cursed(player, stacks)
    return effect


def soul_tax_player(stacks=1):
    def effect(enemy, player):
        from utils.status_effects import apply_soul_tax
        print_slow(f"  {enemy.name} binds your power against you!")
        apply_soul_tax(player, stacks)
    return effect


# ── Move factory ──────────────────────────────────────────────────────────────

def move(name: str, weight: int, effect_fn, cooldown: int = 0, ap_cost: int = 4):
    """
    Create an EnemyMove.

    ap_cost is required at every call site in enemy_data.py so costs are
    always explicit — no silent defaults.  The parameter has a fallback of 4
    (standard attack cost) only so old call sites don't crash during migration.
    """
    from entities.enemy import EnemyMove
    return EnemyMove(name, weight, effect_fn, cooldown=cooldown, ap_cost=ap_cost)