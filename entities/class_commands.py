# entities/class_commands.py
"""
Effect functions for every class command using dice rolls for damage/block.

Signature:  fn(player, enemies, target, ctx) -> bool
"""
from utils.helpers import print_slow, BLUE, RESET
from utils.status_effects import (
    apply_poison, apply_stun, apply_vulnerable, apply_weak,
    apply_rage, apply_volatile, apply_disorient, apply_block,
    consume_block, get_block
)
from utils.dice import roll

# ────────────────────────────────
#  Shared helpers
# ────────────────────────────────
def _deal(player, enemy, dmg, ctx=None, label="You strike"):
    """Apply mark bonus, consume block, deal damage."""
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

# ────────────────────────────────
#  SOLDIER COMMANDS
# ────────────────────────────────
def cmd_brace(player, enemies, target, ctx):
    amount = roll("1d8") if get_block(player) == 0 else roll("1d3")
    apply_block(player, amount)
    print_slow(f"  🛡 Brace — +{amount} Block!")
    return True

def cmd_guard(player, enemies, target, ctx):
    blk = roll("1d8")
    apply_block(player, blk)
    player.combat_flags["guard_counter"] = 10
    print_slow(f"  🛡 Guard — +{blk} Block! (Counter 10 if block breaks)")
    return True

def cmd_berserk(player, enemies, target, ctx):
    apply_rage(player, 2)
    apply_volatile(player)
    print_slow(f"  🔥 Berserk — Rage ×2 + Volatile!")
    return True

def cmd_discipline(player, enemies, target, ctx):
    debuffs = ["poison","stun","vulnerable","weak","volatile","disorient"]
    removed = [d for d in debuffs if d in player.statuses]
    for d in removed:
        player.statuses.pop(d, None)
    blk = roll("2d10+3")
    apply_block(player, blk)
    ctx["discipline_no_atk"] = True
    summary = ", ".join(removed) if removed else "nothing"
    print_slow(f"  ⚔ Discipline — cleared [{summary}]; +{blk} Block; attacks disabled this turn.")
    return True

def cmd_rally(player, enemies, target, ctx):
    blk = roll("1d6")
    apply_block(player, blk)
    ctx["rally_bonus"] = ctx.get("rally_bonus",0) + blk
    print_slow(f"  ⚔ Rally — +{blk} Block! Next attack +{blk} damage.")
    return True

def cmd_cleave(player, enemies, target, ctx):
    dmg = int(roll("2d6+6")*0.75)
    print_slow(f"  ⚔ Cleave — striking all enemies twice for {dmg} each!")
    for e in _alive(enemies):
        for i in range(2):
            actual, absorbed = consume_block(e, dmg)
            e.take_damage(actual)
            tag = f" (blocked {absorbed})" if absorbed else ""
            print_slow(f"    {e.name} hit {i+1}: {actual}{tag} | HP:{max(e.health,0)}")
            if e.health <= 0:
                print_slow(f"  > {e.name} defeated! +{e.xp_reward} XP")
                player.gain_xp(e.xp_reward)
                break
    return True

def cmd_fortify(player, enemies, target, ctx):
    blk = roll("1d5")
    apply_block(player, blk)
    player.combat_flags["fortify"] = True
    print_slow(f"  🛡 Fortify — +{blk} Block now; continues every turn!")
    return True

def cmd_warcry(player, enemies, target, ctx):
    print_slow(f"  ⚔ Warcry — weakening all foes!")
    for e in _alive(enemies):
        apply_weak(e, 2)
        apply_vulnerable(e, 2)
    return True

def cmd_sentinel(player, enemies, target, ctx):
    blk = roll("2d8")
    apply_block(player, blk)
    player.combat_flags["sentinel_thorns"] = 4
    print_slow(f"  🛡 Sentinel — +{blk} Block! Attackers take 4 thorns.")
    return True

