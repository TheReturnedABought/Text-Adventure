# entities/class_commands.py
"""
Effect functions for every class command using dice rolls for damage/block.

Signature:  fn(player, enemies, target, ctx) -> bool
"""
from utils.helpers import print_slow, BLUE, RESET
from utils.status_effects import (
    apply_poison, apply_stun, apply_vulnerable, apply_weak,
    apply_rage, apply_volatile, apply_disorient, apply_block,
    consume_block, get_block, apply_speed
)
from utils.dice import roll, add_dice

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

def _roll_offensive(player, expr):
    bonus = player.statuses.get("strength", 0)
    return roll(add_dice(expr, bonus))

def _roll_defensive(player, expr):
    bonus = player.statuses.get("dexterity", 0)
    return roll(add_dice(expr, bonus))

def _prompt_multi_targets(enemies, hits, label="targets"):
    alive = _alive(enemies)
    if not alive:
        return []
    if len(alive) == 1:
        return [alive[0]] * hits

    print_slow(f"\n  Choose {hits} {label} (repeats allowed):")
    for i, e in enumerate(alive, 1):
        print(f"    [{i}] {e.name:<14} HP:{e.health}/{e.max_health}")

    chosen = []
    for idx in range(hits):
        while True:
            raw = input(f"  Target {idx+1}/{hits} (1-{len(alive)}): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(alive):
                chosen.append(alive[int(raw)-1])
                break
            print("  Invalid choice.")
    return chosen

def _grant_block(player, amount):
    if player.combat_flags.get("no_block_this_turn"):
        print_slow("  ⚔ You cannot gain Block for the rest of this turn.")
        return False
    apply_block(player, amount)
    return True

# ────────────────────────────────
#  SOLDIER COMMANDS
# ────────────────────────────────
def cmd_brace(player, enemies, target, ctx):
    amount = _roll_defensive(player, "1d6+2") if get_block(player) == 0 else _roll_defensive(player, "1d6")
    _grant_block(player, amount)
    print_slow(f"  🛡 Brace — +{amount} Block!")
    return True

def cmd_guard(player, enemies, target, ctx):
    blk = _roll_defensive(player, "1d6+1")
    _grant_block(player, blk)
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
    blk = _roll_defensive(player, "3d10+3")
    _grant_block(player, blk)
    ctx["discipline_no_atk"] = True
    summary = ", ".join(removed) if removed else "nothing"
    print_slow(f"  ⚔ Discipline — cleared [{summary}]; +{blk} Block; attacks disabled this turn.")
    return True

def cmd_rally(player, enemies, target, ctx):
    blk = _roll_defensive(player, "1d10")
    _grant_block(player, blk)
    ctx["rally_bonus"] = ctx.get("rally_bonus",0) + blk
    print_slow(f"  ⚔ Rally — +{blk} Block! Next attack +{blk} damage.")
    return True

def cmd_cleave(player, enemies, target, ctx):
    dmg = int(_roll_offensive(player, "2d6+6")*0.75)
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
    from utils.status_effects import apply_fortify
    apply_fortify(player, 4)
    print_slow(f"  🏰 Fortify — Fortify 4 applied! Gain 4 Block at the start of every turn.")
    return True

def cmd_warcry(player, enemies, target, ctx):
    print_slow(f"  ⚔ Warcry — weakening all foes!")
    for e in _alive(enemies):
        apply_weak(e, 2)
        apply_vulnerable(e, 2)
    return True

def cmd_sentinel(player, enemies, target, ctx):
    blk = _roll_defensive(player, "2d8")
    _grant_block(player, blk)
    player.combat_flags["sentinel_thorns"] = 4
    print_slow(f"  🛡 Sentinel — +{blk} Block! Attackers take 4 thorns.")
    return True

def cmd_execute(player, enemies, target, ctx):
    if not _require_target(target, "execute"):
        return False
    blk = get_block(player)
    block_mult = blk // 10
    player.statuses.pop("block", None)
    dmg = int(_roll_offensive(player, "2d6+6") * (3.0 if target.health/target.max_health < 0.3 else 2.0)) + block_mult
    _deal(player, target, dmg, ctx, "Execute:")
    print_slow(f"  ⚔ Execute ×{2 if target.health/target.max_health >= 0.3 else 3:.1f} (+{block_mult} from Block)")
    return True

def cmd_juggernaut(player, enemies, target, ctx):
    if not _require_target(target, "juggernaut"):
        return False
    dmg = _roll_offensive(player, "2d6+6")
    _deal(player, target, dmg, ctx, "Juggernaut:")
    _grant_block(player, dmg)
    print_slow(f"  🛡 Juggernaut — gained {dmg} Block!")
    return True

def cmd_unbreakable(player, enemies, target, ctx):
    player.combat_flags["persistent_block"] = True
    print_slow(f"  🛡 Unbreakable — Block no longer resets at end of turn this combat.")
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

def cmd_downcut(player, enemies, target, ctx):
    if not _require_target(target, "downcut"):
        return False
    dmg = _roll_offensive(player, "2d10+4")
    _deal(player, target, dmg, ctx, "Downcut:")
    player.combat_flags["no_block_this_turn"] = True
    print_slow("  ⚔ Downcut — you cannot gain Block for the rest of this turn.")
    return True

def cmd_defiant(player, enemies, target, ctx):
    player.combat_flags["defiant_ready"] = True
    print_slow("  ⚔ Defiant — if you end this round with Block, gain +2 AP next turn and +2 Strength.")
    return True

# ────────────────────────────────
#  ROGUE COMMANDS
# ────────────────────────────────
def cmd_cut(player, enemies, target, ctx):
    if not _require_target(target, "cut"): return False
    dmg = _roll_offensive(player, "1d4+4")
    _deal(player, target, dmg, ctx, "Cut:")
    return True

def cmd_flow(player, enemies, target, ctx):
    apply_speed(player, 5)
    print_slow("  🗡 Flow — Speed 5 applied (next 5 actions cost -1 AP).")
    return True

def cmd_feint(player, enemies, target, ctx):
    if not _require_target(target, "feint"): return False
    apply_disorient(target,2)
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
    targets = _prompt_multi_targets(enemies, 3, "flurry hits")
    if not targets:
        return False
    print_slow("  🗡 Flurry — hit three times for 1d4+3 each (same or different targets).")
    for i in range(3):
        t = targets[i]
        if t.health <= 0:
            continue
        dmg = _roll_offensive(player, "1d4+3")
        actual, absorbed = consume_block(t, dmg)
        t.take_damage(actual)
        tag = f" (blocked {absorbed})" if absorbed else ""
        print_slow(f"    Hit {i+1} on {t.name}: {actual}{tag}")
    return True

def cmd_dash(player, enemies, target, ctx):
    blk = _roll_defensive(player, "1d6+2")
    _grant_block(player, blk)
    if target and target.health>0:
        _deal(player, target, 8, ctx, "Dash:")
    apply_speed(player, 1)
    print_slow(f"  🗡 Dash — +{blk} Block, dealt 8, gained Speed 1.")
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
    hits = min(1+prior,6)
    print_slow(f"  🗡 Assault — {hits} strikes!")
    for i in range(hits):
        if target.health<=0: break
        dmg = _roll_offensive(player, f"1d6+{i}")
        actual, absorbed = consume_block(target,dmg)
        target.take_damage(actual)
        tag = f" (blocked {absorbed})" if absorbed else ""
        print_slow(f"    Hit {i+1}: {actual}{tag}")
    return True

def cmd_evade(player, enemies, target, ctx):
    player.statuses["evade"] = max(1, player.statuses.get("evade", 0))
    print_slow(f"  🗡 Evade — active for this enemy turn: 50% chance enemy attacks miss you; gain +2 AP when triggered.")
    return True

def cmd_aim(player, enemies, target, ctx):
    if player.combat_flags.get("aim_used_turn"):
        print_slow("  🗡 Aim can only be used once per turn.")
        return False
    player.combat_flags["aim_used_turn"] = True
    player.statuses["aim"] = player.statuses.get("aim", 0) + 1
    player.statuses["strength"] = player.statuses.get("strength", 0) + 1
    print_slow("  🗡 Aim — next attack cannot miss; gain Strength 1 this combat.")
    return True

def cmd_weave(player, enemies, target, ctx):
    player.statuses["dexterity"] = player.statuses.get("dexterity", 0) + 1
    print_slow("  🗡 Weave — gain Dexterity 1 this combat.")
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
    dmg = _roll_offensive(player, "3d6+10")
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

def cmd_spark(player, enemies, target, ctx):
    targets = _prompt_multi_targets(enemies, 2, "spark hits")
    if not targets:
        return False
    print_slow("  ⚡ Spark — hit twice for 1d4+2 Lightning damage each.")
    for i in range(2):
        t = targets[i]
        if t.health <= 0:
            continue
        dmg = _roll_offensive(player, "1d4+2")
        _deal(player, t, dmg, ctx, "⚡ Spark:")
    return True

def cmd_bolt(player, enemies, target, ctx):
    if not _require_target(target,"bolt"): return False
    dmg = _roll_offensive(player, "2d8+4")
    _deal(player,target,dmg,ctx,"⚡ Bolt:")
    apply_vulnerable(target, 1)
    if player.statuses.get("targeting", 0) > 0:
        player.statuses["targeting"] -= 1
        extra = _prompt_multi_targets(_alive(enemies), 1, "conduit bonus hit")
        if extra:
            _deal(player, extra[0], _roll_offensive(player, "2d8+4"), ctx, "⚡ Conduit bolt:")
            apply_vulnerable(extra[0], 1)
    return True

def cmd_coalesce(player, enemies, target, ctx):
    blk = _roll_defensive(player, "2d8+8")
    _grant_block(player, blk)
    player.combat_flags["coalesce_mp_discount_turns"] = 2
    print_slow(f"  {BLUE}🔮 Coalesce — +{blk} Block; spells cost −1 MP for 2 turns.{RESET}")
    return True

def cmd_delay(player, enemies, target, ctx):
    if not _require_target(target, "delay"): return False
    from utils.status_effects import apply_slow
    apply_slow(target, 1)
    print_slow(f"  {BLUE}🔮 Delay — {target.name} is Slowed 1.{RESET}")
    return True

def cmd_wave(player, enemies, target, ctx):
    print_slow(f"  {BLUE}🌊 Wave — lightning hits all enemies!{RESET}")
    for e in _alive(enemies):
        _deal(player, e, _roll_offensive(player, "1d6+4"), ctx, "Wave:")
    return True

def cmd_storm(player, enemies, target, ctx):
    print_slow(f"  {BLUE}⛈ Storm — heavy lightning hits all enemies!{RESET}")
    for e in _alive(enemies):
        _deal(player, e, _roll_offensive(player, "2d6+6"), ctx, "Storm:")
    return True

def cmd_ward(player, enemies, target, ctx):
    blk = _roll_defensive(player, "1d8+2")
    _grant_block(player, blk)
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
    if not _require_target(target,"blaze"): return False
    apply_poison(target, roll("1d4+2"))
    apply_volatile(target)
    print_slow(f"  {BLUE}🔥 Blaze — {target.name} takes Burn + Volatile!{RESET}")
    return True

def cmd_charm(player, enemies, target, ctx):
    if ctx.get("charm_cooldown"):
        print_slow(f"  {BLUE}Charm is on cooldown until next turn.{RESET}")
        return False
    if not _require_target(target,"charm"): return False
    apply_stun(target,1)
    ctx["charm_cooldown"]=True
    print_slow(f"  {BLUE}🔮 Charm — {target.name} stunned!{RESET}")
    return True

def cmd_drain(player, enemies, target, ctx):
    if not _require_target(target, "drain"):
        return False
    amount = _roll_offensive(player, "1d6+2")
    _deal(player, target, amount, ctx, "Drain:")
    player.heal(amount)
    print_slow(f"  {BLUE}🔮 Drain — healed for {amount}.{RESET}")
    return True

def cmd_shatter(player, enemies, target, ctx):
    if not _require_target(target,"shatter"): return False
    mana_bonus = max(player.mana, 0)
    dmg = (roll("1d6") * mana_bonus) + 3
    _deal(player,target,dmg,ctx,"Shatter:")
    return True

def cmd_silence(player, enemies, target, ctx):
    if not _require_target(target,"silence"): return False
    apply_stun(target,1)
    apply_weak(target,2)
    print_slow(f"  {BLUE}🔮 Silence — {target.name} silenced + Weak 2!{RESET}")
    return True

def cmd_torment(player, enemies, target, ctx):
    if not _require_target(target,"torment"): return False
    apply_poison(target,roll("2d4+2"))
    apply_disorient(target)
    print_slow(f"  {BLUE}🔥 Torment — {target.name} poisoned + disoriented!{RESET}")
    return True

def cmd_obliterate(player, enemies, target, ctx):
    if not _require_target(target,"obliterate"): return False
    dmg = roll("6d6+20")
    _deal(player,target,dmg,ctx,"Obliterate:")
    return True

def cmd_rift(player, enemies, target, ctx):
    """
    Mage utility — restore 3 MP; apply Vulnerable 1 to yourself and all living enemies.
    MP cost: 1
    """
    from utils.status_effects import apply_vulnerable
    gained = min(3, player.max_mana - player.mana)
    player.mana += gained
    print_slow(f"  {BLUE}🌌 Rift — +{gained} MP! ({player.mana}/{player.max_mana}){RESET}")
    apply_vulnerable(player, 1)
    for e in _alive(enemies):
        apply_vulnerable(e, 1)
    print_slow(f"  {BLUE}🌌 Rift — Vulnerable 1 on you and all enemies!{RESET}")
    return True

def cmd_apocalypse(player, enemies, target, ctx):
    if not _require_target(target,"apocalypse"): return False
    total = sum(v for v in target.statuses.values() if isinstance(v,int))
    dmg = min(total*roll("1d5"),40)
    _deal(player,target,dmg,ctx,"Apocalypse:")
    return True

def cmd_conduit(player, enemies, target, ctx):
    player.statuses["targeting"] = player.statuses.get("targeting", 0) + 1
    print_slow(f"  {BLUE}🔮 Conduit — next non-AOE spell hits an additional target.{RESET}")
    return True

def cmd_icewall(player, enemies, target, ctx):
    blk = _roll_defensive(player, "2d8+3")
    _grant_block(player, blk)
    for e in _alive(enemies):
        apply_weak(e, 1)
    print_slow(f"  {BLUE}🧊 Icewall — +{blk} Block and Weak 1 to all enemies.{RESET}")
    return True

def cmd_quickshot(player, enemies, target, ctx):
    targets = _prompt_multi_targets(enemies, 4, "quickshot hits")
    if not targets:
        return False
    for t in targets:
        dmg = _roll_offensive(player, "1d4+2")
        _deal(player, t, dmg, ctx, "Quickshot:")
    return True

def cmd_plan(player, enemies, target, ctx):
    ap_discount = roll("1d4")
    player.combat_flags["plan_ap_discount_pending"] = ap_discount
    player.combat_flags["plan_mp_discount_pending"] = 1
    print_slow(f"  📜 Plan — queued. At the start of your next turn, your first command gets -{ap_discount} AP and -1 MP.")
    return True

def cmd_shielded(player, enemies, target, ctx):

    from utils.status_effects import apply_fortify
    apply_fortify(player, 2)
    player.combat_flags["shielded_pending"] = 1
    print_slow("  🛡 Shielded — Fortify 2. Next turn, your damaging actions grant 2d4 Block.")
    return True

def cmd_tempest(player, enemies, target, ctx):

    print_slow(f"  {BLUE}🌩 Tempest — devastating lightning on all enemies!{RESET}")
    for e in _alive(enemies):
        _deal(player, e, _roll_offensive(player, "3d8+3"), ctx, "Tempest:")
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
    "downcut":     (cmd_downcut,     True),
    "defiant":     (cmd_defiant,     False),
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
    "aim":          (cmd_aim,         False),
    "weave":        (cmd_weave,       False),
    "pandemic":     (cmd_pandemic,    True),
    "assassinate":  (cmd_assassinate, True),
    "shadowstrike": (cmd_shadowstrike,True),
    # Mage
    "spark":       (cmd_spark,       False),
    "bolt":        (cmd_bolt,        True),
    "coalesce":    (cmd_coalesce,    False),
    "delay":       (cmd_delay,       True),
    "wave":        (cmd_wave,        False),
    "storm":       (cmd_storm,       False),
    "drain":       (cmd_drain,       True),
    "silence":     (cmd_silence,     True),
    "torment":     (cmd_torment,     False),
    "obliterate":  (cmd_obliterate,  True),
    "rift":        (cmd_rift,        False),
    "tempest":     (cmd_tempest,     False),
    "apocalypse":  (cmd_apocalypse,  True),
    "conduit":     (cmd_conduit,     False),
    "icewall":     (cmd_icewall,     False),
    # Shared
    "quickshot":   (cmd_quickshot,   False),
    "plan":        (cmd_plan,        False),
    "shielded":    (cmd_shielded,    False),
}
