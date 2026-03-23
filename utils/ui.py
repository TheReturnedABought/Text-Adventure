# utils/ui.py
"""
Terminal UI — 4-panel fixed layout.

┌─ ART ──────────────────────────────────────────────────────────────┐
│  Combat: enemy cards with art, HP/AP bars, planned move            │
│  Explore: room ASCII art + live summary (relics/items/events/exits)│
├─ STATUS ────────────────────────────────────────────────────────────┤
│  HP · AP · MP bars  │  level/XP  │  statuses  │  relics            │
│  command list with AP costs                                         │
├─ LOG ───────────────────────────────────────────────────────────────┤
│  Scrolling story / dialogue / combat output                        │
│  …                                                                 │
├─ INPUT ─────────────────────────────────────────────────────────────┤
│  > _                                                               │
└────────────────────────────────────────────────────────────────────┘

Integration
───────────
1.  from utils.ui import ui
2.  After player + room exist:
        ui.set_explore(player, room)
        ui.enable()
3.  On every room transition:   ui.set_explore(player, new_room)
4.  When combat starts:         ui.set_combat(player, room, enemies)
5.  When combat ends:           ui.set_explore(player, room)

print_slow() in helpers.py routes through ui.log() automatically.
builtins.input and builtins.print are monkey-patched on enable().
"""

import os
import re
import sys
import shutil
import time
import builtins
from collections import deque

# ── ANSI primitives ───────────────────────────────────────────────────────────
def _at(row: int, col: int = 1) -> str:
    return f"\x1b[{row};{col}H"

def _el() -> str:
    return "\x1b[2K"

CLEAR = "\x1b[2J\x1b[H"
HIDE  = "\x1b[?25l"
SHOW  = "\x1b[?25h"

# Colours
R  = "\x1b[0m"
BD = "\x1b[1m"
DM = "\x1b[2m"
RD = "\x1b[31m"
GR = "\x1b[32m"
YL = "\x1b[33m"
BL = "\x1b[34m"
MG = "\x1b[35m"
CY = "\x1b[36m"
WH = "\x1b[37m"
GY = "\x1b[90m"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mABCDEFGHJKSThlsurp]")

def _vis(s: str) -> int:
    """Visible (printable) length of a string, ignoring ANSI codes."""
    return len(_ANSI_RE.sub("", s))

def _pad(s: str, width: int) -> str:
    """Right-pad s to visible-width `width`."""
    gap = width - _vis(s)
    return s + (" " * max(0, gap))

# ── Layout constants ──────────────────────────────────────────────────────────
ART_H    = 13   # total rows for art panel (header + content)
HUD_H    = 4    # total rows for HUD panel
INP_H    = 2    # header + prompt
MIN_LOG  = 5    # minimum log rows


