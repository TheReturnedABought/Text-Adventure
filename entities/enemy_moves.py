"""
Enemy move effects and move() factory using dice for damage.
"""
from utils.helpers import print_slow
from utils.status_effects import (
    apply_poison, apply_stun, apply_vulnerable,
    apply_weak, apply_rage, apply_volatile, apply_disorient,
)
from utils.dice import roll


def resolve_enemy_hit(enemy, player, dmg, label=None, ignore_first_block=False, hit_index=None, detail=None):
    """
    Unified enemy-hit resolver so move attacks behave consistently with combat
    expectations (block, counter, sentinel thorns, intangible, unbreakable cap).
    """
    from utils.status_effects import consume_block, get_counter

    actual, absorbed = consume_block(player, dmg, ignore_first_block=ignore_first_block)

    if player.combat_flags.get("intangible"):
        actual = min(actual, 1)
    if label:
        msg = f"{enemy.name} — {label} for {dmg}"
    else:
        msg = f"{enemy.name} attacks for {dmg}"
    if detail:
        msg += f" [{detail}]"
    if hit_index is not None:
        msg += f" (hit {hit_index})"
    if ignore_first_block:
        msg += " (ignores first block)"

    if absorbed:
        msg += f" — 🛡 blocked {absorbed}, taking {actual}!"
    else:
        msg += "!"
    print_slow(f"  {msg}")

    if absorbed > 0:
        counter = get_counter(player)
        if counter:
            enemy.take_damage(counter)
            print_slow(f"  🔄 Counter — {enemy.name} takes {counter}! (HP:{max(enemy.health,0)})")
            player.statuses.pop("counter", None)

    if actual > 0:
        player.take_damage(actual)
        print_slow(f"  Your HP: {player.health}")
        sentinel = player.combat_flags.get("sentinel_thorns", 0)
        if sentinel:
            enemy.take_damage(sentinel)
            print_slow(f"  🛡 Sentinel — {enemy.name} takes {sentinel} thorns! (HP:{max(enemy.health,0)})")

    player.combat_flags.pop("intangible", None)
    return actual, absorbed


# ── Effect functions ──────────────────────────────────────────────────────────

def damage_attack(damage_expr: str, label=None):
    """Generic damage move using dice notation."""
    def effect(enemy, player):
        dmg = roll(damage_expr)
        resolve_enemy_hit(enemy, player, dmg, label=label, detail=damage_expr)
    effect.intent_hint = f"(ATK {damage_expr})"
    return effect


# ── Special Effects ───────────────────────────────────────────────────────────

def ranged_attack_ignore_block(damage_expr="2d4", label=None):
    """Damage that ignores the first block of the player."""
    def effect(enemy, player):
        dmg = roll(damage_expr)
        resolve_enemy_hit(enemy, player, dmg, label=label or "Piercing Shot", ignore_first_block=True, detail=damage_expr)
    effect.intent_hint = f"(ATK {damage_expr}, pierce)"
    return effect


def double_hit(damage_expr="1d4+3", label=None):
    """Hits twice."""
    def effect(enemy, player):
        for i in range(2):
            dmg = roll(damage_expr)
            resolve_enemy_hit(enemy, player, dmg, label=label, hit_index=i + 1, detail=damage_expr)
    effect.intent_hint = f"(ATK 2x{damage_expr})"
    return effect


def poison_attack(stacks=2, damage_expr="1d6+3"):
    def effect(enemy, player):
        dmg = roll(damage_expr)
        resolve_enemy_hit(enemy, player, dmg, label="Venomous Strike", detail=damage_expr)
        apply_poison(player, stacks)
    effect.intent_hint = f"(ATK {damage_expr} + POISON {stacks})"
    return effect


def enrage_self():
    def effect(enemy, player):
        print_slow(f"  {enemy.name} enters a blood frenzy!")
        apply_rage(enemy, 2)
    effect.intent_hint = "(BUFF Rage 2)"
    return effect


def apply_enemy_vulnerable(stacks=2):
    def effect(enemy, player):
        print_slow(f"  {enemy.name} tears at your defenses!")
        apply_vulnerable(player, stacks)
    effect.intent_hint = f"(DEBUFF Vulnerable {stacks})"
    return effect


def apply_enemy_weak(stacks=2):
    def effect(enemy, player):
        print_slow(f"  {enemy.name} saps your strength!")
        apply_weak(player, stacks)
    effect.intent_hint = f"(DEBUFF Weak {stacks})"
    return effect


