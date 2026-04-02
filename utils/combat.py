# utils/combat.py
"""
CombatSession — one full fight.

Dice integration
────────────────
  Player attack  : dice.roll(BASE_ATTACK_DICE)  e.g. "2d6+6"
  Player heal    : dice.roll(BASE_HEAL_DICE)
  Enemy attack   : enemy.roll_damage()  (uses enemy.damage_dice or fallback)

Passive relic hooks checked here
──────────────────────────────────
  ChippedSword   : +4 dmg / +1 AP cost on 'attack'
  GiantsBelt     : +25% on commands > 6 letters
  StarlitAnvil   : +50% + 1 AP on STARLIT letter commands
  DaggerSheath   : first 'cut'/'flurry' costs -1 AP
  BulwarkFragment: Block command when pre-block=0 → Rage 1
  TimekeepersWatch: end of turn, 2 Block per unspent AP (handled in trigger)
  Bloodstone     : checked via trigger, sets combat_flags["bloodstone_used"]

on_death_effect handling
─────────────────────────
  "shatter"  : 10 dmg + Weak 2 to player on enemy death (Cursed Statue)

_enemies list passed into relic ctx as ctx["_enemies"] so AOE relics work.
"""

import random
from utils.dice      import roll as dice_roll
from utils.helpers   import print_slow, print_status, BLUE, RESET
from utils.constants import (
    BASE_BLOCK,
    BASE_ATTACK_DICE, BASE_HEAL_DICE, HEAL_MP_COST,
    BASE_COMMANDS,
)
from utils.damage import apply_typed_damage, class_base_attack_type
from utils.status_effects import (
    tick_statuses, clear_block, modified_heal,
    is_stunned, is_volatile, is_disoriented, get_echo,
    apply_block, consume_weak, consume_vulnerable, consume_rage,
    format_statuses, get_block,
    get_regen, get_burden,
    get_fortify, get_speed, get_slow, get_soul_tax,
    apply_weak,
)
from entities.relic import (
    TRIGGER_ON_ACTION, TRIGGER_ON_ATTACK, TRIGGER_ON_HEAL,
    TRIGGER_ON_BLOCK, TRIGGER_ON_HIT, TRIGGER_TURN_END, TRIGGER_TURN_START,
)
from entities.class_commands import COMMAND_EFFECTS
from entities.class_data import cmd_ap_cost, get_command_def
from entities.class_data import cmd_mp_cost
from game_engine.parser import parse_command

_END = "end"
_NEXT = "next"
_DONE = "done"
_STARLIT = set("starlit")
_SHIELDED_DAMAGE_COMMANDS = {
    "cut", "flurry", "dash", "assault", "assassinate", "shadowstrike", "pandemic",
    "spark", "bolt", "wave", "storm", "drain", "torment", "obliterate", "tempest", "quickshot",
    "apocalypse", "execute", "juggernaut", "downcut", "cleave",
}


def _intent_hint(move):
    hint = getattr(move, "intent_hint", "")
    return f" {hint}" if hint else ""


def _win():
    try:
        from utils.window import window
        return window if window._active else None
    except Exception:
        return None


