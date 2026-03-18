# entities/class_commands.py
"""
Effect functions for every class command.

Signature:  fn(player, enemies, target, ctx) -> bool
  player   – Player instance
  enemies  – list of ALL Enemy instances in the room (use alive check inside)
  target   – selected Enemy (None for self/AoE commands)
  ctx      – dict of within-turn and within-combat state:
               actions_this_turn   int
               actions_this_combat int
               ward_active         bool  (mage: -1 MP cost this turn)
               flow_active         bool  (rogue: -1 AP cost)
               flow_used           set   (rogue: commands used this turn)
               feint_no_miss       bool  (rogue: next attack can't miss)
               mark_bonus          int   (rogue: bonus dmg on next hit)
               rally_bonus         int   (soldier: bonus dmg on next attack)
               discipline_no_atk   bool  (soldier: can't attack this turn)
               charm_cooldown      bool  (mage: can't use charm again)
Returns True on success, False on failure (triggers AP refund in caller).
"""
import random
from utils.helpers import print_slow, BLUE, RESET
from utils.status_effects import (
    apply_poison, apply_stun, apply_vulnerable, apply_weak,
    apply_rage, apply_volatile, apply_disorient, apply_block,
    consume_block, consume_vulnerable, get_block,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _deal(player, enemy, dmg, ctx=None, label="You strike"):
    """Apply mark bonus, consume block, deal damage. Returns actual damage."""
    bonus = 0
    if ctx and ctx.get("mark_bonus", 0):
        bonus = ctx["mark_bonus"]
        ctx["mark_bonus"] = 0
        print_slow(f"  🗡 Mark bonus: +{bonus} damage!")
    total = dmg + bonus
    actual, absorbed = consume_block(enemy, total)
    enemy.take_damage(actual)
    if absorbed:
        print_slow(f"  {label} {enemy.name} for {total} — 🛡 blocked {absorbed}, taking {actual}!")
    else:
        print_slow(f"  {label} {enemy.name} for {total}!")
    print_slow(f"  {enemy.name} HP: {max(enemy.health, 0)}")
    if enemy.health <= 0:
        print_slow(f"  > {enemy.name} defeated! +{enemy.xp_reward} XP")
        player.gain_xp(enemy.xp_reward)
    return actual


def _require_target(target, cmd):
    if target is None or target.health <= 0:
        print_slow(f"  No valid target for {cmd}.")
        return False
    return True


def _alive(enemies):
    return [e for e in enemies if e.health > 0]


# ─────────────────────────────────────────────────────────────────────────────
#  SOLDIER
# ─────────────────────────────────────────────────────────────────────────────

def cmd_brace(player, enemies, target, ctx):
    amount = 8 if get_block(player) == 0 else 3
    apply_block(player, amount)
    print_slow(f"  🛡 Brace — +{amount} Block!")
    return True


def cmd_guard(player, enemies, target, ctx):
    apply_block(player, 8)
    player.combat_flags["guard_counter"] = 10
    print_slow(f"  🛡 Guard — +8 Block! (Counter 10 dmg if block breaks)")
    return True


def cmd_berserk(player, enemies, target, ctx):
    apply_rage(player, 2)
    apply_volatile(player)
    print_slow(f"  🔥 Berserk — Rage ×2 + Volatile!")
    return True


def cmd_discipline(player, enemies, target, ctx):
    debuffs = ["poison", "stun", "vulnerable", "weak", "volatile", "disorient"]
    removed = [d for d in debuffs if d in player.statuses]
    for d in removed:
        player.statuses.pop(d, None)
    apply_block(player, 15)
    ctx["discipline_no_atk"] = True
    summary = ", ".join(removed) if removed else "nothing"
    print_slow(f"  ⚔ Discipline — cleared [{summary}]; +15 Block; attacks disabled this turn.")
    return True


def cmd_rally(player, enemies, target, ctx):
    apply_block(player, 6)
    ctx["rally_bonus"] = ctx.get("rally_bonus", 0) + 6
    print_slow(f"  ⚔ Rally — +6 Block! Next attack +6 damage.")
    return True


def cmd_cleave(player, enemies, target, ctx):
    base = random.randint(8, 18)
    dmg = int(base * 0.75)
    print_slow(f"  ⚔ Cleave — striking all enemies twice for {dmg} each!")
    for e in _alive(enemies):
        for i in range(2):
            actual, absorbed = consume_block(e, dmg)
            e.take_damage(actual)
            tag = f" (blocked {absorbed})" if absorbed else ""
            print_slow(f"    {e.name} hit {i+1}: {actual} damage{tag} | HP: {max(e.health,0)}")
            if e.health <= 0:
                print_slow(f"  > {e.name} defeated! +{e.xp_reward} XP")
                player.gain_xp(e.xp_reward)
                break
    return True


def cmd_fortify(player, enemies, target, ctx):
    apply_block(player, 5)
    player.combat_flags["fortify"] = True
    print_slow(f"  🛡 Fortify — +5 Block now, and every turn-end this combat!")
    return True


def cmd_warcry(player, enemies, target, ctx):
    print_slow(f"  ⚔ Warcry — weakening all foes!")
    for e in _alive(enemies):
        apply_weak(e, 2)
        apply_vulnerable(e, 2)
    return True


def cmd_sentinel(player, enemies, target, ctx):
    apply_block(player, 16)
    player.combat_flags["sentinel_thorns"] = 4
    print_slow(f"  🛡 Sentinel — +16 Block! Attackers take 4 thorns damage.")
    return True


def cmd_execute(player, enemies, target, ctx):
    if not _require_target(target, "execute"):
        return False
    blk = get_block(player)
    block_mult = blk // 10
    player.statuses.pop("block", None)
    base = random.randint(8, 18)
    mult = 3.0 if target.health / max(target.max_health, 1) < 0.3 else 2.0
    mult += block_mult
    dmg = int(base * mult)
    _deal(player, target, dmg, ctx, "Execute:")
    print_slow(f"  ⚔ Execute ×{mult:.1f} (consumed {blk} Block for +{block_mult}×)")
    return True


def cmd_juggernaut(player, enemies, target, ctx):
    if not _require_target(target, "juggernaut"):
        return False
    dmg = random.randint(8, 18)
    actual = _deal(player, target, dmg, ctx, "Juggernaut:")
    apply_block(player, dmg)
    print_slow(f"  🛡 Juggernaut — gained {dmg} Block from damage dealt!")
    return True


def cmd_unbreakable(player, enemies, target, ctx):
    player.combat_flags["unbreakable"] = True
    player.combat_flags["persistent_block"] = True
    print_slow(f"  🛡 Unbreakable — damage capped at 6; Block persists between turns!")
    return True


def cmd_overwhelm(player, enemies, target, ctx):
    if not _require_target(target, "overwhelm"):
        return False
    apply_weak(target, 2)
    apply_vulnerable(target, 2)
    if len(target.statuses) >= 3:
        apply_stun(target, 1)
        print_slow(f"  ⚔ Overwhelm — {target.name} has {len(target.statuses)} statuses — STUNNED!")
    else:
        print_slow(f"  ⚔ Overwhelm — Weak 2 + Vulnerable 2 on {target.name}!")
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  ROGUE
# ─────────────────────────────────────────────────────────────────────────────

def cmd_cut(player, enemies, target, ctx):
    if not _require_target(target, "cut"):
        return False
    dmg = random.randint(6, 10)
    _deal(player, target, dmg, ctx, "Cut:")
    return True


def cmd_flow(player, enemies, target, ctx):
    ctx["flow_active"] = True
    ctx.setdefault("flow_used", set())
    print_slow(f"  🗡 Flow — actions cost −1 AP this turn; no repeating commands!")
    return True


def cmd_feint(player, enemies, target, ctx):
    if not _require_target(target, "feint"):
        return False
    apply_disorient(target, 1)
    ctx["feint_no_miss"] = True
    print_slow(f"  🗡 Feint — {target.name} disoriented! Your next attack cannot miss.")
    return True


def cmd_mark(player, enemies, target, ctx):
    if not _require_target(target, "mark"):
        return False
    apply_vulnerable(target, 2)
    ctx["mark_bonus"] = ctx.get("mark_bonus", 0) + 5
    print_slow(f"  🗡 Mark — {target.name} marked! Vulnerable 2 + next hit +5 damage.")
    return True


def cmd_venom(player, enemies, target, ctx):
    if not _require_target(target, "venom"):
        return False
    stacks = 4 if target.statuses.get("vulnerable", 0) > 0 else 3
    apply_poison(target, stacks)
    print_slow(f"  🗡 Venom — {target.name} poisoned ×{stacks}!" +
               (" (+1 Vulnerable bonus)" if stacks == 4 else ""))
    return True


def cmd_flurry(player, enemies, target, ctx):
    if not _require_target(target, "flurry"):
        return False
    print_slow(f"  🗡 Flurry — three rapid strikes on {target.name}!")
    for i in range(3):
        if target.health <= 0:
            break
        dmg = random.randint(4, 10)
        actual, absorbed = consume_block(target, dmg)
        target.take_damage(actual)
        tag = f" (blocked {absorbed})" if absorbed else ""
        print_slow(f"    Hit {i+1}: {actual}{tag}")
    print_slow(f"  {target.name} HP: {max(target.health,0)}")
    if target.health <= 0:
        print_slow(f"  > {target.name} defeated! +{target.xp_reward} XP")
        player.gain_xp(target.xp_reward)
    return True


def cmd_dash(player, enemies, target, ctx):
    apply_block(player, 8)
    if target and target.health > 0:
        _deal(player, target, 8, ctx, "Dash:")
    print_slow(f"  🗡 Dash — +8 Block!")
    return True


def cmd_toxin(player, enemies, target, ctx):
    if not _require_target(target, "toxin"):
        return False
    current = target.statuses.get("poison", 0)
    if current == 0:
        apply_poison(target, 2)
        print_slow(f"  🗡 Toxin — no poison to double, applied 2 stacks.")
    else:
        new_val = min(current * 2, 8)
        target.statuses["poison"] = new_val
        print_slow(f"  🗡 Toxin — doubled {target.name}'s poison: {current} → {new_val}!")
    return True


def cmd_assault(player, enemies, target, ctx):
    if not _require_target(target, "assault"):
        return False
    prior = ctx.get("actions_this_turn", 0)
    hits = min(3 + prior, 6)
    print_slow(f"  🗡 Assault — {hits} strikes ({prior} prior actions)!")
    for i in range(hits):
        if target.health <= 0:
            break
        dmg = random.randint(3 + i * 2, 8 + i * 2)
        actual, absorbed = consume_block(target, dmg)
        target.take_damage(actual)
        tag = f" (blocked {absorbed})" if absorbed else ""
        print_slow(f"    Hit {i+1}: {actual}{tag}")
    print_slow(f"  {target.name} HP: {max(target.health,0)}")
    if target.health <= 0:
        print_slow(f"  > {target.name} defeated! +{target.xp_reward} XP")
        player.gain_xp(target.xp_reward)
    return True


def cmd_evade(player, enemies, target, ctx):
    player.combat_flags["evade"] = True
    print_slow(f"  🗡 Evade — you prepare to dodge the next attack! (+2 AP if triggered)")
    return True


def cmd_pandemic(player, enemies, target, ctx):
    if not _require_target(target, "pandemic"):
        return False
    bonus = 3 if target.statuses.get("poison", 0) > 0 else 0
    stacks = 6 + bonus
    apply_poison(target, stacks)
    print_slow(f"  🗡 Pandemic — {target.name} infected ×{stacks}!" +
               (" (+3 already poisoned)" if bonus else ""))
    return True


def cmd_assassinate(player, enemies, target, ctx):
    if not _require_target(target, "assassinate"):
        return False
    first = ctx.get("actions_this_turn", 0) == 0
    base = random.randint(20, 35)
    if first:
        base = int(base * 1.5)
        print_slow(f"  🗡 Assassinate — FIRST STRIKE BONUS!")
    _deal(player, target, base, ctx, "Assassinate:")
    return True


def cmd_shadowstrike(player, enemies, target, ctx):
    if not _require_target(target, "shadowstrike"):
        return False
    actions = max(ctx.get("actions_this_combat", 1), 1)
    dmg = min(6 * actions, 80)
    print_slow(f"  🗡 Shadowstrike — {actions} combat actions × 6 = {dmg} damage!")
    _deal(player, target, dmg, ctx, "Shadowstrike:")
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  MAGE
# ─────────────────────────────────────────────────────────────────────────────

def _spend_mp(player, base_cost, ward=False):
    cost = max(0, base_cost - (1 if ward else 0))
    if player.mana < cost:
        print_slow(f"  {BLUE}Not enough MP! Need {cost}, have {player.mana}.{RESET}")
        return False
    player.mana -= cost
    if cost > 0:
        print_slow(f"  {BLUE}[-{cost} MP → {player.mana}/{player.max_mana}]{RESET}")
    return True


def cmd_spark(player, enemies, target, ctx):
    if not _spend_mp(player, 1, ctx.get("ward_active")): return False
    if not _require_target(target, "spark"): return False
    dmg = random.randint(8, 12)
    _deal(player, target, dmg, ctx, "⚡ Spark:")
    return True


def cmd_bolt(player, enemies, target, ctx):
    if not _spend_mp(player, 1, ctx.get("ward_active")): return False
    if not _require_target(target, "bolt"): return False
    dmg = random.randint(18, 26)
    _deal(player, target, dmg, ctx, "⚡ Bolt:")
    return True


def cmd_ward(player, enemies, target, ctx):
    if not _spend_mp(player, 1, ctx.get("ward_active")): return False
    apply_block(player, 8)
    ctx["ward_active"] = True
    print_slow(f"  {BLUE}🛡 Ward — +8 Block! Spells cost −1 MP this turn.{RESET}")
    return True


def cmd_curse(player, enemies, target, ctx):
    if not _require_target(target, "curse"): return False
    apply_vulnerable(target, 2)
    apply_weak(target, 2)
    print_slow(f"  {BLUE}🔮 Curse — Vulnerable 2 + Weak 2 on {target.name}!{RESET}")
    return True


def cmd_blaze(player, enemies, target, ctx):
    if not _spend_mp(player, 2, ctx.get("ward_active")): return False
    if not _require_target(target, "blaze"): return False
    apply_poison(target, 3)   # Burn = Poison
    apply_volatile(target)
    print_slow(f"  {BLUE}🔥 Blaze — {target.name} takes Burn 3 + Volatile!{RESET}")
    return True


def cmd_charm(player, enemies, target, ctx):
    if ctx.get("charm_cooldown"):
        print_slow(f"  {BLUE}Charm is on cooldown until next turn.{RESET}")
        return False
    if not _spend_mp(player, 2, ctx.get("ward_active")): return False
    if not _require_target(target, "charm"): return False
    apply_stun(target, 1)
    ctx["charm_cooldown"] = True
    print_slow(f"  {BLUE}🔮 Charm — {target.name} is stunned! (Charm on cooldown){RESET}")
    return True


def cmd_drain(player, enemies, target, ctx):
    if not _spend_mp(player, 1, ctx.get("ward_active")): return False
    tgt = target if (target and target.health > 0) else None
    if tgt is None:
        alive = _alive(enemies)
        if alive:
            tgt = max(alive, key=lambda e: e.statuses.get("poison", 0))
    if tgt:
        stacks = tgt.statuses.pop("poison", 0)
        if stacks:
            player.heal(stacks)
            print_slow(f"  {BLUE}🔮 Drain — absorbed {stacks} poison from {tgt.name}; healed {stacks} HP! (HP: {player.health}){RESET}")
        else:
            player.heal(5)
            print_slow(f"  {BLUE}🔮 Drain — no poison on target; healed 5 HP.{RESET}")
    return True


def cmd_shatter(player, enemies, target, ctx):
    if not _spend_mp(player, 2, ctx.get("ward_active")): return False
    if not _require_target(target, "shatter"): return False
    vuln = min(target.statuses.get("vulnerable", 0), 4)
    mult = max(1, vuln)
    base = random.randint(10, 18)
    dmg = base * mult
    print_slow(f"  {BLUE}🔮 Shatter — {base} × {mult} (Vulnerable stacks) = {dmg}!{RESET}")
    _deal(player, target, dmg, ctx, "Shatter:")
    return True


def cmd_silence(player, enemies, target, ctx):
    if not _spend_mp(player, 1, ctx.get("ward_active")): return False
    if not _require_target(target, "silence"): return False
    apply_stun(target, 1)
    apply_weak(target, 2)
    print_slow(f"  {BLUE}🔮 Silence — {target.name} silenced (loses turn) + Weak 2!{RESET}")
    return True


def cmd_torment(player, enemies, target, ctx):
    if not _spend_mp(player, 2, ctx.get("ward_active")): return False
    debuffs = ["poison", "stun", "vulnerable", "weak", "disorient"]
    print_slow(f"  {BLUE}🔮 Torment — extending all enemy debuffs!{RESET}")
    for e in _alive(enemies):
        extended = []
        for d in debuffs:
            if e.statuses.get(d, 0) > 0:
                e.statuses[d] += 1
                extended.append(d)
        if extended:
            print_slow(f"    {e.name}: {', '.join(extended)} +1 turn.")
    return True


def cmd_obliterate(player, enemies, target, ctx):
    if not _spend_mp(player, 3, ctx.get("ward_active")): return False
    if not _require_target(target, "obliterate"): return False
    dmg = random.randint(50, 70)
    print_slow(f"  {BLUE}💥 Obliterate!{RESET}")
    _deal(player, target, dmg, ctx, "Obliterate:")
    return True


def cmd_rift(player, enemies, target, ctx):
    if not _spend_mp(player, 1, ctx.get("ward_active")): return False
    gained = min(3, player.max_mana - player.mana)
    player.mana += gained
    print_slow(f"  {BLUE}🔮 Rift — +{gained} MP restored!{RESET}")
    apply_vulnerable(player, 1)
    print_slow(f"  Rift tears the veil — Vulnerable 1 applied to ALL:")
    for e in _alive(enemies):
        apply_vulnerable(e, 1)
    return True


def cmd_apocalypse(player, enemies, target, ctx):
    if not _spend_mp(player, 3, ctx.get("ward_active")): return False
    if not _require_target(target, "apocalypse"): return False
    total = sum(v for v in target.statuses.values() if isinstance(v, int))
    dmg = min(total * 5, 40)
    print_slow(f"  {BLUE}💥 Apocalypse — {total} stacks × 5 = {dmg} damage!{RESET}")
    _deal(player, target, dmg, ctx, "Apocalypse:")
    return True


# ─────────────────────────────────────────────────────────────────────────────
#  Registry  {command_name: (fn, needs_single_target)}
# ─────────────────────────────────────────────────────────────────────────────

COMMAND_EFFECTS = {
    # Soldier
    "brace":       (cmd_brace,       False),
    "guard":       (cmd_guard,       False),
    "berserk":     (cmd_berserk,     False),
    "discipline":  (cmd_discipline,  False),
    "rally":       (cmd_rally,       False),
    "cleave":      (cmd_cleave,      False),
    "fortify":     (cmd_fortify,     False),
    "warcry":      (cmd_warcry,      False),
    "sentinel":    (cmd_sentinel,    False),
    "execute":     (cmd_execute,     True),
    "juggernaut":  (cmd_juggernaut,  True),
    "unbreakable": (cmd_unbreakable, False),
    "overwhelm":   (cmd_overwhelm,   True),
    # Rogue
    "cut":          (cmd_cut,         True),
    "flow":         (cmd_flow,        False),
    "feint":        (cmd_feint,       True),
    "mark":         (cmd_mark,        True),
    "venom":        (cmd_venom,       True),
    "flurry":       (cmd_flurry,      True),
    "dash":         (cmd_dash,        True),
    "toxin":        (cmd_toxin,       True),
    "assault":      (cmd_assault,     True),
    "evade":        (cmd_evade,       False),
    "pandemic":     (cmd_pandemic,    True),
    "assassinate":  (cmd_assassinate, True),
    "shadowstrike": (cmd_shadowstrike,True),
    # Mage
    "spark":       (cmd_spark,       True),
    "bolt":        (cmd_bolt,        True),
    "ward":        (cmd_ward,        False),
    "curse":       (cmd_curse,       True),
    "blaze":       (cmd_blaze,       True),
    "charm":       (cmd_charm,       True),
    "drain":       (cmd_drain,       True),
    "shatter":     (cmd_shatter,     True),
    "silence":     (cmd_silence,     True),
    "torment":     (cmd_torment,     False),
    "obliterate":  (cmd_obliterate,  True),
    "rift":        (cmd_rift,        False),
    "apocalypse":  (cmd_apocalypse,  True),
}