class UIManager:
    """
    Manages the 4-panel terminal UI.
    All panels are redrawn from scratch on every real input prompt.
    Between prompts, _paint_log_tail() cheaply appends new log lines.
    """

    def __init__(self):
        self._active     = False
        self._player     = None
        self._room       = None
        self._enemies    = []          # all enemies in current combat
        self._mode       = "explore"   # "explore" | "combat"
        self._log        = deque(maxlen=400)
        self._tw         = 80
        self._th         = 24
        self._log_top    = ART_H + HUD_H + 2   # first content row of log panel
        self._log_h      = MIN_LOG
        self._orig_input = builtins.input
        self._orig_print = builtins.print

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def enable(self):
        """Wire monkey-patches and activate the UI."""
        if self._active:
            return
        self._active = True
        mgr = self

        def _inp(prompt=""):
            return mgr._handle_input(str(prompt))

        def _prt(*args, sep=" ", end="\n", file=None, flush=False):
            if file not in (None, sys.stdout):
                mgr._orig_print(*args, sep=sep, end=end, file=file, flush=flush)
                return
            text = sep.join(str(a) for a in args)
            # Split multi-line prints into individual log entries
            for line in text.splitlines():
                mgr._add(line)
            if not text.endswith("\n") and text:
                pass  # already handled line by line

        builtins.input = _inp
        builtins.print = _prt

    def disable(self):
        if not self._active:
            return
        self._active = False
        builtins.input = self._orig_input
        builtins.print = self._orig_print
        sys.stdout.write(SHOW)
        sys.stdout.flush()

    # ── State setters ─────────────────────────────────────────────────────────

    def set_explore(self, player, room):
        self._player  = player
        self._room    = room
        self._mode    = "explore"
        self._enemies = []

    def set_combat(self, player, room, enemies):
        self._player  = player
        self._room    = room
        self._mode    = "combat"
        self._enemies = list(enemies)  # store all; filter alive on render

    # ── Logging ───────────────────────────────────────────────────────────────

    def log(self, text: str):
        """Add text to the story log (called by print_slow in helpers.py)."""
        for line in str(text).splitlines():
            self._add(line)
        if not str(text).strip():
            self._add("")

    def _add(self, line: str):
        self._log.append(line)
        if self._active:
            self._paint_log_tail()

    def _paint_log_tail(self):
        """
        Cheap incremental update: redraw only the log panel content.
        Positions cursor below the log area afterward so it does not
        interfere with the already-drawn input panel.
        """
        lines   = list(self._log)
        visible = lines[-self._log_h:] if len(lines) > self._log_h else lines
        pad     = self._log_h - len(visible)
        out     = []
        for i, ln in enumerate([""] * pad + visible):
            out.append(_at(self._log_top + i) + _el() + "  " + ln)
        # Park cursor just above the input separator so it stays tidy
        out.append(_at(self._log_top + self._log_h))
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # ── Input handler ─────────────────────────────────────────────────────────

    def _handle_input(self, prompt: str) -> str:
        """
        Monkey-patched replacement for builtins.input.
        "Press Enter" / "continue" prompts get a lightweight treatment.
        All other prompts trigger a full redraw.
        """
        is_cont = any(kw in prompt.lower()
                      for kw in ("press enter", "continue", "enter to"))
        if is_cont:
            # Show a dimmed separator in the log; don't fully redraw
            self._add(f"{GY}── {prompt.strip()} ──{R}")
            # Place cursor on last terminal row out of the way
            sys.stdout.write(_at(self._th, 1) + _el())
            sys.stdout.flush()
            return self._orig_input("")

        # Full redraw before real prompts (commands, choices, targeting)
        self._full_render(prompt)
        # Position cursor at the input content line, after the prompt
        sys.stdout.write(_at(self._th - 1, 3 + _vis(prompt)))
        sys.stdout.flush()
        result = self._orig_input("")
        if result.strip():
            self._log.append(f"{GY}  › {result}{R}")
        return result

    # ── Full render ───────────────────────────────────────────────────────────

    def _full_render(self, prompt: str = "> "):
        self._update_size()
        # Recalculate log height to fill the gap
        self._log_h   = max(MIN_LOG,
                            self._th - ART_H - HUD_H - INP_H - 1)
        self._log_top = ART_H + HUD_H + 2

        out = [CLEAR, HIDE]
        row = 1
        row = self._draw_art(out, row)
        row = self._draw_hud(out, row)
        row = self._draw_log(out, row)
        self._draw_input(out, row, prompt)
        out.append(SHOW)
        sys.stdout.write("".join(out))
        sys.stdout.flush()

    # ── Panel 1 — ART ─────────────────────────────────────────────────────────

    def _draw_art(self, out: list, r: int) -> int:
        w = self._tw
        if self._mode == "combat":
            title = "  ⚔  COMBAT  "
            hdr   = f"{YL}{BD}{'━'*3}{title}{'━'*max(0, w-len(title)-3)}{R}"
        else:
            name  = self._room.name if self._room else "…"
            title = f"  {name}  "
            hdr   = f"{CY}{BD}{'━'*3}{title}{'━'*max(0, w-len(title)-3)}{R}"
        out.append(_at(r) + _el() + hdr)
        r += 1

        art_lines = self._build_art()
        for i in range(ART_H - 1):
            ln = art_lines[i] if i < len(art_lines) else ""
            out.append(_at(r + i) + _el() + ln)
        return r + ART_H - 1

    def _build_art(self) -> list:
        if self._mode == "combat":
            alive = [e for e in self._enemies if e.health > 0]
            if alive:
                return self._combat_art(alive)
        if self._room:
            return self._room_art()
        return []

    # ── Combat art ────────────────────────────────────────────────────────────

    def _combat_art(self, alive: list) -> list:
        w = self._tw - 2
        if len(alive) <= 2:
            return self._enemies_row(alive, w)
        # 3-4 enemies: two rows of 2
        top = self._enemies_row(alive[:2], w)
        bot = self._enemies_row(alive[2:], w)
        return top + [""] + bot

    def _enemies_row(self, enemies: list, total_w: int) -> list:
        n    = max(len(enemies), 1)
        col  = (total_w - (n - 1) * 2) // n   # distribute width evenly
        cards = [self._enemy_card(e, col) for e in enemies]
        height = max(len(c) for c in cards)
        lines  = []
        for ri in range(height):
            segs = []
            for c in cards:
                seg = c[ri] if ri < len(c) else ""
                segs.append(_pad(seg, col))
            lines.append("  " + "  ".join(segs))
        return lines

    def _enemy_card(self, enemy, width: int) -> list:
        from utils.ascii_art import ENEMY_ART
        from utils.status_effects import format_statuses, is_stunned
        from utils.helpers import make_bar

        idx      = self._enemies.index(enemy) + 1 if enemy in self._enemies else "?"
        hp_pct   = enemy.health / max(enemy.max_health, 1)
        hp_col   = GR if hp_pct > 0.5 else (YL if hp_pct > 0.25 else RD)
        bar_w    = max(8, min(14, width - 22))
        hp_bar   = make_bar(enemy.health, enemy.max_health, bar_w)
        ap_bar   = make_bar(enemy.current_ap, enemy.max_ap, 6, "◆", "◇")

        if is_stunned(enemy):
            intent = f"{YL}⚡ STUNNED{R}"
        elif enemy._planned_moves:
            m0    = enemy._planned_moves[0]
            extra = f" +{len(enemy._planned_moves)-1}" if len(enemy._planned_moves) > 1 else ""
            intent = f"{RD}{m0.name}{R}({m0.ap_cost}){extra}"
        else:
            intent = f"{GY}???{R}"

        statuses = format_statuses(enemy)

        card = [
            f"{BD}[{idx}] {enemy.name}{R}",
            f"  {hp_col}HP[{hp_bar}]{enemy.health}/{enemy.max_health}{R}",
            f"  {BL}AP[{ap_bar}]{enemy.current_ap}/{enemy.max_ap}{R}",
            f"  →{intent}",
        ]
        if statuses:
            card.append(f"  [{statuses}]")

        art = ENEMY_ART.get(enemy.name, [])
        for al in art:
            card.append(f"  {GY}{al}{R}")

        return card

    # ── Room art ──────────────────────────────────────────────────────────────

    def _room_art(self) -> list:
        from utils.ascii_art import ROOM_ART
        from utils.helpers import RARITY_COLORS, RESET as RS

        room  = self._room
        lines = []

        art_str = ROOM_ART.get(room.name, "")
        if art_str:
            for al in art_str.strip("\n").splitlines():
                lines.append(f"  {GY}{al}{R}")
            lines.append("")

        alive = [e for e in room.enemies if e.health > 0]
        if alive:
            en = ", ".join(f"{RD}{e.name}{R}" for e in alive)
            lines.append(f"  {BD}Enemies :{R} {en}")
        if room.relics:
            rns = []
            for rr in room.relics:
                col = RARITY_COLORS.get(getattr(rr, "rarity", "Common"), "")
                rns.append(f"{col}{rr.name}{RS}")
            lines.append(f"  {BD}Relics  :{R} {', '.join(rns)}")
        if room.items:
            lines.append(f"  {BD}Items   :{R} {', '.join(room.items)}")
        if room.event and not room.event.resolved:
            lines.append(f"  {BD}Event   :{R} {CY}{room.event.name}{R}  (interact)")
        if room.puzzle and not room.puzzle.solved:
            lines.append(f"  {BD}Puzzle  :{R} {MG}{room.puzzle.name}{R}  (examine / solve)")
        exits    = list(room.connections.keys())
        locked   = room.locked_connections
        ex_strs  = [f"{e}🔒" if e in locked else e for e in exits]
        lines.append(f"  {BD}Exits   :{R} {', '.join(ex_strs)}")

        return lines

    # ── Panel 2 — STATUS / HUD ────────────────────────────────────────────────

    def _draw_hud(self, out: list, r: int) -> int:
        w = self._tw
        out.append(_at(r) + _el() +
                   f"{GR}{BD}{'━'*3}  STATUS  {'━'*max(0,w-12)}{R}")
        r += 1
        for ln in self._build_hud():
            out.append(_at(r) + _el() + ln)
            r += 1
        return r

    def _build_hud(self) -> list:
        from utils.helpers import make_bar, RARITY_COLORS, RESET as RS
        from utils.constants import MAX_AP, MAX_MANA, BASE_COMMANDS, HEAL_MP_COST
        from utils.status_effects import format_statuses
        from entities.class_data import get_command_def, cmd_ap_cost as _apc

        p = self._player
        if p is None:
            return ["  —", "", ""]

        hp_pct = p.health / max(p.max_health, 1)
        hc     = GR if hp_pct > 0.5 else (YL if hp_pct > 0.25 else RD)
        hp_b   = make_bar(p.health,     p.max_health, 18)
        ap_b   = make_bar(p.current_ap, MAX_AP,       12, "◆", "◇")
        mp_b   = make_bar(p.mana,       p.max_mana,    6, "●", "○")

        line1 = (
            f"  {hc}HP [{hp_b}] {p.health:>3}/{p.max_health:<3}{R}  "
            f"AP [{ap_b}] {p.current_ap:>2}/{MAX_AP}  "
            f"{BL}MP [{mp_b}] {p.mana}/{p.max_mana}{R}  "
            f"{BD}Lv{p.level}{R}  XP {p.xp}"
        )

        parts2 = []
        sts = format_statuses(p)
        if sts:
            parts2.append(f"Status [{sts}]")
        if p.relics:
            rns = []
            for rr in p.relics:
                col = RARITY_COLORS.get(getattr(rr, "rarity", "Common"), "")
                rns.append(f"{col}{rr.name}{RS}")
            parts2.append("  ".join(rns))
        line2 = "  " + "  │  ".join(parts2) if parts2 else ""

        base_str = (
            f"attack({BASE_COMMANDS['attack']['ap_cost']}) "
            f"heal({BASE_COMMANDS['heal']['ap_cost']}+{HEAL_MP_COST}MP) "
            f"block({BASE_COMMANDS['block']['ap_cost']})"
        )
        known = sorted(p.known_commands) if p.known_commands else []
        extra = ""
        if known:
            ps = []
            for cn in known[:10]:
                d  = get_command_def(p.char_class, cn)
                ps.append(f"{cn}({_apc(d) if d else len(cn)})")
            extra = "  │  " + " ".join(ps)
        line3 = f"  {DM}{base_str}{extra}{R}"

        lines = [line1]
        if line2:
            lines.append(line2)
        lines.append(line3)
        # Ensure exactly HUD_H - 1 content lines
        while len(lines) < HUD_H - 1:
            lines.append("")
        return lines[:HUD_H - 1]

    # ── Panel 3 — LOG ─────────────────────────────────────────────────────────

    def _draw_log(self, out: list, r: int) -> int:
        w = self._tw
        self._log_top = r + 1
        out.append(_at(r) + _el() +
                   f"{BL}{BD}{'━'*3}  LOG  {'━'*max(0,w-9)}{R}")
        r += 1
        lines   = list(self._log)
        visible = lines[-self._log_h:] if len(lines) > self._log_h else lines
        pad     = self._log_h - len(visible)
        for _ in range(pad):
            out.append(_at(r) + _el())
            r += 1
        for ln in visible:
            out.append(_at(r) + _el() + "  " + ln)
            r += 1
        return r

    # ── Panel 4 — INPUT ───────────────────────────────────────────────────────

    def _draw_input(self, out: list, r: int, prompt: str):
        w = self._tw
        out.append(_at(r) + _el() +
                   f"{MG}{BD}{'━'*3}  INPUT  {'━'*max(0,w-11)}{R}")
        out.append(_at(r + 1) + _el() +
                   f"  {BD}{WH}{prompt}{R} ")

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _update_size(self):
        s = shutil.get_terminal_size((80, 24))
        self._tw = s.columns
        self._th = s.lines


# ── Module-level singleton ────────────────────────────────────────────────────

ui = UIManager()