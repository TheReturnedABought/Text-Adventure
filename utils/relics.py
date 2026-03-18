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
from utils.helpers import print_slow

VOWELS = set("aeiou")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _count(raw, letters):
    """Count occurrences of any character in `letters` within raw string."""
    return sum(raw.count(c) for c in letters)

def _vowels_as_l(raw):
    """Silent Lamb Wool: replace all vowels with 'l' before counting."""
    return "".join("l" if c in VOWELS else c for c in raw)


# ── Relics ────────────────────────────────────────────────────────────────────

class FrogStatue(Relic):
    name        = "Frog Statue"
    description = "Each 'a' typed poisons the enemy for 1 stack."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy.health > 0:
            n = ctx.get("raw", "").count("a")
            if n:
                apply_poison(enemy, n)


class VenomGland(Relic):
    name        = "Venom Gland"
    description = "Every attack poisons the enemy for 1 stack."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ATTACK and enemy.health > 0:
            apply_poison(enemy, 1)


class IronWill(Relic):
    name        = "Iron Will"
    description = "Gain 5 Block at the end of each turn."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_TURN_END:
            apply_block(player, 5)


class ThornBracelet(Relic):
    name        = "Thorn Bracelet"
    description = "Each time you are hit, gain 1 Rage (doubles next attack)."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_HIT and player.health > 0:
            apply_rage(player, 1)


class BerserkerHelm(Relic):
    name        = "Berserker Helm"
    description = "Each 'r' typed applies 2 Rage to yourself."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION:
            n = ctx.get("raw", "").count("r")
            if n:
                apply_rage(player, n * 2)


class CursedEye(Relic):
    name        = "Cursed Eye"
    description = "Each 'i' typed applies 1 Vulnerable to the enemy."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy.health > 0:
            n = ctx.get("raw", "").count("i")
            if n:
                apply_vulnerable(enemy, n)


class WhisperCharm(Relic):
    name        = "Whisper Charm"
    description = "Each 'k' typed applies 2 Weak to the enemy."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION and enemy.health > 0:
            n = ctx.get("raw", "").count("k")
            if n:
                apply_weak(enemy, n * 2)


class BlessedEye(Relic):
    name        = "Blessed Eye"
    description = "Each 'i' typed grants 2 Block."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION:
            n = ctx.get("raw", "").count("i")
            if n:
                apply_block(player, n * 2)


class SilentLambWool(Relic):
    name        = "Silent Lamb Wool"
    description = "All vowels (a/e/i/o/u) also count as 'l' when typed."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION:
            raw = ctx.get("raw", "")
            # Keep originals, append one extra 'l' per vowel
            extra_ls = sum(1 for c in raw if c in VOWELS)
            ctx["raw"] = raw + ("l" * extra_ls)


class BearsHide(Relic):
    name        = "Bear's Hide"
    description = "Each 'r' typed grants 1 AP."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ACTION:
            from utils.constants import MAX_AP
            n = ctx.get("raw", "").count("r")
            if n:
                gained = min(n, MAX_AP - player.current_ap)
                if gained > 0:
                    player.current_ap += gained
                    print_slow(f"  🐻 Bear's Hide — +{gained} AP! (AP: {player.current_ap})")


class VampiricBlade(Relic):
    name        = "Vampiric Blade"
    description = "Each attack drains 2 HP from the enemy."

    def trigger(self, event, player, enemy, ctx):
        if event == TRIGGER_ON_ATTACK:
            player.heal(2)
            print_slow(f"  🩸 Vampiric Blade — +2 HP! (HP: {player.health})")


# ── Registry ──────────────────────────────────────────────────────────────────

ALL_RELICS = {
    "frog statue":      FrogStatue,
    "venom gland":      VenomGland,
    "iron will":        IronWill,
    "thorn bracelet":   ThornBracelet,
    "berserker helm":   BerserkerHelm,
    "cursed eye":       CursedEye,
    "whisper charm":    WhisperCharm,
    "blessed eye":      BlessedEye,
    "silent lamb wool": SilentLambWool,
    "bears hide":       BearsHide,
    "vampiric blade":   VampiricBlade,
}


def get_relic(name):
    cls = ALL_RELICS.get(name.lower())
    return cls() if cls else None