# utils/relics.py
import random
from entities.relic import (
    Relic,
    TRIGGER_ON_ACTION, TRIGGER_ON_ATTACK, TRIGGER_ON_HEAL,
    TRIGGER_ON_BLOCK, TRIGGER_ON_HIT, TRIGGER_TURN_END, TRIGGER_TURN_START,
)
from utils.status_effects import (
    apply_poison, apply_stun, apply_rage,
    apply_vulnerable, apply_weak, apply_block,
)
from utils.helpers import print_slow, RARITY_COLORS, RESET

VOWELS = set("aeiou")

# Rarity tiers
COMMON    = "Common"
UNCOMMON  = "Uncommon"
RARE      = "Rare"
LEGENDARY = "Legendary"


# ══════════════════════════════════════════════════════════════════════════════
#  CLASS STARTER RELICS
# ══════════════════════════════════════════════════════════════════════════════

class IronCastHelm(Relic):
    """Soldier starter relic."""
    name        = "Iron-Cast Helm"
    description = "Gain 12 Block at the start of each combat."
    rarity      = UNCOMMON

    def on_combat_start(self, player, enemy):
        apply_block(player, 12)
        print_slow(f"  🪖 Iron-Cast Helm — +12 Block at combat start!")


class SleightmakersGlove(Relic):
    """Passive — checked in combat._calc_ap_cost via _letter_discount.
    With Silent Lamb Wool: free-letter set expands to include all vowels."""
    name        = "Sleightmaker's Glove"
    description = "Each 'l' in a command is free (no AP cost). With Silent Lamb Wool: vowels are also free."
    rarity      = RARE


class AetherTapestry(Relic):
    """Mage starter relic."""
    name        = "Aether-Spun Tapestry"
    description = "Max MP +2. Restore 1 MP at the start of each turn."
    rarity      = RARE

    def on_combat_start(self, player, enemy):
        player.max_mana += 2
        player.mana = min(player.mana + 2, player.max_mana)
        print_slow(f"  🌌 Aether-Spun Tapestry — Max MP +2! ({player.mana}/{player.max_mana})")

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_TURN_START:
            if player.mana < player.max_mana:
                player.mana += 1
                print_slow(f"  🌌 Aether-Spun Tapestry — +1 MP! ({player.mana}/{player.max_mana})")


# ══════════════════════════════════════════════════════════════════════════════
#  GENERAL RELICS
# ══════════════════════════════════════════════════════════════════════════════

class FrogStatue(Relic):
    name        = "Frog Statue"
    description = "Each 'a' typed poisons the target for 1 stack."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy and enemy.health > 0:
            n = ctx.get("raw", "").count("a")
            if n:
                apply_poison(enemy, n)


class VenomGland(Relic):
    name        = "Venom Gland"
    description = "Every attack poisons the target for 1 stack."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ATTACK and enemy and enemy.health > 0:
            apply_poison(enemy, 1)


class IronWill(Relic):
    name        = "Iron Will"
    description = "Gain 5 Block at the end of each turn."
    rarity      = UNCOMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_TURN_END:
            apply_block(player, 5)


class ThornBracelet(Relic):
    name        = "Thorn Bracelet"
    description = "Each time you are hit, gain 1 Rage."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_HIT and player.health > 0:
            apply_rage(player, 1)


class BerserkerHelm(Relic):
    name        = "Berserker Helm"
    description = "Each 'r' typed applies 2 Rage to yourself."
    rarity      = UNCOMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION:
            n = ctx.get("raw", "").count("r")
            if n:
                apply_rage(player, n * 2)


class CursedEye(Relic):
    name        = "Cursed Eye"
    description = "Each 'i' typed applies 1 Vulnerable to the target."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy and enemy.health > 0:
            n = ctx.get("raw", "").count("i")
            if n:
                apply_vulnerable(enemy, n)


class WhisperCharm(Relic):
    name        = "Whisper Charm"
    description = "Each 'k' typed applies 2 Weak to the target."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy and enemy.health > 0:
            n = ctx.get("raw", "").count("k")
            if n:
                apply_weak(enemy, n * 2)


class BlessedEye(Relic):
    name        = "Blessed Eye"
    description = "Each 'i' typed grants 2 Block."
    rarity      = UNCOMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION:
            n = ctx.get("raw", "").count("i")
            if n:
                apply_block(player, n * 2)


class SilentLambWool(Relic):
    name        = "Silent Lamb Wool"
    description = (
        "Vowels (a/e/i/o/u) count as 'l' when typed — "
        "reducing AP cost via Sleightmaker's Glove, "
        "and triggering other letter-counting relics."
    )
    rarity      = RARE

    def trigger(self, event, player, enemy, ctx):
        # Adds 'l's to ctx["raw"] so letter-counting relics (Whetstone,
        # BerserkerHelm, etc.) see vowels as 'l' for their own effects.
        # AP cost reduction is handled in combat._calc_ap_cost before AP
        # is spent, so it is not duplicated here.
        if event == TRIGGER_ON_ACTION:
            raw = ctx.get("raw", "")
            extra_ls = sum(1 for c in raw if c in VOWELS)
            ctx["raw"] = raw + ("l" * extra_ls)