def cmd_execute(player, enemies, target, ctx):
    if not _require_target(target, "execute"):
        return False
    blk = get_block(player)
    block_mult = blk // 10
    player.statuses.pop("block", None)
    dmg = int(roll("2d6+6") * (3.0 if target.health/target.max_health < 0.3 else 2.0)) + block_mult
    _deal(player, target, dmg, ctx, "Execute:")
    print_slow(f"  ⚔ Execute ×{2 if target.health/target.max_health >= 0.3 else 3:.1f} (+{block_mult} from Block)")
    return True

def cmd_juggernaut(player, enemies, target, ctx):
    if not _require_target(target, "juggernaut"):
        return False
    dmg = roll("2d6+6")
    _deal(player, target, dmg, ctx, "Juggernaut:")
    apply_block(player, dmg)
    print_slow(f"  🛡 Juggernaut — gained {dmg} Block!")
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
    if len(target.statuses)>=3:
        apply_stun(target,1)
        print_slow(f"  ⚔ Overwhelm — {target.name} has {len(target.statuses)} statuses — STUNNED!")
    else:
        print_slow(f"  ⚔ Overwhelm — Weak 2 + Vulnerable 2 on {target.name}!")
    return True

# ────────────────────────────────
#  ROGUE COMMANDS
# ────────────────────────────────
def cmd_cut(player, enemies, target, ctx):
    if not _require_target(target, "cut"): return False
    dmg = roll("1d6+2")
    _deal(player, target, dmg, ctx, "Cut:")
    return True

def cmd_flow(player, enemies, target, ctx):
    ctx["flow_active"] = True
    ctx.setdefault("flow_used", set())
    print_slow(f"  🗡 Flow — actions cost −1 AP this turn; no repeating commands!")
    return True

def cmd_feint(player, enemies, target, ctx):
    if not _require_target(target, "feint"): return False
    apply_disorient(target,1)
    ctx["feint_no_miss"] = True
    print_slow(f"  🗡 Feint — {target.name} disoriented! Your next attack cannot miss.")
    return True

def cmd_mark(player, enemies, target, ctx):
    if not _require_target(target, "mark"): return False
    apply_vulnerable(target,2)
    ctx["mark_bonus"] = ctx.get("mark_bonus",0)+5
    print_slow(f"  🗡 Mark — {target.name} marked! Vulnerable 2 + next hit +5 damage.")
    return True

def cmd_venom(player, enemies, target, ctx):
    if not _require_target(target, "venom"): return False
    stacks = 4 if target.statuses.get("vulnerable",0)>0 else 3
    apply_poison(target, stacks)
    print_slow(f"  🗡 Venom — {target.name} poisoned ×{stacks}!" + (" (+1 Vulnerable bonus)" if stacks==4 else ""))
    return True

def cmd_flurry(player, enemies, target, ctx):
    if not _require_target(target, "flurry"): return False
    print_slow(f"  🗡 Flurry — three rapid strikes on {target.name}!")
    for i in range(3):
        if target.health<=0: break
        dmg = roll("1d8+2")
        actual, absorbed = consume_block(target, dmg)
        target.take_damage(actual)
        tag = f" (blocked {absorbed})" if absorbed else ""
        print_slow(f"    Hit {i+1}: {actual}{tag}")
    return True

def cmd_dash(player, enemies, target, ctx):
    blk = roll("1d8")
    apply_block(player, blk)
    if target and target.health>0:
        _deal(player, target, blk, ctx, "Dash:")
    print_slow(f"  🗡 Dash — +{blk} Block!")
    return True

def cmd_toxin(player, enemies, target, ctx):
    if not _require_target(target, "toxin"): return False
    current = target.statuses.get("poison",0)
    if current==0:
        apply_poison(target,2)
        print_slow(f"  🗡 Toxin — no poison to double, applied 2 stacks.")
    else:
        new_val = min(current*2,8)
        target.statuses["poison"]=new_val
        print_slow(f"  🗡 Toxin — doubled {target.name}'s poison: {current} → {new_val}!")
    return True

