# utils/combat.py
import random
from utils.helpers import print_slow, print_status, BLUE, RESET
from utils.actions import get_alive_enemies, spend_ap
from utils.constants import MAX_AP
from utils.status_effects import (
    tick_statuses, clear_block,
    is_stunned, is_raging, is_volatile, is_disoriented, get_echo,
    apply_block, consume_block,
    consume_weak, consume_vulnerable, consume_rage,
    format_statuses, get_block,
)
from entities.relic import (
    TRIGGER_ON_ACTION, TRIGGER_ON_ATTACK, TRIGGER_ON_HEAL,
    TRIGGER_ON_BLOCK, TRIGGER_ON_HIT, TRIGGER_TURN_END, TRIGGER_TURN_START,
)
from game_engine.parser import parse_command


COMBAT_COMMANDS = ["attack", "heal", "block"]
BASE_BLOCK       = 7   # block adds 7 stacks per use (modified by Iron Will)


# ── Combat actions ────────────────────────────────────────────────────────────

def do_attack(player, enemy, raw="attack"):
    import random

    # Disorient — 50% miss chance
    if is_disoriented(player):
        if random.random() < 0.5:
            print_slow(f"  🌪 Disoriented — your attack misses!")
            return

    dmg = random.randint(8, 18)

    # Volatile — +50% damage dealt
    if is_volatile(player):
        dmg = int(dmg * 1.5)
        print_slow(f"  💥 Volatile — +50% damage!")

    rage_mult = consume_rage(player)
    if rage_mult > 1:
        print_slow(f"  🔥 Rage — DOUBLE DAMAGE!")
    dmg = int(dmg * rage_mult)

    vuln_mult = consume_vulnerable(enemy)
    if vuln_mult > 1:
        print_slow(f"  💢 {enemy.name} is Vulnerable — +50% damage!")
    dmg = int(dmg * vuln_mult)

    enemy.take_damage(dmg)
    print_slow(f"  > You strike {enemy.name} for {dmg} damage! (Enemy HP: {max(enemy.health, 0)})")
    if enemy.health <= 0:
        print_slow(f"  > You defeated {enemy.name}! +{enemy.xp_reward} XP")
        player.gain_xp(enemy.xp_reward)

    # Volatile — 50% chance of 5 self-damage per action
    if is_volatile(player):
        if random.random() < 0.5:
            player.take_damage(5)
            print_slow(f"  💥 Volatile backfires — 5 self-damage! (HP: {player.health})")

    player.trigger_relics(TRIGGER_ON_ATTACK, enemy, {"raw": raw})
    player.trigger_relics(TRIGGER_ON_ACTION, enemy, {"raw": raw, "command": "attack"})


def do_heal(player, enemy, raw="heal"):
    if player.mana < 1:
        print_slow(f"  {BLUE}Not enough Mana to heal! (0/{player.max_mana}){RESET}")
        return False   # signal: action failed, AP already spent — caller handles refund
    player.mana -= 1
    heal_amt = random.randint(8, 15)
    player.heal(heal_amt)
    print_slow(f"  > You heal for {heal_amt} HP! (Your HP: {player.health})  {BLUE}[-1 MP → {player.mana}/{player.max_mana}]{RESET}")
    player.trigger_relics(TRIGGER_ON_HEAL,   enemy, {"raw": raw})
    player.trigger_relics(TRIGGER_ON_ACTION, enemy, {"raw": raw, "command": "heal"})
    return True

def do_block(player, enemy, raw="block"):
    apply_block(player, BASE_BLOCK)
    player.trigger_relics(TRIGGER_ON_BLOCK,  enemy, {"raw": raw})
    player.trigger_relics(TRIGGER_ON_ACTION, enemy, {"raw": raw, "command": "block"})


def enemy_counter(player, enemy):
    # Tick cooldowns so moves become available again
    enemy.tick_move_cooldowns()

    # Disorient — 50% miss chance for enemy
    if is_disoriented(enemy):
        if random.random() < 0.5:
            print_slow(f"  🌪 {enemy.name} is disoriented — attack misses!")
            return

    # Choose a move from the enemy's list, or fall back to basic attack
    chosen = enemy.choose_move()

    if chosen:
        print_slow(f"  [ {enemy.name} uses {chosen.name} ]")
        chosen.use(enemy, player)
        # Apply rage / volatile / weak multipliers to the move's raw damage
        # (handled inside each effect fn — status effects apply on top)
    else:
        # Fallback: plain attack with status modifiers
        raw_dmg = random.randint(4, enemy.attack_power)

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

        actual_dmg, absorbed = consume_block(player, raw_dmg)
        if absorbed:
            print_slow(f"  {enemy.name} hits for {raw_dmg} — 🛡 blocked {absorbed}, taking {actual_dmg}!")
        else:
            print_slow(f"  {enemy.name} hits you for {raw_dmg}!")
        if actual_dmg:
            player.take_damage(actual_dmg)
            print_slow(f"  Your HP: {player.health}")

    player.trigger_relics(TRIGGER_ON_HIT, enemy, {"damage": 0})


# ── Turn helpers ──────────────────────────────────────────────────────────────