class CombatSession:

    def __init__(self, player, room):
        self.player  = player
        self.room    = room
        self.enemies = room.enemies[:4]

    # ══════════════════════════════════════════════════════════════════════════
    #  Public
    # ══════════════════════════════════════════════════════════════════════════

    def run(self):
        self._combat_start()
        while True:
            if not self._alive():
                self._victory()
                self._combat_end_cleanup()
                break
            enemy_alive = self._player_turn()
            if self.player.health <= 0:
                self._combat_end_cleanup()
                break
            if not enemy_alive:
                continue
            self._enemies_turn()
            if self.player.health <= 0:
                self._combat_end_cleanup()
                break

    # ══════════════════════════════════════════════════════════════════════════
    #  Setup / teardown
    # ══════════════════════════════════════════════════════════════════════════

    def _combat_start(self):
        p     = self.player
        alive = self._alive()
        p.reset_combat_state()

        if p.pending_combat_effects:
            print_slow("\n  The effect from before surges through you!")
            for effect, value in p.pending_combat_effects:
                self._apply_pending_effect(effect, value)
            p.pending_combat_effects.clear()
            input("  Press Enter to continue...")

        for relic in p.relics:
            if alive:
                relic.on_combat_start(p, alive[0])

        for e in alive:
            if hasattr(e, "on_combat_start"):
                e.on_combat_start(player=p, combat_session=self)

        if p.has_relic("Warden's Brand"):
            from utils.status_effects import apply_vulnerable
            for e in alive:
                apply_vulnerable(e, 1)

    def _victory(self):
        print()
        print_slow("  ✦ All enemies defeated! ✦")
        self._regen_ap()

        # Merchant's Ledger — gold after elite victory
        if any(getattr(e, "guaranteed_relic", None) for e in self.enemies):
            if self.player.has_relic("Merchant's Ledger"):
                self.player.gold = getattr(self.player, "gold", 0) + 50
                print_slow("  📒 Merchant's Ledger — +50 gold!")

        input("\n  Press Enter to continue...")
        p = self.player
        if p.level_ups or p.pending_command_choices or p.auto_unlocked_commands:
            from utils.display import show_levelup
            show_levelup(p)

    def _alive(self):
        return [e for e in self.enemies if e.health > 0 and not e.fled]

    def _apply_pending_effect(self, effect, value):
        from utils.status_effects import (
            apply_rage, apply_regen, apply_block as _blk, apply_poison,
        )
        p = self.player
        {
            "rage":   lambda: apply_rage(p, value),
            "regen":  lambda: apply_regen(p, value),
            "block":  lambda: _blk(p, value),
            "poison": lambda: apply_poison(p, value),
        }.get(effect, lambda: None)()

    # ══════════════════════════════════════════════════════════════════════════
    #  Player turn
    # ══════════════════════════════════════════════════════════════════════════

    def _player_turn(self):
        p = self.player
        self._regen_ap()
        self._plan_enemy_moves()
        alive = self._alive()
        p.trigger_relics(TRIGGER_TURN_START, alive[0] if alive else None, {})

        w = _win()
        if w:
            w.set_combat(p, self.room, self.enemies)

        self._show_status()
        ctx = self._build_ctx()

        while True:
            if not self._alive():
                return False
            signal = self._take_one_action(ctx)
            if signal == _DONE:
                return False
            if signal == _END:
                self._resolve_turn_end(ctx)
                return bool(self._alive())

    def _plan_enemy_moves(self):
        for e in self._alive():
            e.plan_turn()

    def _regen_ap(self):
        p = self.player
        burden        = p.statuses.get("burden", 0)
        effective_max = max(1, p.max_ap - burden)
        p.current_ap  = effective_max
        if burden:
            print_slow(f"  ⚖️ Burden — max AP reduced to {effective_max}/{p.max_ap}!")

        if p.combat_flags.get("evade_bonus_ap", 0):
            bonus = p.combat_flags.pop("evade_bonus_ap")
            p.current_ap = min(p.max_ap, p.current_ap + bonus)
            print_slow(f"  🗡 Evade bonus — +{bonus} AP! ({p.current_ap}/{p.max_ap})")

        if p.combat_flags.get("plan_ap_discount_pending", 0):
            p.combat_flags["plan_ap_discount_active"] = p.combat_flags.pop("plan_ap_discount_pending")
            p.combat_flags["plan_mp_discount_active"] = p.combat_flags.pop("plan_mp_discount_pending", 0)
            print_slow("  📜 Plan resolves — your first command this turn is discounted.")

        if p.combat_flags.pop("shielded_pending", 0) > 0:
            p.combat_flags["shielded_active"] = True
            print_slow("  🛡 Shielded activates — damaging actions grant 2d4 Block this turn.")

        # Borrow penalty
        if p.combat_flags.get("borrow_penalty", 0):
            penalty = p.combat_flags.pop("borrow_penalty")
            p.mana  = max(0, p.mana - penalty)
            print_slow(f"  💸 Borrow — −{penalty} MP! (MP: {p.mana}/{p.max_mana})")

        if not p.combat_flags.get("persistent_block"):
            clear_block(p)

        regen = get_regen(p)
        if regen > 0:
            p.heal(regen)
            print_slow(f"  🌿 Regen — +{regen} HP! (HP: {p.health})")

        fortify = get_fortify(p)
        if fortify > 0:
            apply_block(p, fortify)
            print_slow(f"  🏰 Fortify — +{fortify} Block!")

    def _build_ctx(self):
        p = self.player
        return {
            "actions_this_turn":   0,
            "actions_this_combat": p.actions_this_combat,
            "ward_active":         p.combat_flags.get("ward_turns_remaining", 0) > 0,
            "feint_no_miss":       False,
            "mark_bonus":          0,
            "rally_bonus":         p.combat_flags.pop("rally_bonus_pending", 0),
            "discipline_no_atk":   False,
            "charm_cooldown":      p.combat_flags.pop("charm_cooldown", False),
            "ap_spent_this_turn":  0,
            "_enemies":            self.enemies,   # for AOE relics
            "combat_session":      self,
            "last_command_this_turn": None,
        }

    def _resolve_turn_end(self, ctx):
        p     = self.player
        alive = self._alive()

        echo_cmd = get_echo(p)
        if echo_cmd and alive:
            repeats = 2 if p.has_relic("Echo Chamber") else 1
            for i in range(repeats):
                if not self._alive():
                    break
                lbl = f" (echo {i+1}/2)" if repeats > 1 else ""
                print_slow(f"  🔊 Echo — '{echo_cmd}' repeats{lbl}!")
                if echo_cmd == "attack":
                    self._do_attack(self._alive()[0], echo_cmd, ctx)
                elif echo_cmd == "heal":
                    self._do_heal(echo_cmd, ctx)
                elif echo_cmd == "block":
                    self._do_block(echo_cmd, ctx)

        first = self._alive()[0] if self._alive() else None
        p.trigger_relics(TRIGGER_TURN_END, first, ctx)

        if p.combat_flags.get("ward_turns_remaining", 0) > 0:
            p.combat_flags["ward_turns_remaining"] -= 1
            if p.combat_flags["ward_turns_remaining"] == 0:
                del p.combat_flags["ward_turns_remaining"]
                print_slow(f"  {BLUE}✦ Coalesce fades.{RESET}")

        for e in self._alive():
            tick_statuses(e)
        tick_statuses(p)
        p.combat_flags.pop("aim_used_turn", None)
        p.combat_flags.pop("shielded_active", None)

        # Clear per-combat-turn relic flags
        p.combat_flags.pop("bloodstone_used", None)
        p.combat_flags.pop("block_was_zero", None)
        p.combat_flags.pop("no_block_this_turn", None)

    # ══════════════════════════════════════════════════════════════════════════
    #  Per-action
    # ══════════════════════════════════════════════════════════════════════════

    def _take_one_action(self, ctx):
        p   = self.player
        raw = input("\n⚔ > ").lower().strip()
        if not raw:
            return _NEXT
        command, _ = parse_command(raw)

        if self._handle_meta(command):
            if command in ["end", "done", "pass"]:
                print_slow("  You end your turn.")
                return _END
            return _NEXT

        is_base  = command in BASE_COMMANDS
        is_class = command in p.known_commands and command in COMMAND_EFFECTS
        if not is_base and not is_class:
            print_slow(f"  Unknown command '{command}'. Type 'help' for options.")
            return _NEXT

        ap_cost = self._calc_ap_cost(command, ctx)
        if p.current_ap < ap_cost:
            print_slow(f"  Not enough AP! '{command}' costs {ap_cost}, you have {p.current_ap}.")
            print_slow("  Type 'end' to end your turn.")
            return _NEXT

        mp_spent = 0
        if is_class:
            cmd_def = get_command_def(p.char_class, command)
            mp_cost = cmd_mp_cost(cmd_def) if cmd_def else 0


            if ctx.get("ward_active"):
                 mp_cost = max(1, mp_cost - 1)
            if p.combat_flags.get("coalesce_mp_discount_turns", 0) > 0:
                mp_cost = max(1, mp_cost - 1)

            # Plan discount — all classes
            if p.combat_flags.get("plan_mp_discount_active", 0):
                discount = p.combat_flags.pop("plan_mp_discount_active")
                mp_cost = max(1, mp_cost - discount)
                print_slow(f"  📜 Plan — −{discount} MP on this command!")

            if p.mana < mp_cost:
                print_slow(f"  Not enough MP! '{command}' needs {mp_cost}, you have {p.mana}.")
                return _NEXT
            if mp_cost > 0:
                p.mana -= mp_cost
                mp_spent = mp_cost
                print_slow(f"  🔷 {command} costs {mp_cost} MP. (MP: {p.mana}/{p.max_mana})")
                ctx["_last_mp_spent"] = mp_cost

            # Tick coalesce after spend
            if p.char_class == "mage" and p.combat_flags.get("coalesce_mp_discount_turns", 0) > 0:
                p.combat_flags["coalesce_mp_discount_turns"] -= 1
                if p.combat_flags["coalesce_mp_discount_turns"] <= 0:
                    p.combat_flags.pop("coalesce_mp_discount_turns", None)
                    print_slow(f"  {BLUE}✦ Coalesce's MP discount fades.{RESET}")

        # Record pre-block AP for BulwarkFragment
        if command == "block":
            p.combat_flags["block_was_zero"] = get_block(p) == 0

        p.current_ap -= ap_cost
        ctx["ap_spent_this_turn"] += ap_cost

        soul_tax = get_soul_tax(p)
        if soul_tax and ap_cost > 0:
            dmg = soul_tax * ap_cost
            p.take_damage(dmg)
            print_slow(f"  ⚰ Soul Tax — {soul_tax}×{ap_cost}AP = {dmg} dmg! (HP:{p.health})")

        success, action_target = self._dispatch(command, raw, ctx)
        if not success:
            p.current_ap += ap_cost
            ctx["ap_spent_this_turn"] -= ap_cost
            if mp_spent:
                p.mana = min(p.max_mana, p.mana + mp_spent)
            ctx.pop("_last_mp_spent", None)
            return _NEXT

        result = self._post_action(command, raw, action_target, ctx)
        if result == _DONE:
            return _DONE

        if p.current_ap == 0:
            print_slow("  No AP remaining.")
            confirm = input("  Press Enter to end turn, or type a command: ").lower().strip()
            if not confirm or confirm in ["yes","y","end","done","pass"]:
                print_slow("  You end your turn.")
                return _END
        return _NEXT

    def _handle_meta(self, command):
        p = self.player
        if command in ["end","done","pass"]:
            return True
        if command in ["move","go","north","south","east","west","flee","run","escape"]:
            print_slow("  You cannot flee from combat!")
            return True
        if command in ["inventory","inv","i"]:
            from utils.actions import do_inventory
            do_inventory(p)
            return True
        if command in ["relics","relic"]:
            from utils.display import show_relics
            show_relics(p)
            return True
        if command in ["look","l"]:
            print_slow(f"  Fighting: {', '.join(e.name for e in self._alive())}.")
            return True
        if command in ["help","?"]:
            from utils.display import show_help
            show_help(p)
            input("  Press Enter to continue...")
            return True
        if command in ["journal","j"]:
            from utils.display import show_journal
            show_journal(p)
            return True
        return False

    # ── AP cost calculation (all passive relics) ──────────────────────────────

    @staticmethod
    def _claim_letters(command, free_letters, discounted, cap=None):
        claimed = 0
        for i, ch in enumerate(command):
            if cap is not None and claimed >= cap:
                break
            if ch in free_letters and not discounted[i]:
                discounted[i] = True
                claimed += 1
        return claimed

    def _calc_ap_cost(self, command, ctx):
        p = self.player

        # Base cost
        if command in BASE_COMMANDS:
            cost = BASE_COMMANDS[command]["ap_cost"]
        else:
            cmd_def = get_command_def(p.char_class, command)
            cost    = cmd_ap_cost(cmd_def) if cmd_def else len(command)

        discounted = [False] * len(command)

        # Sleightmaker's Glove
        if p.has_relic("Sleightmaker's Glove"):
            free = {"l"}
            if p.has_relic("Silent Lamb Wool"):
                free |= set("aeiou")
                print_slow("  🐑 Silent Lamb Wool — vowels count as 'l'!")
            d = self._claim_letters(command, free, discounted)
            if d:
                cost -= d
                print_slow(f"  🧤 Sleightmaker's Glove — {d}× free letter(s)!")

        # Bear Skin
        if p.has_relic("Bear Skin"):
            d = self._claim_letters(command, {"a"}, discounted, cap=2)
            if d:
                cost -= d
                print_slow(f"  🐻 Bear Skin — {d}× 'a' discount!")

        # Chipped Sword — attack costs +1
        if command == "attack" and p.has_relic("Chipped Sword"):
            cost += 1
            print_slow("  🗡 Chipped Sword — attack costs +1 AP!")

        # Starlit Anvil — commands containing all of STARLIT cost +1
        if p.has_relic("Starlit Anvil") and set(command) >= _STARLIT:
            cost += 1
            print_slow("  ⭐ Starlit Anvil — STARLIT letters, +1 AP!")

        # Dagger Sheath — first cut/flurry costs -1
        if command in ("cut","flurry") and p.has_relic("Dagger Sheath"):
            if not p.combat_flags.get("dagger_sheath_used"):
                cost -= 1
                p.combat_flags["dagger_sheath_used"] = True
                print_slow("  🗡 Dagger Sheath — first strike, -1 AP!")

        # Speed
        if get_speed(p) > 0:
            cost -= 1
            p.statuses["speed"] -= 1
            if p.statuses["speed"] <= 0:
                del p.statuses["speed"]
                print_slow("  💨 Speed fades.")
            else:
                print_slow(f"  💨 Speed — −1 AP! ({p.statuses.get('speed',0)} left)")

        # Slow
        if get_slow(p) > 0:
            cost += 1
            p.statuses["slow"] -= 1
            if p.statuses["slow"] <= 0:
                del p.statuses["slow"]
                print_slow("  🕸 Slow fades.")
            else:
                print_slow(f"  🕸 Slow — +1 AP! ({p.statuses.get('slow',0)} left)")

        if p.combat_flags.get("plan_ap_discount_active", 0):
            discount = p.combat_flags.pop("plan_ap_discount_active")
            cost -= discount
            print_slow(f"  📜 Plan — −{discount} AP on this command!")
        return max(1, cost)

    def _dispatch(self, command, raw, ctx):
        p = self.player
        action_target = None

        if command == "attack":
            action_target = self._pick_target()
            if action_target:
                self._do_attack(action_target, raw, ctx)
            return True, action_target

        if command == "heal":
            success = self._do_heal(raw, ctx)
            return success, None

        if command == "block":
            self._do_block(raw, ctx)
            return True, None

        fn, needs_target = COMMAND_EFFECTS[command]
        action_target    = self._pick_target() if needs_target else None
        success          = fn(p, self.enemies, action_target, ctx)
        return success, action_target

    def _post_action(self, command, raw, action_target, ctx):
        p = self.player
        ctx["actions_this_turn"]   += 1
        p.actions_this_combat      += 1
        ctx["actions_this_combat"]  = p.actions_this_combat

        if "echo" in p.statuses:
            p.statuses["echo"] = command

        alive = self._alive()
        relic_target = (
            (action_target if action_target and action_target.health > 0 else None)
            or (alive[0] if alive else None)
        )
        p.trigger_relics(TRIGGER_ON_ACTION, relic_target,
                         {**ctx, "raw": raw, "command": command, "previous_command": ctx.get("last_command_this_turn"), "mp_spent": ctx.pop("_last_mp_spent", 0)})

        ctx["last_command_this_turn"] = command

        if p.combat_flags.get("shielded_active") and command in _SHIELDED_DAMAGE_COMMANDS:
            self._grant_shielded_block()

        w = _win()
        if w:
            w.set_combat(p, self.room, self.enemies)

        alive = self._alive()
        if not alive:
            return _DONE

        self._show_mid_turn(alive)
        return _NEXT

    # ══════════════════════════════════════════════════════════════════════════
    #  Base actions — dice-based
    # ══════════════════════════════════════════════════════════════════════════

    def _do_attack(self, enemy, raw, ctx):
        p = self.player

        if ctx.get("discipline_no_atk"):
            print_slow("  ⚔ Discipline active — cannot attack this turn.")
            return

        guaranteed_hit = ctx.get("feint_no_miss") or p.statuses.get("aim", 0) > 0
        if is_disoriented(p) and not guaranteed_hit:
            if random.random() < 0.5:
                print_slow("  🌪 Disoriented — your attack misses!")
                return
        if p.statuses.get("aim", 0) > 0:
            p.statuses["aim"] -= 1
            if p.statuses["aim"] <= 0:
                del p.statuses["aim"]
            print_slow("  🎯 Aim — this attack cannot miss.")
        ctx["feint_no_miss"] = False

        # Dice roll
        dmg = dice_roll(BASE_ATTACK_DICE)

        # Chipped Sword +4
        if p.has_relic("Chipped Sword"):
            dmg += 4
            print_slow("  🗡 Chipped Sword — +4 damage!")

        # Giant's Belt: command > 6 letters → +25%
        if p.has_relic("Giant's Belt") and len(raw.strip()) > 6:
            dmg = int(dmg * 1.25)
            print_slow("  🏋 Giant's Belt — long command, +25% damage!")

        # Starlit Anvil: STARLIT letters → +50%
        if p.has_relic("Starlit Anvil") and set(raw.strip()) >= _STARLIT:
            dmg = int(dmg * 1.5)
            print_slow("  ⭐ Starlit Anvil — STARLIT letters, +50% damage!")

        if ctx.get("rally_bonus", 0):
            dmg += ctx.pop("rally_bonus")
            print_slow("  ⚔ Rally bonus applied!")
        if ctx.get("mark_bonus", 0):
            dmg += ctx.pop("mark_bonus")
            print_slow("  🗡 Mark bonus applied!")

        if is_volatile(p):
            dmg = int(dmg * 1.5)
            print_slow("  💥 Volatile — +50% damage!")

        rage_mult = consume_rage(p)
        if rage_mult > 1:
            print_slow("  🔥 Rage — DOUBLE DAMAGE!")
        dmg = int(dmg * rage_mult)

        vuln_mult = consume_vulnerable(enemy)
        if vuln_mult > 1:
            print_slow(f"  💢 {enemy.name} is Vulnerable — +50%!")
        dmg = int(dmg * vuln_mult)

        # Trap — stored flag
        if p.combat_flags.get("trap_set") and enemy.health > 0:
            p.combat_flags.pop("trap_set")
            dmg += 8
            print_slow("  🪤 Trap triggered — +8 damage!")

        # Mark of Death enemy flag
        if enemy.statuses.pop("mark_of_death", 0):
            dmg *= 2
            print_slow("  💀 Mark of Death — DOUBLE damage!")

        base_type = class_base_attack_type(p.char_class)
        actual, absorbed, _ = apply_typed_damage(
            attacker=p,
            target=enemy,
            dmg=dmg,
            damage_type=base_type,
            label="Strike",
            ctx=ctx,
        )
        if enemy.health <= 0:
            self._on_enemy_death(enemy, p)

        if p.combat_flags.get("shielded_active"):
            self._grant_shielded_block()

        if is_volatile(p) and random.random() < 0.5:
            p.take_damage(5)
            print_slow(f"  💥 Volatile backfires — 5 self-damage! (HP:{p.health})")

        p.trigger_relics(TRIGGER_ON_ATTACK, enemy, {"raw": raw})

    def _do_heal(self, raw, ctx):
        p = self.player
        if p.mana < HEAL_MP_COST:
            print_slow(f"  {BLUE}Not enough Mana!{RESET}")
            return False
        p.mana -= HEAL_MP_COST
        ctx["_last_mp_spent"] = HEAL_MP_COST

        base = dice_roll(BASE_HEAL_DICE)

        # Star Core: mage spells +50%
        if p.has_relic("Star Core") and p.char_class == "mage":
            base = int(base * 1.5)
            print_slow("  ⭐ Star Core — +50% heal!")

        amt = modified_heal(p, base)
        p.heal(amt)
        print_slow(f"  > Healed {amt} HP! (HP:{p.health})  {BLUE}[−{HEAL_MP_COST}MP → {p.mana}/{p.max_mana}]{RESET}")
        alive = self._alive()
        p.trigger_relics(TRIGGER_ON_HEAL, alive[0] if alive else None, {"raw": raw})
        return True

    def _do_block(self, raw, ctx):
        p = self.player
        if p.combat_flags.get("no_block_this_turn"):
            print_slow("  ⚔ You cannot gain Block for the rest of this turn.")
            return
        apply_block(p, BASE_BLOCK)
        alive = self._alive()
        p.trigger_relics(TRIGGER_ON_BLOCK, alive[0] if alive else None, {"raw": raw})

    def _on_enemy_death(self, enemy, p):
        print_slow(f"  > Defeated {enemy.name}! +{enemy.xp_reward} XP")
        p.gain_xp(enemy.xp_reward)
        p.journal.record_enemy(enemy)

        # on_death_effect
        effect = getattr(enemy, "on_death_effect", None)
        if effect == "shatter":
            from utils.status_effects import consume_block as cb
            shatter_dmg = 10
            actual, absorbed = cb(p, shatter_dmg)
            p.take_damage(actual)
            apply_weak(p, 2)
            print_slow(f"  💥 Cursed Statue SHATTERS — {shatter_dmg} damage + Weak 2! (HP:{p.health})")

        self._handle_drops(enemy)
        input("  Press Enter to continue...")

    # ══════════════════════════════════════════════════════════════════════════
    #  Display helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _show_status(self):
        if _win():
            return
        p     = self.player
        alive = self._alive()
        print(f"\n  {'─'*50}")
        for i, e in enumerate(alive, 1):
            s   = format_statuses(e)
            tag = f"  [{s}]" if s else ""
            if is_stunned(e):
                intent = "  → ⚡ STUNNED"
            elif e._planned_moves:
                intent = "  → " + " → ".join(f"{m.name}({m.ap_cost}){_intent_hint(m)}" for m in e._planned_moves)
            else:
                intent = "  → ???"
            print_slow(f"  [{i}] {e.name:<14} HP:{e.health}/{e.max_health}  AP:{e.current_ap}/{e.max_ap}{tag}{intent}")
        print(f"  {'─'*50}")
        print_status(p)
        ps = format_statuses(p)
        if ps:
            print(f"  Status: [{ps}]")
        if p.relics:
            print(f"  Relics: {', '.join(r.name for r in p.relics)}")
        known = sorted(p.known_commands)
        base_str = (
            f"attack({BASE_COMMANDS['attack']['ap_cost']}) | "
            f"{BLUE}heal({BASE_COMMANDS['heal']['ap_cost']}AP+{HEAL_MP_COST}MP){RESET} | "
            f"block({BASE_COMMANDS['block']['ap_cost']})"
        )
        if known:
            parts = [f"{c}({cmd_ap_cost(get_command_def(p.char_class,c)) if get_command_def(p.char_class,c) else len(c)})" for c in known]
            base_str += " | " + " | ".join(parts)
        print(f"\n  {base_str} | end")

    def _show_mid_turn(self, alive):
        p  = self.player
        ps = format_statuses(p)
        print_status(p)
        for e in alive:
            s = format_statuses(e)
            if s:
                print(f"  {e.name}: [{s}]")
        if ps:
            print(f"  You: [{ps}]")

    def _pick_target(self):
        alive = self._alive()
        if not alive:
            return None
        if len(alive) == 1:
            return alive[0]
        print_slow("\n  Choose target:")
        for i, e in enumerate(alive, 1):
            s = format_statuses(e)
            print(f"    [{i}] {e.name:<14} HP:{e.health}/{e.max_health}{' ['+s+']' if s else ''}")
        while True:
            raw = input(f"  Target (1-{len(alive)}): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(alive):
                return alive[int(raw)-1]
            print("  Invalid choice.")

    # ══════════════════════════════════════════════════════════════════════════
    #  Enemy turn
    # ══════════════════════════════════════════════════════════════════════════

    def _enemies_turn(self):
        input("\n  Press Enter for enemy turn...")
        print(f"\n  {'─'*50}")
        for enemy in self._alive():
            print_slow(f"  {enemy.name}'s turn")
            self._enemy_turn_start_buffs(enemy)
            if is_stunned(enemy):
                print_slow(f"  ⚡ {enemy.name} is stunned — skips turn!")
                tick_statuses(enemy)
            else:
                enemy._current_player_ref = self.player
                self._enemy_act(enemy)
                enemy._current_player_ref = None
                tick_statuses(enemy)
            if self.player.health <= 0:
                return

        if self.player.combat_flags.pop("defiant_ready", False) and get_block(self.player) > 0:
            self.player.combat_flags["evade_bonus_ap"] = self.player.combat_flags.get("evade_bonus_ap", 0) + 2
            self.player.statuses["strength"] = self.player.statuses.get("strength", 0) + 2
            print_slow("  ⚔ Defiant triggers — Block remained after enemy turn. +2 AP next turn, +2 Strength.")

        self.player.statuses.pop("evade", None)

        w = _win()
        if w:
            w.set_combat(self.player, self.room, self.enemies)
        print()

    def _enemy_turn_start_buffs(self, enemy):
        fortify = enemy.statuses.get("fortify", 0)
        if fortify:
            apply_block(enemy, fortify)
            print_slow(f"  🏰 {enemy.name} Fortify — +{fortify} Block!")
        regen = get_regen(enemy)
        if regen > 0:
            enemy.health = min(enemy.max_health, enemy.health + regen)
            print_slow(f"  🌿 {enemy.name} regenerates {regen} HP! (HP:{enemy.health})")

    def _enemy_act(self, enemy):
        p = self.player
        enemy.tick_move_cooldowns()

        burden       = enemy.statuses.get("burden", 0)
        effective_ap = max(1, enemy.max_ap - burden)
        if burden:
            print_slow(f"  ⚖️ {enemy.name} Burdened — {effective_ap}/{enemy.max_ap} AP!")

        speed = enemy.statuses.get("speed", 0)
        if speed:
            effective_ap += speed
            del enemy.statuses["speed"]
            print_slow(f"  💨 {enemy.name} Hastened — +{speed} AP! ({effective_ap} total)")

        enemy.current_ap = effective_ap

        if is_disoriented(enemy) and random.random() < 0.5:
            print_slow(f"  🌪 {enemy.name} disoriented — wastes turn!")
            enemy._planned_moves = []
            enemy._planned_move = None
            return

        if get_slow(enemy) > 0:
            enemy.statuses["slow"] -= 1
            if enemy.statuses["slow"] <= 0:
                del enemy.statuses["slow"]
            if random.random() < 0.5:
                print_slow(f"  🕸 {enemy.name} Slowed — loses turn!")
                enemy._planned_moves = []
                enemy._planned_move = None
                return
            print_slow(f"  🕸 {enemy.name} Slowed — pushes through!")

        # Trap check
        if p.combat_flags.get("trap_set"):
            p.combat_flags.pop("trap_set")
            enemy.take_damage(8)
            print_slow(f"  🪤 Trap triggers! {enemy.name} takes 8 damage! (HP:{max(enemy.health,0)})")
            if enemy.health <= 0:
                self._on_enemy_death(enemy, p)
                return

        used_ids: set = set()
        actions_taken = 0

        while enemy.current_ap > 0 and enemy.health > 0 and p.health > 0:
            evade_stacks = p.statuses.get("evade", 0)
            if evade_stacks > 0 and random.random() < 0.5:
                p.statuses["evade"] -= 1
                if p.statuses["evade"] <= 0:
                    del p.statuses["evade"]
                p.combat_flags["evade_bonus_ap"] = p.combat_flags.get("evade_bonus_ap", 0) + 2
                print_slow(f"  🗡 Evade triggers — {enemy.name} misses an action! (+2 AP next turn)")
                actions_taken += 1
                break

            chosen = enemy.choose_affordable_move(enemy.current_ap, used_ids)
            if not chosen:
                break
            print_slow(f"  [ {enemy.name} — {chosen.name} ({chosen.ap_cost}AP){_intent_hint(chosen)} ]")
            enemy.current_ap -= chosen.ap_cost
            used_ids.add(id(chosen))
            p.journal.record_move(enemy.name, chosen.name)
            chosen.use(enemy, p)
            enemy.on_move_used(chosen.name, combat_session=self, ctx={"player": p})
            self._handle_shield_self(enemy)
            self._handle_shield_allies(enemy)
            # Phalanx — block all allies
            if enemy.statuses.pop("_phalanx", 0) > 0:
                for ally in [e for e in self.enemies if e.health > 0]:
                    apply_block(ally, 4)
                    print_slow(f"  🛡 Phalanx — {ally.name} +4 Block!")
            actions_taken += 1

        if actions_taken == 0 and enemy.health > 0 and p.health > 0:
            self._enemy_basic_attack(enemy)

        p.trigger_relics(TRIGGER_ON_HIT, enemy, {"damage": 0})

    def _enemy_basic_attack(self, enemy):
        p       = self.player
        evade_stacks = p.statuses.get("evade", 0)
        if evade_stacks > 0 and random.random() < 0.5:
            p.statuses["evade"] -= 1
            if p.statuses["evade"] <= 0:
                del p.statuses["evade"]
            p.combat_flags["evade_bonus_ap"] = p.combat_flags.get("evade_bonus_ap", 0) + 2
            print_slow(f"  🗡 Evade triggers — {enemy.name} misses! (+2 AP next turn)")
            return
        raw_dmg = enemy.roll_damage()   # uses damage_dice

        soul_tax = enemy.statuses.get("soul_tax", 0)
        if soul_tax:
            raw_dmg += soul_tax
            print_slow(f"  ⚰ {enemy.name} Soul Tax surge — +{soul_tax}!")

        burden = get_burden(enemy)
        if burden > 0:
            raw_dmg = max(1, raw_dmg - burden * 2)
            print_slow(f"  ⚖️ {enemy.name} Burdened — reduced damage!")

        raw_dmg = int(raw_dmg * consume_rage(enemy))
        if is_volatile(enemy):
            raw_dmg = int(raw_dmg * 1.5)
            print_slow(f"  💥 {enemy.name} Volatile — +50%!")
            if random.random() < 0.5:
                enemy.take_damage(5)
                print_slow(f"  💥 Volatile backfires on {enemy.name}! (HP:{enemy.health})")
        raw_dmg = int(raw_dmg * consume_weak(enemy))

        from entities.enemy_moves import resolve_enemy_hit
        resolve_enemy_hit(enemy, p, raw_dmg, detail=getattr(enemy, "damage_type", "physical"))

    def _handle_shield_allies(self, enemy):
        amt = enemy.statuses.pop("_shield_allies", 0)
        if amt:
            for ally in [e for e in self.enemies if e.health > 0]:
                apply_block(ally, amt)
                print_slow(f"  🛡 {ally.name} gains {amt} Block from barrier!")

    def _handle_shield_self(self, enemy):
        amt = enemy.statuses.pop("_shield_self", 0)
        if amt:
            apply_block(enemy, amt)
            print_slow(f"  🛡 {enemy.name} gains {amt} Block.")

    def _handle_drops(self, enemy):
        p = self.player
        for item in enemy.roll_drops():
            p.inventory.append(item)
            p.journal.record_drop(enemy.name, item)
            print_slow(f"  ↳ {enemy.name} dropped: {item}")

        if enemy.guaranteed_relic:
            from utils.relics import get_relic
            from utils.ascii_art import RELIC_ART, print_art
            from utils.helpers import RARITY_COLORS, RESET as RS
            r = get_relic(enemy.guaranteed_relic)
            if r:
                p.add_relic(r)
                art = RELIC_ART.get(r.name)
                if art:
                    print_art(art, indent=10)
                color  = RARITY_COLORS.get(getattr(r,"rarity","Common"),"")
                rarity = getattr(r,"rarity","Common")
                print_slow(f"  ✦ Elite drop: {color}{r.name}{RS}  [{rarity}]")
                print_slow(f"    {r.description}")

    def _grant_shielded_block(self):
        bonus_block = dice_roll("2d4")
        apply_block(self.player, bonus_block)
        print_slow(f"  🛡 Shielded — +{bonus_block} Block from your action.")

    def _combat_end_cleanup(self, ignore_statuses=None):
        ignore = set(ignore_statuses or self.player.combat_flags.get("status_cleanup_ignore", []))
        if not ignore:
            self.player.statuses.clear()
            return
        self.player.statuses = {k: v for k, v in self.player.statuses.items() if k in ignore}


def combat_loop(player, room):
    CombatSession(player, room).run()