class VampiricBlade(Relic):
    name        = "Vampiric Blade"
    description = "Each attack drains 2 HP from the enemy."
    rarity      = RARE

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ATTACK:
            player.heal(2)
            print_slow(f"  🩸 Vampiric Blade — +2 HP! (HP: {player.health})")


class Whetstone(Relic):
    name        = "Whetstone"
    description = "Each 's' typed applies 1 Bleed to the target (max 5 stacks total)."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy and enemy.health > 0:
            from utils.status_effects import apply_bleed
            n = ctx.get("raw", "").count("s")
            if n:
                current  = enemy.statuses.get("bleed", 0)
                can_add  = max(0, 5 - current)
                if can_add:
                    apply_bleed(enemy, min(n, can_add))


class EchoChamber(Relic):
    name        = "Echo Chamber"
    description = "Echo triggers twice instead of once."
    rarity      = RARE

    # Passive — checked by name in combat.py's _resolve_turn_end


class BearSkin(Relic):
    """Passive — checked in combat._calc_ap_cost via _letter_discount."""
    name        = "Bear Skin"
    description = "Each 'a' in a command reduces its AP cost by 1 (max −2)."
    rarity      = UNCOMMON


class WardensBrand(Relic):
    name        = "Warden's Brand"
    description = "All enemies enter combat with 1 Vulnerable."
    rarity      = COMMON

    def on_combat_start(self, player, enemy_ref):
        # enemy_ref is the first enemy; we need all enemies, stored in combat_flags
        player.combat_flags["wardens_brand_pending"] = True

    def trigger(self, event, player, enemy, ctx):
        # Fires on TRIGGER_TURN_START turn 1 to catch all enemies
        if event == TRIGGER_TURN_START and player.combat_flags.pop("wardens_brand_pending", False):
            # ctx doesn't have the full list; handled in combat.py run() directly
            pass


class EtchedStone(Relic):
    name        = "Etched Stone"
    description = "Each 'e' typed applies 1 Vulnerable to the target."
    rarity      = COMMON

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy and enemy.health > 0:
            from utils.status_effects import apply_vulnerable
            n = ctx.get("raw", "").count("e")
            if n:
                apply_vulnerable(enemy, n)



class ManaInfusedBone(Relic):
    name        = "Mana Infused Bone"
    description = "Gain 1 Dexterity for every MP you spend."
    rarity      = RARE

    def trigger(self, event, player, enemy, ctx):
        if event != TRIGGER_ON_ACTION:
            return
        spent = int(ctx.get("mp_spent", 0) or 0)
        if spent <= 0:
            return
        player.statuses["dexterity"] = player.statuses.get("dexterity", 0) + spent
        print_slow(f"  🦴 Mana Infused Bone — +{spent} Dexterity this combat.")


class TheStaticHunger(Relic):
    name        = "The Static Hunger"
    description = "Repeating the same action grants +1 Strength this turn."
    rarity      = UNCOMMON

    def trigger(self, event, player, enemy, ctx):
        if event != TRIGGER_ON_ACTION:
            return
        cmd = (ctx.get("command") or "").strip().lower()
        prev = (ctx.get("previous_command") or "").strip().lower()
        if not cmd or not prev or cmd != prev:
            return
        player.statuses["strength"] = player.statuses.get("strength", 0) + 1
        print_slow("  ⚡ The Static Hunger — repeated action, +1 Strength!")


# ── Registry ──────────────────────────────────────────────────────────────────

ALL_RELICS = {
    # Class starters
    "iron-cast helm":      IronCastHelm,
    "sleightmakers glove": SleightmakersGlove,
    "aether tapestry":     AetherTapestry,
    # General
    "frog statue":         FrogStatue,
    "venom gland":         VenomGland,
    "iron will":           IronWill,
    "thorn bracelet":      ThornBracelet,
    "berserker helm":      BerserkerHelm,
    "cursed eye":          CursedEye,
    "whisper charm":       WhisperCharm,
    "blessed eye":         BlessedEye,
    "silent lamb wool":    SilentLambWool,
    "bear skin":           BearSkin,
    "vampiric blade":      VampiricBlade,
    "whetstone":           Whetstone,
    "echo chamber":        EchoChamber,
    "wardens brand":       WardensBrand,
    "etched stone":        EtchedStone,
    "mana infused bone":   ManaInfusedBone,
    "the static hunger":   TheStaticHunger,
}


def get_relic(name):
    cls = ALL_RELICS.get(name.lower())
    return cls() if cls else None