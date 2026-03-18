# utils/combat.py
"""
CombatSession — encapsulates one full fight between the player and a room's enemies.

Usage:
    session = CombatSession(player, room)
    session.run()        # blocks until combat ends

Everything that was a module-level function is now a private method.
The only public surface is run().
"""
import random
from utils.helpers import print_slow, print_status, BLUE, RESET
from utils.constants import MAX_AP
from utils.status_effects import (
    tick_statuses, clear_block,
    is_stunned, is_raging, is_volatile, is_disoriented, get_echo,
    apply_block, consume_block,
    consume_weak, consume_vulnerable, consume_rage,
    format_statuses, get_block,
    get_burden, get_regen, apply_regen,
)
from entities.relic import (
    TRIGGER_ON_ACTION, TRIGGER_ON_ATTACK, TRIGGER_ON_HEAL,
    TRIGGER_ON_BLOCK, TRIGGER_ON_HIT, TRIGGER_TURN_END, TRIGGER_TURN_START,
)
from entities.class_commands import COMMAND_EFFECTS
from game_engine.parser import parse_command


BASE_BLOCK = 7


class CombatSession:
    """Runs one full combat encounter between `player` and all enemies in `room`."""

    def __init__(self, player, room):
        self.player  = player
        self.room    = room
        self.enemies = room.enemies[:4]   # hard cap of 4

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self):
        self.player.reset_combat_state()
        alive = self._alive()
        for relic in self.player.relics:
            if alive:
                relic.on_combat_start(self.player, alive[0])

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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _alive(self):
        return [e for e in self.enemies if e.health > 0]

    def _victory(self):
        print()
        print_slow("  ✦ All enemies defeated! ✦")
        self._regen_ap()
        input("\n  Press Enter to continue...")
        if (self.player.level_ups or self.player.pending_command_choices
                or self.player.auto_unlocked_commands):
            from utils.display import show_levelup
            show_levelup(self.player)

    # ── AP / block management ─────────────────────────────────────────────────

    def _regen_ap(self):
        p = self.player
        p.current_ap = MAX_AP
        if p.combat_flags.get("evade_bonus_ap", 0):
            bonus = p.combat_flags.pop("evade_bonus_ap")
            p.current_ap = min(MAX_AP, p.current_ap + bonus)
            print_slow(f"  🗡 Evade bonus — +{bonus} AP this turn! ({p.current_ap}/{MAX_AP})")
        if not p.combat_flags.get("persistent_block"):
            clear_block(p)
        # Regen — heal at start of turn
        regen = get_regen(p)
        if regen > 0:
            p.heal(regen)
            print_slow(f"  🌿 Regen — +{regen} HP! (HP: {p.health})")

    # ── Target selection ──────────────────────────────────────────────────────

    def _pick_target(self):
        alive = self._alive()
        if not alive:
            return None
        if len(alive) == 1:
            return alive[0]
        print_slow("\n  Choose target:")
        for i, e in enumerate(alive, 1):
            s = format_statuses(e)
            tag = f"  [{s}]" if s else ""
            print(f"    [{i}] {e.name:<14} HP: {e.health}/{e.max_health}{tag}")
        while True:
            raw = input(f"  Target (1-{len(alive)}): ").strip()
            if raw.isdigit() and 1 <= int(raw) <= len(alive):
                return alive[int(raw) - 1]
            print("  Invalid choice.")

    # ── Status display ────────────────────────────────────────────────────────

    def _show_status(self):
        alive = self._alive()
        p = self.player
        print(f"\n  {'─' * 50}")
        for i, e in enumerate(alive, 1):
            s = format_statuses(e)
            tag = f"  [{s}]" if s else ""
            print_slow(f"  [{i}] {e.name:<14} HP: {e.health}/{e.max_health}{tag}")
        print(f"  {'─' * 50}")
        print_status(p)
        ps = format_statuses(p)
        if ps:
            print(f"  Status: [{ps}]")
        if p.relics:
            print(f"  Relics: {', '.join(r.name for r in p.relics)}")
        known = sorted(p.known_commands)
        base  = f"attack(6) | {BLUE}heal(4AP+1MP){RESET} | block(5)"
        extra = (" | " + " | ".join(f"{c}({len(c)})" for c in known)) if known else ""
        print(f"\n  {base}{extra} | end")

    # ── Base actions ──────────────────────────────────────────────────────────

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

        dmg = random.randint(8, 18)

        if ctx.get("rally_bonus", 0):
            dmg += ctx.pop("rally_bonus")
            print_slow(f"  ⚔ Rally bonus applied!")
        if ctx.get("mark_bonus", 0):
            dmg += ctx.pop("mark_bonus")
            print_slow(f"  🗡 Mark bonus applied!")
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
            print_slow(f"  > You strike {enemy.name} for {dmg} — 🛡 blocked {absorbed}, dealing {actual}! (HP: {max(enemy.health,0)})")
        else:
            print_slow(f"  > You strike {enemy.name} for {dmg}! (HP: {max(enemy.health,0)})")

        if enemy.health <= 0:
            print_slow(f"  > You defeated {enemy.name}! +{enemy.xp_reward} XP")
            p.gain_xp(enemy.xp_reward)
            input("  Press Enter to continue...")

        if is_volatile(p) and random.random() < 0.5:
            p.take_damage(5)
            print_slow(f"  💥 Volatile backfires — 5 self-damage! (HP: {p.health})")

        p.trigger_relics(TRIGGER_ON_ATTACK, enemy, {"raw": raw})

    def _do_heal(self, raw, ctx):
        p = self.player
        if p.mana < 1:
            print_slow(f"  {BLUE}Not enough Mana to heal!{RESET}")
            return False
        p.mana -= 1
        amt = random.randint(8, 15)
        p.heal(amt)
        print_slow(f"  > Healed {amt} HP! (HP: {p.health})  {BLUE}[-1 MP → {p.mana}/{p.max_mana}]{RESET}")
        alive = self._alive()
        first = alive[0] if alive else None
        p.trigger_relics(TRIGGER_ON_HEAL, first, {"raw": raw})
        return True

    def _do_block(self, raw, ctx):
        apply_block(self.player, BASE_BLOCK)
        alive = self._alive()
        first = alive[0] if alive else None
        self.player.trigger_relics(TRIGGER_ON_BLOCK, first, {"raw": raw})

    # ── Turn-end resolution ───────────────────────────────────────────────────

    def _resolve_turn_end(self, ctx):
        p = self.player
        alive = self._alive()

        if p.combat_flags.get("fortify"):
            apply_block(p, 5)
            print_slow("  🛡 Fortify — +5 Block at turn end!")

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
        for e in self._alive():
            tick_statuses(e)
        tick_statuses(p)

    # ── Player turn ───────────────────────────────────────────────────────────

    def _player_turn(self):
        """Run the player's turn. Returns True if combat should continue."""
        p = self.player
        self._regen_ap()
        alive = self._alive()
        p.trigger_relics(TRIGGER_TURN_START, alive[0] if alive else None, {})
        self._show_status()

        ctx = {
            "actions_this_turn":   0,
            "actions_this_combat": p.actions_this_combat,
            "ward_active":         False,
            "flow_active":         False,
            "flow_used":           set(),
            "feint_no_miss":       False,
            "mark_bonus":          0,
            "rally_bonus":         p.combat_flags.pop("rally_bonus_pending", 0),
            "discipline_no_atk":   False,
            "charm_cooldown":      p.combat_flags.pop("charm_cooldown", False),
            "glove_ap_given":      False,
        }

        while True:
            alive = self._alive()
            if not alive:
                return False

            raw = input("\n⚔ > ").lower().strip()
            if not raw:
                continue
            command, _ = parse_command(raw)

            # ── Free / meta commands ──────────────────────────────────────────
            if command in ["end", "done", "pass"]:
                print_slow("  You end your turn.")
                self._resolve_turn_end(ctx)
                return bool(self._alive())

            if command in ["move", "go", "north", "south", "east", "west",
                           "flee", "run", "escape"]:
                print_slow("  You cannot flee from combat!")
                continue

            if command in ["inventory", "inv", "i"]:
                from utils.actions import do_inventory
                do_inventory(p)
                continue

            if command in ["relics", "relic"]:
                from utils.display import show_relics
                show_relics(p)
                continue

            if command in ["look", "l"]:
                names = ", ".join(e.name for e in alive)
                print_slow(f"  You are fighting: {names}.")
                continue

            if command in ["help", "?"]:
                from utils.display import show_help
                show_help(p)
                input("  Press Enter to continue...")
                continue

            # ── Validate command ──────────────────────────────────────────────
            is_base  = command in ["attack", "heal", "block"]
            is_class = command in p.known_commands and command in COMMAND_EFFECTS
            if not is_base and not is_class:
                print_slow(f"  Unknown command '{command}'. Type 'help' for options.")
                continue

            if ctx["flow_active"] and command in ctx["flow_used"]:
                print_slow(f"  🗡 Flow — cannot repeat '{command}' this turn!")
                continue

            # ── AP cost ───────────────────────────────────────────────────────
            ap_cost = len(command)
            if ctx["flow_active"]:
                ap_cost = max(1, ap_cost - 1)
            if ap_cost <= 4 and p.has_relic("Sleightmaker's Glove"):
                ap_cost = max(1, ap_cost - 1)
                print_slow(f"  🧤 Sleightmaker's Glove — '{command}' costs {ap_cost} AP!")
            burden = get_burden(p)
            if burden > 0:
                ap_cost += burden
                print_slow(f"  ⚖️ Burdened — +{burden} AP cost! ({ap_cost} total)")

            if p.current_ap < ap_cost:
                print_slow(f"  Not enough AP! '{command}' costs {ap_cost}, you have {p.current_ap}.")
                print_slow("  Type 'end' to end your turn.")
                continue

            p.current_ap -= ap_cost

            # ── Execute ───────────────────────────────────────────────────────
            success      = True
            action_target = None

            if command == "attack":
                action_target = self._pick_target()
                if action_target:
                    self._do_attack(action_target, raw, ctx)

            elif command == "heal":
                success = self._do_heal(raw, ctx)
                if not success:
                    p.current_ap += ap_cost
                    continue

            elif command == "block":
                self._do_block(raw, ctx)

            else:
                fn, needs_target = COMMAND_EFFECTS[command]
                action_target = self._pick_target() if needs_target else None
                success = fn(p, self.enemies, action_target, ctx)
                if not success:
                    p.current_ap += ap_cost
                    continue

            if not success:
                continue

            # ── Post-action bookkeeping ───────────────────────────────────────
            ctx["actions_this_turn"]   += 1
            p.actions_this_combat      += 1
            ctx["actions_this_combat"]  = p.actions_this_combat
            if ctx["flow_active"]:
                ctx["flow_used"].add(command)
            if "echo" in p.statuses:
                p.statuses["echo"] = command

            # ON_ACTION relic trigger — use actual target, never bleed onto others
            alive = self._alive()
            if action_target is not None:
                relic_target = action_target if action_target.health > 0 else None
            else:
                relic_target = alive[0] if alive else None
            p.trigger_relics(TRIGGER_ON_ACTION, relic_target, {"raw": raw, "command": command})

            alive = self._alive()
            if not alive:
                return False

            # Show updated state
            ps = format_statuses(p)
            print_status(p)
            for e in alive:
                s = format_statuses(e)
                if s:
                    print(f"  {e.name}: [{s}]")
            if ps:
                print(f"  You: [{ps}]")

            # AP-out confirmation
            if p.current_ap == 0:
                print_slow("  No AP remaining.")
                confirm = input("  Press Enter to end your turn, or type a command: ").lower().strip()
                if not confirm or confirm in ["yes", "y", "end", "done", "pass"]:
                    print_slow("  You end your turn.")
                    self._resolve_turn_end(ctx)
                    return bool(self._alive())
                continue

    # ── Enemies' turn ─────────────────────────────────────────────────────────

    def _enemies_turn(self):
        input("\n  Press Enter for enemy turn...")
        print(f"\n  {'─' * 50}")
        for enemy in self._alive():
            print_slow(f"  {enemy.name}'s turn")
            # Regen ticks at the start of the enemy's turn
            regen = get_regen(enemy)
            if regen > 0:
                enemy.health = min(enemy.max_health, enemy.health + regen)
                print_slow(f"  🌿 {enemy.name} regenerates {regen} HP! (HP: {enemy.health})")
            if is_stunned(enemy):
                print_slow(f"  ⚡ {enemy.name} is stunned — loses their turn!")
                tick_statuses(enemy)
            else:
                self._enemy_act(enemy)
                tick_statuses(enemy)
            if self.player.health <= 0:
                return
        print()

    def _enemy_act(self, enemy):
        p = self.player
        enemy.tick_move_cooldowns()

        if p.combat_flags.get("evade"):
            p.combat_flags.pop("evade")
            p.combat_flags["evade_bonus_ap"] = 2
            print_slow(f"  🗡 Evade triggered — you dodge {enemy.name}'s attack!")
            return

        if is_disoriented(enemy) and random.random() < 0.5:
            print_slow(f"  🌪 {enemy.name} is disoriented — attack misses!")
            return

        chosen = enemy.choose_move()
        if chosen:
            print_slow(f"  [ {enemy.name} uses {chosen.name} ]")
            chosen.use(enemy, p)
        else:
            self._enemy_basic_attack(enemy)

        p.trigger_relics(TRIGGER_ON_HIT, enemy, {"damage": 0})

    def _enemy_basic_attack(self, enemy):
        p = self.player
        raw_dmg = random.randint(4, enemy.attack_power)

        # Burden — reduce damage per stack (min 1)
        burden = get_burden(enemy)
        if burden > 0:
            reduction = burden * 2
            raw_dmg = max(1, raw_dmg - reduction)
            print_slow(f"  ⚖️ {enemy.name} is Burdened — -{reduction} damage!")

        rage_mult = consume_rage(enemy)
        if rage_mult > 1:
            print_slow(f"  🔥 {enemy.name} is enraged — DOUBLE DAMAGE!")
        raw_dmg = int(raw_dmg * rage_mult)

        if is_volatile(enemy):
            raw_dmg = int(raw_dmg * 1.5)
            print_slow(f"  💥 {enemy.name} is Volatile — +50% damage!")
            if random.random() < 0.5:
                enemy.take_damage(5)
                print_slow(f"  💥 Volatile backfires on {enemy.name}! (HP: {enemy.health})")

        weak_mult = consume_weak(enemy)
        if weak_mult < 1:
            print_slow(f"  🌀 {enemy.name} is Weakened!")
        raw_dmg = int(raw_dmg * weak_mult)

        actual, absorbed = consume_block(p, raw_dmg)
        if p.combat_flags.get("unbreakable"):
            actual = min(actual, 6)

        if absorbed:
            print_slow(f"  {enemy.name} hits for {raw_dmg} — 🛡 blocked {absorbed}, taking {actual}!")
        else:
            print_slow(f"  {enemy.name} hits you for {raw_dmg}!")

        # Guard counter
        if absorbed and actual > 0 and p.combat_flags.get("guard_counter", 0):
            thorns = p.combat_flags.pop("guard_counter")
            enemy.take_damage(thorns)
            print_slow(f"  🛡 Guard counter — {enemy.name} takes {thorns} damage! (HP: {max(enemy.health,0)})")

        if actual > 0:
            p.take_damage(actual)
            print_slow(f"  Your HP: {p.health}")

        # Sentinel thorns
        if p.combat_flags.get("sentinel_thorns", 0) and actual > 0:
            thorns = p.combat_flags["sentinel_thorns"]
            enemy.take_damage(thorns)
            print_slow(f"  🛡 Sentinel — {enemy.name} takes {thorns} thorns! (HP: {max(enemy.health,0)})")


# ── Convenience wrapper (keeps call sites clean) ──────────────────────────────

def combat_loop(player, room):
    CombatSession(player, room).run()