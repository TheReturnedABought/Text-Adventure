# utils/combat.py
"""
CombatSession — one full fight between the player and a room's enemies.

Window integration
──────────────────
When the Tkinter window (utils/window.py) is active:
  _show_status()   -> refreshes window panels, prints nothing inline.
  _show_mid_turn() -> skips print_status() (STATUS panel handles it).
  _player_turn()   -> calls window.set_combat() after planning moves so
                      the ART panel reflects current telegraphed moves.

All attack results, status messages, and drops still go to the LOG panel
via print_slow() -> window.log().
"""
import random
from utils.helpers import print_slow, print_status, BLUE, RESET
from utils.constants import (
    MAX_AP, BASE_BLOCK,
    BASE_ATTACK_MIN, BASE_ATTACK_MAX,
    BASE_HEAL_MIN, BASE_HEAL_MAX, HEAL_MP_COST,
    BASE_COMMANDS,
)
from utils.status_effects import (
    tick_statuses, clear_block, modified_heal,
    is_stunned, is_raging, is_volatile, is_disoriented, get_echo,
    apply_block, consume_block,
    consume_weak, consume_vulnerable, consume_rage,
    format_statuses, get_block,
    get_regen, get_burden,
    get_fortify, get_speed, get_slow, get_soul_tax, get_counter,
    apply_speed, apply_slow,
)
from entities.relic import (
    TRIGGER_ON_ACTION, TRIGGER_ON_ATTACK, TRIGGER_ON_HEAL,
    TRIGGER_ON_BLOCK, TRIGGER_ON_HIT, TRIGGER_TURN_END, TRIGGER_TURN_START,
)
from entities.class_commands import COMMAND_EFFECTS
from entities.class_data import cmd_ap_cost, get_command_def
from game_engine.parser import parse_command


# Turn signals
_END  = "end"
_NEXT = "next"
_DONE = "done"