def regen_ap(player):
    player.current_ap = MAX_AP
    clear_block(player)   # Block clears at start of each new turn (StS style)


def _resolve_turn_end(player, enemy):
    # Echo — free repeat of last command at end of turn
    echo_cmd = get_echo(player)
    if echo_cmd and enemy.health > 0:
        print_slow(f"  🔊 Echo — '{echo_cmd}' repeats for free!")
        if echo_cmd == "attack":
            do_attack(player, enemy, echo_cmd)
        elif echo_cmd == "heal":
            do_heal(player, enemy, echo_cmd)
        elif echo_cmd == "block":
            do_block(player, enemy, echo_cmd)

    player.trigger_relics(TRIGGER_TURN_END, enemy, {})
    if enemy.health > 0:
        tick_statuses(enemy)
    tick_statuses(player)


def _status_line(label, entity):
    s = format_statuses(entity)
    return f"  {label}: {s}" if s else None


def show_combat_status(player, enemy):
    print(f"\n  {'─' * 46}")
    enemy_s = format_statuses(enemy)
    player_s = format_statuses(player)
    print_slow(f"  ⚔  {enemy.name}  HP: {enemy.health}/{enemy.max_health}"
               + (f"  [{enemy_s}]" if enemy_s else ""))
    print(f"  {'─' * 46}")
    print_status(player)
    if player_s:
        print(f"  Status: [{player_s}]")
    if player.relics:
        print(f"  Relics: {', '.join(r.name for r in player.relics)}")
    print(f"\n  attack(6) | {BLUE}heal(4 AP + 1 MP){RESET} | block(5) | end")


# ── Player turn ───────────────────────────────────────────────────────────────

def player_turn(player, enemy):
    regen_ap(player)
    player.trigger_relics(TRIGGER_TURN_START, enemy, {})
    show_combat_status(player, enemy)

    while True:
        if enemy.health <= 0:
            return False

        raw = input("\n⚔ > ").lower().strip()
        if not raw:
            continue

        command, _ = parse_command(raw)

        if command in ["end", "done", "pass"]:
            print_slow("  You end your turn.")
            _resolve_turn_end(player, enemy)
            return enemy.health > 0

        if command in ["move", "go", "north", "south", "east", "west", "flee", "run", "escape"]:
            print_slow("  You cannot flee! Fight or die!")
            continue

        if command in ["inventory", "inv", "i"]:
            from utils.actions import do_inventory
            do_inventory(player)
            continue

        if command in ["relics", "relic"]:
            if player.relics:
                for r in player.relics:
                    print_slow(f"  • {r}")
            else:
                print_slow("  You carry no relics.")
            continue

        if command in ["look", "l"]:
            print_slow(f"  You are fighting {enemy.name}. There is no escape.")
            continue

        if command in ["help", "?"]:
            print_slow(f"  attack(6) | {BLUE}heal(4 AP + 1 MP){RESET} | block(5) | end")
            continue

        if command not in COMBAT_COMMANDS:
            print_slow(f"  Unknown: {command}. Use attack, heal, block, or end.")
            continue

        if not spend_ap(player, command):
            print_slow("  Not enough AP — type 'end' to end your turn.")
            continue

        if command == "attack":
            do_attack(player, enemy, raw)
        elif command == "heal":
            success = do_heal(player, enemy, raw)
            if not success:
                player.current_ap += len(command)  # refund AP
                continue
        elif command == "block":
            do_block(player, enemy, raw)

        # Update echo to track the last command used this turn
        if "echo" in player.statuses:
            player.statuses["echo"] = command

        if enemy.health <= 0:
            return False

        # Show updated status after every action
        enemy_s  = format_statuses(enemy)
        player_s = format_statuses(player)
        print_status(player)
        if enemy_s:
            print(f"  {enemy.name}: [{enemy_s}]")
        if player_s:
            print(f"  You:    [{player_s}]")

        if player.current_ap == 0:
            print_slow("  No AP remaining — ending your turn.")
            _resolve_turn_end(player, enemy)
            return enemy.health > 0


# ── Combat loop ───────────────────────────────────────────────────────────────

def combat_loop(player, room):
    for relic in player.relics:
        alive = get_alive_enemies(room)
        if alive:
            relic.on_combat_start(player, alive[0])

    while True:
        alive = get_alive_enemies(room)
        if not alive:
            print()
            print_slow("  ✦ All enemies defeated! ✦")
            regen_ap(player)
            input("\n  Press Enter to continue...")
            if player.level_ups:
                from utils.display import show_levelup
                show_levelup(player)
            break

        enemy = alive[0]
        enemy_alive = player_turn(player, enemy)

        if player.health <= 0:
            break
        if not enemy_alive:
            continue

        # Enemy turn
        print(f"\n  {'─' * 46}")
        print_slow(f"  {enemy.name}'s turn")
        print(f"  {'─' * 46}")

        if is_stunned(enemy):
            print_slow(f"  ⚡ {enemy.name} is stunned and loses their turn!")
            tick_statuses(enemy)
        else:
            enemy_counter(player, enemy)

        print()
        if player.health <= 0:
            break