def cmd_assault(player, enemies, target, ctx):
    if not _require_target(target,"assault"): return False
    prior = ctx.get("actions_this_turn",0)
    hits = min(3+prior,6)
    print_slow(f"  🗡 Assault — {hits} strikes!")
    for i in range(hits):
        if target.health<=0: break
        dmg = roll(f"1d6+{i}")
        actual, absorbed = consume_block(target,dmg)
        target.take_damage(actual)
        tag = f" (blocked {absorbed})" if absorbed else ""
        print_slow(f"    Hit {i+1}: {actual}{tag}")
    return True

def cmd_evade(player, enemies, target, ctx):
    player.combat_flags["evade"] = True
    print_slow(f"  🗡 Evade — you prepare to dodge the next attack! (+2 AP if triggered)")
    return True

def cmd_pandemic(player, enemies, target, ctx):
    if not _require_target(target,"pandemic"): return False
    bonus = 3 if target.statuses.get("poison",0)>0 else 0
    stacks = 6 + bonus
    apply_poison(target, stacks)
    print_slow(f"  🗡 Pandemic — {target.name} infected ×{stacks}!" + (" (+3 already poisoned)" if bonus else ""))
    return True

def cmd_assassinate(player, enemies, target, ctx):
    if not _require_target(target,"assassinate"): return False
    dmg = roll("3d6+10")
    if ctx.get("actions_this_turn",0)==0:
        dmg = int(dmg*1.5)
        print_slow("  🗡 Assassinate — FIRST STRIKE BONUS!")
    _deal(player,target,dmg,ctx,"Assassinate:")
    return True

def cmd_shadowstrike(player, enemies, target, ctx):
    if not _require_target(target,"shadowstrike"): return False
    actions = max(ctx.get("actions_this_combat",1),1)
    dmg = min(6*actions,80)
    print_slow(f"  🗡 Shadowstrike — {actions} combat actions × 6 = {dmg} damage!")
    _deal(player,target,dmg,ctx,"Shadowstrike:")
    return True

# ────────────────────────────────
#  MAGE COMMANDS
# ────────────────────────────────
def _spend_mp(player, cost, ward=False):
    real_cost = max(0, cost - (1 if ward else 0))
    if player.mana < real_cost:
        print_slow(f"  {BLUE}Not enough MP! Need {real_cost}, have {player.mana}.{RESET}")
        return False
    player.mana -= real_cost
    if real_cost>0:
        print_slow(f"  {BLUE}[-{real_cost} MP → {player.mana}/{player.max_mana}]{RESET}")
    return True

def cmd_spark(player, enemies, target, ctx):
    if not _spend_mp(player,1,ctx.get("ward_active")): return False
    if not _require_target(target,"spark"): return False
    dmg = roll("1d8+4")
    _deal(player,target,dmg,ctx,"⚡ Spark:")
    return True

def cmd_bolt(player, enemies, target, ctx):
    if not _spend_mp(player,1,ctx.get("ward_active")): return False
    if not _require_target(target,"bolt"): return False
    dmg = roll("2d8+8")
    _deal(player,target,dmg,ctx,"⚡ Bolt:")
    return True

def cmd_ward(player, enemies, target, ctx):
    if not _spend_mp(player,1,ctx.get("ward_active")): return False
    blk = roll("1d8")
    apply_block(player, blk)
    ctx["ward_active"]=True
    print_slow(f"  {BLUE}🛡 Ward — +{blk} Block! Spells cost −1 MP this turn.{RESET}")
    return True

def cmd_curse(player, enemies, target, ctx):
    if not _require_target(target,"curse"): return False
    apply_vulnerable(target,2)
    apply_weak(target,2)
    print_slow(f"  {BLUE}🔮 Curse — Vulnerable 2 + Weak 2 on {target.name}!{RESET}")
    return True