def _win():
    """Return the window singleton if active, else None."""
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
                break
            enemy_alive = self._player_turn()
            if self.player.health <= 0:
                break
            if not enemy_alive:
                continue
            self._enemies_turn()
            if self.player.health <= 0:
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

        if p.has_relic("Warden's Brand"):
            from utils.status_effects import apply_vulnerable
            for e in alive:
                apply_vulnerable(e, 1)

    def _victory(self):
        print()
        print_slow("  ✦ All enemies defeated! ✦")
        self._regen_ap()
        input("\n  Press Enter to continue...")
        p = self.player
        if p.level_ups or p.pending_command_choices or p.auto_unlocked_commands:
            from utils.display import show_levelup
            show_levelup(p)

    def _alive(self):
        return [e for e in self.enemies if e.health > 0]

    def _apply_pending_effect(self, effect, value):
        from utils.status_effects import (
            apply_rage, apply_regen, apply_block as _blk, apply_poison,
        )
        p = self.player
        dispatch = {
            "rage":   lambda: apply_rage(p, value),
            "regen":  lambda: apply_regen(p, value),
            "block":  lambda: _blk(p, value),
            "poison": lambda: apply_poison(p, value),
        }
        if effect in dispatch:
            dispatch[effect]()

    # ══════════════════════════════════════════════════════════════════════════
    #  Player turn
    # ══════════════════════════════════════════════════════════════════════════

    def _player_turn(self):
        p = self.player
        self._regen_ap()
        self._plan_enemy_moves()
        alive = self._alive()
        p.trigger_relics(TRIGGER_TURN_START, alive[0] if alive else None, {})

        # Refresh ART panel so telegraphed moves are visible before the prompt
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
        for enemy in self._alive():
            enemy.plan_turn()

    def _regen_ap(self):
        p = self.player

        burden        = p.statuses.get("burden", 0)
        effective_max = max(1, MAX_AP - burden)
        p.current_ap  = effective_max
        if burden:
            print_slow(f"  ⚖️ Burden — max AP reduced to {effective_max}/{MAX_AP}!")

        if p.combat_flags.get("evade_bonus_ap", 0):
            bonus = p.combat_flags.pop("evade_bonus_ap")
            p.current_ap = min(MAX_AP, p.current_ap + bonus)
            print_slow(f"  🗡 Evade bonus — +{bonus} AP! ({p.current_ap}/{MAX_AP})")

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
                label = f" (echo {i+1}/2)" if repeats > 1 else ""
                print_slow(f"  🔊 Echo — '{echo_cmd}' repeats{label}!")
                if echo_cmd == "attack":
                    self._do_attack(self._alive()[0], echo_cmd, ctx)
                elif echo_cmd == "heal":
                    self._do_heal(echo_cmd, ctx)
                elif echo_cmd == "block":
                    self._do_block(echo_cmd, ctx)

        first = self._alive()[0] if self._alive() else None
        p.trigger_relics(TRIGGER_TURN_END, first, {})

        if p.combat_flags.get("ward_turns_remaining", 0) > 0:
            p.combat_flags["ward_turns_remaining"] -= 1
            if p.combat_flags["ward_turns_remaining"] == 0:
                del p.combat_flags["ward_turns_remaining"]
                print_slow(f"  {BLUE}✦ Coalesce fades.{RESET}")

        for e in self._alive():
            tick_statuses(e)
        tick_statuses(p)

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

        p.current_ap -= ap_cost
        ctx["ap_spent_this_turn"] += ap_cost

        soul_tax = get_soul_tax(p)
        if soul_tax and ap_cost > 0:
            dmg = soul_tax * ap_cost
            p.take_damage(dmg)
            print_slow(
                f"  ⚰ Soul Tax — {soul_tax} × {ap_cost} AP = {dmg} damage! "
                f"(HP: {p.health})"
            )

        success, action_target = self._dispatch(command, raw, ctx)
        if not success:
            p.current_ap += ap_cost
            ctx["ap_spent_this_turn"] -= ap_cost
            return _NEXT

        result = self._post_action(command, raw, action_target, ctx)
        if result == _DONE:
            return _DONE

        if p.current_ap == 0:
            print_slow("  No AP remaining.")
            confirm = input(
                "  Press Enter to end your turn, or type a command: "
            ).lower().strip()
            if not confirm or confirm in ["yes", "y", "end", "done", "pass"]:
                print_slow("  You end your turn.")
                return _END
        return _NEXT

    def _handle_meta(self, command):
        p = self.player
        if command in ["end", "done", "pass"]:
            return True
        if command in ["move", "go", "north", "south", "east", "west",
                       "flee", "run", "escape"]:
            print_slow("  You cannot flee from combat!")
            return True
        if command in ["inventory", "inv", "i"]:
            from utils.actions import do_inventory
            do_inventory(p)
            return True
        if command in ["relics", "relic"]:
            from utils.display import show_relics
            show_relics(p)
            return True
        if command in ["look", "l"]:
            names = ", ".join(e.name for e in self._alive())
            print_slow(f"  You are fighting: {names}.")
            return True
        if command in ["help", "?"]:
            from utils.display import show_help
            show_help(p)
            input("  Press Enter to continue...")
            return True
        if command in ["journal", "j"]:
            from utils.display import show_journal
            show_journal(p)
            return True
        return False

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

        if command in BASE_COMMANDS:
            cost = BASE_COMMANDS[command]["ap_cost"]
        else:
            cmd_def = get_command_def(p.char_class, command)
            cost    = cmd_ap_cost(cmd_def) if cmd_def else len(command)

        discounted = [False] * len(command)

        if p.has_relic("Sleightmaker's Glove"):
            free_letters = {"l"}
            if p.has_relic("Silent Lamb Wool"):
                free_letters |= set("aeiou")
                print_slow("  🐑 Silent Lamb Wool — vowels count as 'l'!")
            discount = self._claim_letters(command, free_letters, discounted)
            if discount:
                cost -= discount
                print_slow(f"  🧤 Sleightmaker's Glove — {discount}× free letter(s)!")

        if p.has_relic("Bear Skin"):
            discount = self._claim_letters(command, {"a"}, discounted, cap=2)
            if discount:
                cost -= discount
                print_slow(f"  🐻 Bear Skin — {discount}× 'a' discount!")

        if get_speed(p) > 0:
            cost -= 1
            p.statuses["speed"] -= 1
            if p.statuses["speed"] <= 0:
                del p.statuses["speed"]
                print_slow("  💨 Speed fades.")
            else:
                print_slow(f"  💨 Speed — −1 AP! ({p.statuses.get('speed', 0)} left)")

        if get_slow(p) > 0:
            cost += 1
            p.statuses["slow"] -= 1
            if p.statuses["slow"] <= 0:
                del p.statuses["slow"]
                print_slow("  🕸 Slow fades.")
            else:
                print_slow(f"  🕸 Slow — +1 AP! ({p.statuses.get('slow', 0)} left)")

        return max(1, cost)

    def _dispatch(self, command, raw, ctx):
        p             = self.player
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
                         {"raw": raw, "command": command})

        # Refresh ART panel after the action (HP/AP changes)
        w = _win()
        if w:
            w.set_combat(p, self.room, self.enemies)

        alive = self._alive()
        if not alive:
            return _DONE

        self._show_mid_turn(alive)
        return _NEXT

    # ══════════════════════════════════════════════════════════════════════════
    #  Base actions
    # ══════════════════════════════════════════════════════════════════════════

    def _do_attack(self, enemy, raw, ctx):
        p = self.player

        if ctx.get("discipline_no_atk"):
            print_slow("  ⚔ Discipline active — you cannot attack this turn.")
            return

        if is_disoriented(p) and not ctx.get("feint_no_miss"):
            if random.random() < 0.5:
                print_slow("  🌪 Disoriented — your attack misses!")
                return
        ctx["feint_no_miss"] = False

        dmg = random.randint(BASE_ATTACK_MIN, BASE_ATTACK_MAX)

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
            print_slow(f"  💢 {enemy.name} is Vulnerable — +50% damage!")
        dmg = int(dmg * vuln_mult)

        actual, absorbed = consume_block(enemy, dmg)
        enemy.take_damage(actual)
        if absorbed:
            print_slow(
                f"  > You strike {enemy.name} for {dmg} — "
                f"🛡 blocked {absorbed}, dealing {actual}! "
                f"(HP: {max(enemy.health, 0)})"
            )
        else:
            print_slow(f"  > You strike {enemy.name} for {dmg}! (HP: {max(enemy.health, 0)})")

        if enemy.health <= 0:
            print_slow(f"  > You defeated {enemy.name}! +{enemy.xp_reward} XP")
            p.gain_xp(enemy.xp_reward)
            p.journal.record_enemy(enemy)
            self._handle_drops(enemy)
            input("  Press Enter to continue...")

        if is_volatile(p) and random.random() < 0.5:
            p.take_damage(5)
            print_slow(f"  💥 Volatile backfires — 5 self-damage! (HP: {p.health})")

        p.trigger_relics(TRIGGER_ON_ATTACK, enemy, {"raw": raw})

    def _do_heal(self, raw, ctx):
        p = self.player
        if p.mana < HEAL_MP_COST:
            print_slow(f"  {BLUE}Not enough Mana to heal!{RESET}")
            return False
        p.mana -= HEAL_MP_COST
        base = random.randint(BASE_HEAL_MIN, BASE_HEAL_MAX)
        amt  = modified_heal(p, base)
        p.heal(amt)
        print_slow(
            f"  > Healed {amt} HP! (HP: {p.health})  "
            f"{BLUE}[-{HEAL_MP_COST} MP → {p.mana}/{p.max_mana}]{RESET}"
        )
        alive = self._alive()
        p.trigger_relics(TRIGGER_ON_HEAL, alive[0] if alive else None, {"raw": raw})
        return True

    def _do_block(self, raw, ctx):
        p = self.player
        apply_block(p, BASE_BLOCK)
        alive = self._alive()
        p.trigger_relics(TRIGGER_ON_BLOCK, alive[0] if alive else None, {"raw": raw})

    # ══════════════════════════════════════════════════════════════════════════
    #  Display helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _show_status(self):
        """
        Classic inline HUD.
        When the window is active, the ART + STATUS panels already show
        this information, so we skip the inline print entirely.
        """
        if _win():
            return   # panels handle it

        p     = self.player
        alive = self._alive()
        print(f"\n  {'─' * 50}")
        for i, e in enumerate(alive, 1):
            s      = format_statuses(e)
            tag    = f"  [{s}]" if s else ""
            if is_stunned(e):
                intent = "  → ⚡ STUNNED"
            elif e._planned_moves:
                seq    = " → ".join(
                    f"{m.name}({m.ap_cost})" for m in e._planned_moves
                )
                intent = f"  → {seq}"
            else:
                intent = "  → ???"
            print_slow(
                f"  [{i}] {e.name:<14} HP: {e.health}/{e.max_health}"
                f"  AP:{e.current_ap}/{e.max_ap}{tag}{intent}"
            )
        print(f"  {'─' * 50}")
        print_status(p)
        ps = format_statuses(p)
        if ps:
            print(f"  Status: [{ps}]")
        if p.relics:
            print(f"  Relics: {', '.join(r.name for r in p.relics)}")
        known    = sorted(p.known_commands)
        base_str = (
            f"attack({BASE_COMMANDS['attack']['ap_cost']}) | "
            f"{BLUE}heal({BASE_COMMANDS['heal']['ap_cost']}AP"
            f"+{HEAL_MP_COST}MP){RESET} | "
            f"block({BASE_COMMANDS['block']['ap_cost']})"
        )
        extra = ""
        if known:
            parts = []
            for c in known:
                d  = get_command_def(p.char_class, c)
                ap = cmd_ap_cost(d) if d else len(c)
                parts.append(f"{c}({ap})")
            extra = " | " + " | ".join(parts)
        print(f"\n  {base_str}{extra} | end")

    def _show_mid_turn(self, alive):
        """
        Brief status update between actions.
        print_status() is suppressed by helpers.py when window is active.
        """
        p  = self.player
        ps = format_statuses(p)
        print_status(p)   # no-op when window active
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
            s   = format_statuses(e)
            tag = f"  [{s}]" if s else ""
            print(f"    [{i}] {e.name:<14} HP: {e.health}/{e.max_health}{tag}")
        while True:
            raw = input(f"  Target (1-{len(alive)}): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(alive):
                return alive[int(raw) - 1]
            print("  Invalid choice.")

    # ══════════════════════════════════════════════════════════════════════════
    #  Enemy turn
    # ══════════════════════════════════════════════════════════════════════════

    def _enemies_turn(self):
        input("\n  Press Enter for enemy turn...")
        print(f"\n  {'─' * 50}")
        for enemy in self._alive():
            print_slow(f"  {enemy.name}'s turn")
            self._enemy_turn_start_buffs(enemy)
            if is_stunned(enemy):
                print_slow(f"  ⚡ {enemy.name} is stunned — loses their turn!")
                tick_statuses(enemy)
            else:
                self._enemy_act(enemy)
                tick_statuses(enemy)
            if self.player.health <= 0:
                return

        # Refresh ART after all enemies acted
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
            print_slow(f"  🌿 {enemy.name} regenerates {regen} HP! (HP: {enemy.health})")

    def _enemy_act(self, enemy):
        p = self.player
        enemy.tick_move_cooldowns()

        burden       = enemy.statuses.get("burden", 0)
        effective_ap = max(1, enemy.max_ap - burden)
        if burden:
            print_slow(
                f"  ⚖️ {enemy.name} is Burdened — "
                f"{effective_ap}/{enemy.max_ap} AP!"
            )

        speed = enemy.statuses.get("speed", 0)
        if speed:
            effective_ap += speed
            del enemy.statuses["speed"]
            print_slow(
                f"  💨 {enemy.name} is Hastened — "
                f"+{speed} AP! ({effective_ap} total)"
            )

        enemy.current_ap = effective_ap

        # Turn-level interrupts
        if p.combat_flags.get("evade"):
            p.combat_flags.pop("evade")
            p.combat_flags["evade_bonus_ap"] = 2
            print_slow(f"  🗡 Evade — you dodge {enemy.name}'s attack!")
            enemy._planned_moves = []
            enemy._planned_move  = None
            return

        if is_disoriented(enemy) and random.random() < 0.5:
            print_slow(
                f"  🌪 {enemy.name} is disoriented — "
                "stumbles and wastes their turn!"
            )
            enemy._planned_moves = []
            enemy._planned_move  = None
            return

        if get_slow(enemy) > 0:
            enemy.statuses["slow"] -= 1
            if enemy.statuses["slow"] <= 0:
                del enemy.statuses["slow"]
            if random.random() < 0.5:
                print_slow(f"  🕸 {enemy.name} is Slowed — loses their turn!")
                enemy._planned_moves = []
                enemy._planned_move  = None
                return
            print_slow(f"  🕸 {enemy.name} is Slowed — pushes through!")

        used_ids: set = set()
        actions_taken = 0

        while enemy.current_ap > 0 and enemy.health > 0 and p.health > 0:
            chosen = enemy.choose_affordable_move(enemy.current_ap, used_ids)
            if not chosen:
                break
            print_slow(
                f"  [ {enemy.name} uses {chosen.name} ({chosen.ap_cost} AP) ]"
            )
            enemy.current_ap -= chosen.ap_cost
            used_ids.add(id(chosen))
            p.journal.record_move(enemy.name, chosen.name)
            chosen.use(enemy, p)
            self._handle_shield_allies(enemy)
            actions_taken += 1

        if actions_taken == 0 and enemy.health > 0 and p.health > 0:
            self._enemy_basic_attack(enemy)

        p.trigger_relics(TRIGGER_ON_HIT, enemy, {"damage": 0})

    def _enemy_basic_attack(self, enemy):
        p       = self.player
        raw_dmg = random.randint(4, enemy.attack_power)

        soul_tax = enemy.statuses.get("soul_tax", 0)
        if soul_tax:
            raw_dmg += soul_tax
            print_slow(
                f"  ⚰ {enemy.name}'s cursed power surges — "
                f"+{soul_tax} bonus damage!"
            )

        burden = get_burden(enemy)
        if burden > 0:
            raw_dmg = max(1, raw_dmg - burden * 2)
            print_slow(f"  ⚖️ {enemy.name} is Burdened — reduced damage!")

        raw_dmg = int(raw_dmg * consume_rage(enemy))
        if is_volatile(enemy):
            raw_dmg = int(raw_dmg * 1.5)
            print_slow(f"  💥 {enemy.name} is Volatile — +50% damage!")
            if random.random() < 0.5:
                enemy.take_damage(5)
                print_slow(
                    f"  💥 Volatile backfires on {enemy.name}! "
                    f"(HP: {enemy.health})"
                )
        raw_dmg = int(raw_dmg * consume_weak(enemy))

        actual, absorbed = consume_block(p, raw_dmg)
        if p.combat_flags.get("unbreakable"):
            from utils.constants import UNBREAKABLE_CAP
            actual = min(actual, UNBREAKABLE_CAP)

        if absorbed:
            print_slow(
                f"  {enemy.name} hits for {raw_dmg} — "
                f"🛡 blocked {absorbed}, taking {actual}!"
            )
        else:
            print_slow(f"  {enemy.name} hits you for {raw_dmg}!")

        if absorbed > 0 and actual > 0:
            counter = get_counter(p)
            if counter:
                enemy.take_damage(counter)
                print_slow(
                    f"  🔄 Counter — block shattered! "
                    f"{enemy.name} takes {counter} damage! "
                    f"(HP: {max(enemy.health, 0)})"
                )
                del p.statuses["counter"]

        if actual > 0:
            p.take_damage(actual)
            print_slow(f"  Your HP: {p.health}")

        sentinel = p.combat_flags.get("sentinel_thorns", 0)
        if sentinel and actual > 0:
            enemy.take_damage(sentinel)
            print_slow(
                f"  🛡 Sentinel — {enemy.name} takes {sentinel} thorns! "
                f"(HP: {max(enemy.health, 0)})"
            )

    def _handle_shield_allies(self, enemy):
        shield_amt = enemy.statuses.pop("_shield_allies", 0)
        if shield_amt:
            for ally in [e for e in self.enemies if e.health > 0]:
                apply_block(ally, shield_amt)
                print_slow(
                    f"  🛡 {ally.name} gains {shield_amt} Block from the barrier!"
                )

    def _handle_drops(self, enemy):
        p = self.player
        for item in enemy.roll_drops():
            p.inventory.append(item)
            p.journal.record_drop(enemy.name, item)
            print_slow(f"  ↳ {enemy.name} dropped: {item}")

        if enemy.guaranteed_relic:
            from utils.relics import get_relic
            from utils.ascii_art import RELIC_ART, print_art
            from utils.helpers import RARITY_COLORS, RESET as _RST
            r = get_relic(enemy.guaranteed_relic)
            if r:
                p.add_relic(r)
                art = RELIC_ART.get(r.name)
                if art:
                    print_art(art, indent=10)
                color  = RARITY_COLORS.get(getattr(r, "rarity", "Common"), "")
                rarity = getattr(r, "rarity", "Common")
                print_slow(f"  ✦ Elite drop: {color}{r.name}{_RST}  [{rarity}]")
                print_slow(f"    {r.description}")


# ── Convenience wrapper ───────────────────────────────────────────────────────

def combat_loop(player, room):
    CombatSession(player, room).run()