def stun_attack(damage_expr="1d6+3"):
    def effect(enemy, player):
        dmg = roll(damage_expr)
        resolve_enemy_hit(enemy, player, dmg, label="Stunning Blow", detail=damage_expr)
        apply_stun(player, 1)
        print_slow(f"  Your HP: {player.health} — you are STUNNED!")
    effect.intent_hint = f"(ATK {damage_expr} + STUN)"
    return effect


def self_heal(amount_expr="1d8+2"):
    def effect(enemy, player):
        amount = roll(amount_expr)
        healed = min(amount, enemy.max_health - enemy.health)
        enemy.health = min(enemy.health + amount, enemy.max_health)
        print_slow(f"  {enemy.name} regenerates {healed} HP! (HP: {enemy.health}/{enemy.max_health})")
    effect.intent_hint = f"(HEAL {amount_expr})"
    return effect


def volatile_self():
    def effect(enemy, player):
        print_slow(f"  {enemy.name} ignites with wild energy!")
        apply_volatile(enemy)
    effect.intent_hint = "(BUFF Volatile)"
    return effect


def disorient_attack(damage_expr="1d6+3"):
    def effect(enemy, player):
        dmg = roll(damage_expr)
        resolve_enemy_hit(enemy, player, dmg, label="Disorienting Slash", detail=damage_expr)
        apply_disorient(player, 1)
        print_slow(f"  Your HP: {player.health} — you are DISORIENTED!")
    effect.intent_hint = f"(ATK {damage_expr} + DISORIENT)"
    return effect


def shield_self(block_dice="1d8+4"):
    """Signals combat loop to grant block to self."""
    def effect(enemy, player):
        amount = roll(block_dice)
        print_slow(f"  {enemy.name} raises a personal barrier!")
        enemy.statuses["_shield_self"] = amount
    effect.intent_hint = f"(BLOCK {block_dice} self)"
    return effect


def shield_allies(block_dice="1d8+4"):
    """Signals combat loop to grant block to all living enemies."""
    def effect(enemy, player):
        amount = roll(block_dice)
        print_slow(f"  {enemy.name} raises a spectral barrier for all allies!")
        enemy.statuses["_shield_allies"] = amount
    effect.intent_hint = f"(BLOCK {block_dice} all)"
    return effect


def fortify_self(stacks=1):
    def effect(enemy, player):
        from utils.status_effects import apply_fortify
        print_slow(f"  {enemy.name} settles into an iron stance!")
        apply_fortify(enemy, stacks)
    effect.intent_hint = f"(BUFF Fortify {stacks})"
    return effect


def haste_self(stacks=2):
    def effect(enemy, player):
        from utils.status_effects import apply_speed
        print_slow(f"  {enemy.name} surges with unnatural speed!")
        apply_speed(enemy, stacks)
    effect.intent_hint = f"(BUFF Speed {stacks})"
    return effect


def slow_player(stacks=2):
    def effect(enemy, player):
        from utils.status_effects import apply_slow
        print_slow(f"  {enemy.name} drags at your movements!")
        apply_slow(player, stacks)
    effect.intent_hint = f"(DEBUFF Slow {stacks})"
    return effect


def curse_player(stacks=2):
    def effect(enemy, player):
        from utils.status_effects import apply_cursed
        print_slow(f"  {enemy.name} lays a withering curse upon you!")
        apply_cursed(player, stacks)
    effect.intent_hint = f"(DEBUFF Cursed {stacks})"
    return effect


def soul_tax_player(stacks=1):
    def effect(enemy, player):
        from utils.status_effects import apply_soul_tax
        print_slow(f"  {enemy.name} binds your power against you!")
        apply_soul_tax(player, stacks)
    effect.intent_hint = f"(DEBUFF SoulTax {stacks})"
    return effect


# ── Move factory ──────────────────────────────────────────────────────────────

def move(name: str, weight: int, effect_fn, cooldown: int = 0, ap_cost: int = 4, tags=None):
    """Create an EnemyMove."""
    from entities.enemy import EnemyMove
    mv = EnemyMove(name, weight, effect_fn, cooldown=cooldown, ap_cost=ap_cost, tags=tags)
    mv.intent_hint = getattr(effect_fn, "intent_hint", "")
    return mv