def cmd_blaze(player, enemies, target, ctx):
    if not _spend_mp(player,2,ctx.get("ward_active")): return False
    if not _require_target(target,"blaze"): return False
    apply_poison(target, roll("1d4+2"))
    apply_volatile(target)
    print_slow(f"  {BLUE}🔥 Blaze — {target.name} takes Burn + Volatile!{RESET}")
    return True

def cmd_charm(player, enemies, target, ctx):
    if ctx.get("charm_cooldown"):
        print_slow(f"  {BLUE}Charm is on cooldown until next turn.{RESET}")
        return False
    if not _spend_mp(player,2,ctx.get("ward_active")): return False
    if not _require_target(target,"charm"): return False
    apply_stun(target,1)
    ctx["charm_cooldown"]=True
    print_slow(f"  {BLUE}🔮 Charm — {target.name} stunned!{RESET}")
    return True

def cmd_drain(player, enemies, target, ctx):
    if not _spend_mp(player,1,ctx.get("ward_active")): return False
    tgt = target if target and target.health>0 else None
    if not tgt:
        alive = _alive(enemies)
        if alive:
            tgt = max(alive,key=lambda e:e.statuses.get("poison",0))
    if tgt:
        stacks = tgt.statuses.pop("poison",0)
        if stacks:
            player.heal(stacks)
            print_slow(f"  {BLUE}🔮 Drain — absorbed {stacks} poison from {tgt.name}, healed {stacks} HP!{RESET}")
        else:
            player.heal(5)
            print_slow(f"  {BLUE}🔮 Drain — no poison on target; healed 5 HP.{RESET}")
    return True

def cmd_shatter(player, enemies, target, ctx):
    if not _spend_mp(player,2,ctx.get("ward_active")): return False
    if not _require_target(target,"shatter"): return False
    vuln = max(target.statuses.get("vulnerable",0),1)
    dmg = roll("2d6+4")*vuln
    _deal(player,target,dmg,ctx,"Shatter:")
    return True

def cmd_silence(player, enemies, target, ctx):
    if not _spend_mp(player,1,ctx.get("ward_active")): return False
    if not _require_target(target,"silence"): return False
    apply_stun(target,1)
    apply_weak(target,2)
    print_slow(f"  {BLUE}🔮 Silence — {target.name} silenced + Weak 2!{RESET}")
    return True

def cmd_torment(player, enemies, target, ctx):
    if not _spend_mp(player,2,ctx.get("ward_active")): return False
    if not _require_target(target,"torment"): return False
    apply_poison(target,roll("2d4+2"))
    apply_disorient(target)
    print_slow(f"  {BLUE}🔥 Torment — {target.name} poisoned + disoriented!{RESET}")
    return True

def cmd_obliterate(player, enemies, target, ctx):
    if not _spend_mp(player,3,ctx.get("ward_active")): return False
    if not _require_target(target,"obliterate"): return False
    dmg = roll("6d6+20")
    _deal(player,target,dmg,ctx,"Obliterate:")
    return True

def cmd_rift(player, enemies, target, ctx):
    """
    Mage AoE attack — strikes all enemies with arcane energy.
    MP cost: 3
    Damage: 3d6 per enemy
    """
    if not _spend_mp(player, 3, ctx.get("ward_active")):
        return False
    alive_enemies = _alive(enemies)
    if not alive_enemies:
        print_slow("  No enemies to hit with Rift.")
        return False
    print_slow(f"  {BLUE}🌌 Rift — unleashing arcane energy on all enemies!{RESET}")
    for e in alive_enemies:
        dmg = roll("3d6")
        _deal(player, e, dmg, ctx, "Rift:")
    return True

def cmd_apocalypse(player, enemies, target, ctx):
    if not _spend_mp(player,4,ctx.get("ward_active")): return False
    if not _require_target(target,"apocalypse"): return False
    total = sum(v for v in target.statuses.values() if isinstance(v,int))
    dmg = min(total*roll("1d5"),40)
    _deal(player,target,dmg,ctx,"Apocalypse:")
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