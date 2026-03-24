# utils/window.py
"""
GameWindow — standalone Tkinter window for the text adventure.

Layout (4 panels, stacked vertically)
──────────────────────────────────────
  ┌─ ART ──────────────────────────────────┐
  │  Combat : enemy cards + ASCII portraits │
  │  Explore: room art + room summary       │
  ├─ STATUS ───────────────────────────────┤
  │  HP / AP / MP bars  ·  relics · cmds   │
  ├─ LOG ──────────────────────────────────┤
  │  Scrolling story / combat output       │
  │  (auto-scroll, ANSI colours rendered)  │
  ├─ INPUT ────────────────────────────────┤
  │  prompt  [__________________________]  │
  └────────────────────────────────────────┘

Threading model
───────────────
  Main thread  → Tkinter mainloop (all widget operations).
  Game thread  → game logic; blocked on threading.Event for every input().

Integration
───────────
  from utils.window import window
  window.run_game(callable)   # builds window, starts game thread, loops

  window.set_explore(player, room)
  window.set_combat(player, room, enemies)
  window.log(text)            # called by print_slow in helpers.py
"""

import re
import sys
import threading
import tkinter as tk
import builtins
from collections import deque

# ── Helpers ───────────────────────────────────────────────────────────────────

_ANSI_RE    = re.compile(r'\x1b\[[0-9;]*[mABCDEFGHJKSThlsurp]')
_ANSI_SPLIT = re.compile(r'(\x1b\[[0-9;]*m)')

def _strip(s: str) -> str:
    return _ANSI_RE.sub('', str(s))

# ANSI code → tkinter tag name
_CODE_TAG = {
    '31': 'red',   '32': 'green',  '33': 'yellow',
    '34': 'blue',  '35': 'magenta','36': 'cyan',
    '37': 'white', '90': 'gray',   '94': 'blue',
}


# ══════════════════════════════════════════════════════════════════════════════
#  UIState — shared data snapshot (written by game thread, read by UI thread)
# ══════════════════════════════════════════════════════════════════════════════

class UIState:
    def __init__(self):
        self.player  = None
        self.room    = None
        self.enemies = []
        self.mode    = 'explore'   # 'explore' | 'combat'

    def set_explore(self, player, room):
        self.player  = player
        self.room    = room
        self.mode    = 'explore'
        self.enemies = []

    def set_combat(self, player, room, enemies):
        self.player  = player
        self.room    = room
        self.mode    = 'combat'
        self.enemies = list(enemies)


# ══════════════════════════════════════════════════════════════════════════════
#  GameWindow
# ══════════════════════════════════════════════════════════════════════════════

class GameWindow:
    # ── Colour palette ────────────────────────────────────────────────────────
    C_BG      = '#0d0d1a'
    C_PANEL   = '#11111f'
    C_SEP     = '#1e1e38'
    C_BORDER  = '#2a2a50'
    C_TEXT    = '#d0d0e8'
    C_DIM     = '#505068'

    C_HP      = '#e05555'
    C_AP      = '#5588ee'
    C_MP      = '#9955ee'
    C_GOLD    = '#ddaa33'

    C_RED     = '#e05555'
    C_GREEN   = '#55cc88'
    C_YELLOW  = '#ddcc44'
    C_BLUE    = '#5588ee'
    C_CYAN    = '#44cccc'
    C_MAGENTA = '#cc55cc'
    C_GRAY    = '#505068'
    C_WHITE   = '#d0d0e8'

    FONT    = ('Courier New', 10)
    FONT_B  = ('Courier New', 10, 'bold')
    FONT_SM = ('Courier New', 9)

    # All colour tags shared between art and log panels
    _TAGS = {
        'bold':    {'font': ('Courier New', 10, 'bold')},
        'dim':     {'foreground': '#505068'},
        'red':     {'foreground': '#e05555'},
        'green':   {'foreground': '#55cc88'},
        'yellow':  {'foreground': '#ddcc44'},
        'blue':    {'foreground': '#5588ee'},
        'magenta': {'foreground': '#cc55cc'},
        'cyan':    {'foreground': '#44cccc'},
        'gray':    {'foreground': '#505068'},
        'white':   {'foreground': '#d0d0e8'},
        'input':   {'foreground': '#ddcc44'},
        'sep':     {'foreground': '#2a2a50'},
        'hp':      {'foreground': '#e05555'},
        'ap':      {'foreground': '#5588ee'},
        'mp':      {'foreground': '#9955ee'},
    }

    def __init__(self):
        self._state        = UIState()
        self._log          = deque(maxlen=600)
        self._input_event  = threading.Event()
        self._input_result = ''
        self._active       = False
        self._root         = None
        self._orig_print   = builtins.print
        self._orig_input   = builtins.input

    # ── Public API ────────────────────────────────────────────────────────────

    def _enable_copy(self, widget):
        widget.bind("<Control-c>", lambda e: widget.event_generate("<<Copy>>"))
        widget.bind("<Button-1>", lambda e: widget.config(state="normal"))
        widget.bind("<ButtonRelease-1>", lambda e: widget.config(state="disabled"))

    def _allow_text_selection(self, widget):
        widget.bind("<Button-1>", lambda e: widget.config(state="normal"))
        widget.bind("<ButtonRelease-1>", lambda e: widget.config(state="disabled"))

    def set_explore(self, player, room):
        self._state.set_explore(player, room)
        self._schedule(self._refresh_art)
        self._schedule(self._refresh_hud)

    def set_combat(self, player, room, enemies):
        self._state.set_combat(player, room, enemies)
        self._schedule(self._refresh_art)
        self._schedule(self._refresh_hud)

    def refresh(self):
        """Force a full panel refresh (callable from either thread)."""
        self._schedule(self._refresh_art)
        self._schedule(self._refresh_hud)

    def log(self, text: str):
        """Append text to the log. Safe to call from game thread."""
        for line in str(text).splitlines():
            self._log.append(line)
            self._schedule(lambda ln=line: self._append_log(ln))

    def enable(self):
        """Monkey-patch builtins.print and builtins.input."""
        if self._active:
            return
        self._active = True
        gw = self

        def _print(*args, sep=' ', end='\n', file=None, flush=False):
            if file not in (None, sys.stdout):
                gw._orig_print(*args, sep=sep, end=end, file=file, flush=flush)
                return
            text = sep.join(str(a) for a in args)
            for line in text.splitlines():
                gw._log.append(line)
                gw._schedule(lambda ln=line: gw._append_log(ln))

        def _input(prompt=''):
            return gw._handle_input(str(prompt))

        builtins.print = _print
        builtins.input = _input

    def disable(self):
        if not self._active:
            return
        self._active = False
        builtins.print = self._orig_print
        builtins.input = self._orig_input

    def run_game(self, game_fn):
        """
        Entry point: build window → patch builtins → start game thread → mainloop.
        Call this from the main thread (typically at the bottom of main.py).
        """
        self._build_window()
        self.enable()
        t = threading.Thread(target=self._game_thread, args=(game_fn,), daemon=True)
        t.start()
        self._root.mainloop()

    # ── Window construction ───────────────────────────────────────────────────

    def _build_window(self):
        root = tk.Tk()
        root.title('Text Adventure')
        root.configure(bg=self.C_BG)
        root.geometry('920x700')
        root.minsize(700, 520)
        root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._root = root

        # 4 rows: ART fixed, STATUS fixed, LOG expands, INPUT fixed
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=0)
        root.rowconfigure(1, weight=0)
        root.rowconfigure(2, weight=1)
        root.rowconfigure(3, weight=0)

        self._build_art(root)
        self._build_status(root)
        self._build_log(root)
        self._build_input(root)

    def _hdr(self, parent, row, text, color):
        """Shared coloured header label for each panel."""
        lbl = tk.Label(
            parent, text=f'  {text}', bg=self.C_BORDER, fg=color,
            font=self.FONT_B, anchor='w', padx=6, pady=2,
        )
        lbl.grid(row=row, column=0, sticky='ew')
        return lbl

    # ── Panel 1 — ART ─────────────────────────────────────────────────────────

    def _build_art(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=0, column=0, sticky='nsew', padx=4, pady=(4, 0))
        frm.columnconfigure(0, weight=1)

        self._art_hdr = self._hdr(frm, 0, 'EXPLORE', self.C_CYAN)

        self._art_txt = tk.Text(
            frm, height=13, bg=self.C_PANEL, fg=self.C_TEXT,
            font=self.FONT_SM, bd=0, relief='flat',
            state='disabled', wrap='none',
            cursor='arrow',
        )
        self._art_txt.grid(row=1, column=0, sticky='nsew')
        self._apply_tags(self._art_txt)
        self._enable_copy(self._art_txt)
        self._allow_text_selection(self._art_txt)

    # ── Panel 2 — STATUS ──────────────────────────────────────────────────────

    def _build_status(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=1, column=0, sticky='nsew', padx=4, pady=(2, 0))
        frm.columnconfigure(0, weight=1)

        self._hdr(frm, 0, 'STATUS', self.C_GREEN)

        self._hud_txt = tk.Text(
            frm,
            height=4,
            bg=self.C_PANEL,
            fg=self.C_TEXT,
            font=self.FONT_SM,
            bd=0,
            relief='flat',
            state='disabled',
            wrap='none'
        )

        self._hud_txt.grid(row=1, column=0, sticky='ew')

        self._apply_tags(self._hud_txt)
        self._enable_copy(self._hud_txt)

    # ── Panel 3 — LOG ─────────────────────────────────────────────────────────

    def _build_log(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=2, column=0, sticky='nsew', padx=4, pady=(2, 0))
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        self._hdr(frm, 0, 'LOG', self.C_BLUE)

        self._log_txt = tk.Text(
            frm, bg=self.C_PANEL, fg=self.C_TEXT,
            font=self.FONT_SM, bd=0, relief='flat',
            state='disabled', wrap='word',
        )
        sb = tk.Scrollbar(frm, command=self._log_txt.yview,
                          bg=self.C_BORDER, troughcolor=self.C_SEP,
                          relief='flat', bd=0)
        self._log_txt.configure(yscrollcommand=sb.set)

        self._log_txt.grid(row=1, column=0, sticky='nsew')
        sb.grid(row=1, column=1, sticky='ns')
        self._apply_tags(self._log_txt)
        self._enable_copy(self._log_txt)
        self._allow_text_selection(self._log_txt)

    # ── Panel 4 — INPUT ───────────────────────────────────────────────────────

    def _build_input(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=3, column=0, sticky='nsew', padx=4, pady=(2, 4))
        frm.columnconfigure(1, weight=1)

        self._hdr(frm, 0, 'INPUT', self.C_MAGENTA)

        self._prompt_lbl = tk.Label(
            frm, text='>  ', bg=self.C_PANEL, fg=self.C_YELLOW,
            font=self.FONT_B, padx=6,
        )
        self._prompt_lbl.grid(row=1, column=0, sticky='w')

        self._input_var = tk.StringVar()
        self._input_ent = tk.Entry(
            frm, textvariable=self._input_var,
            bg=self.C_PANEL, fg=self.C_TEXT,
            insertbackground=self.C_TEXT,
            font=self.FONT, relief='flat', bd=4,
        )
        self._input_ent.grid(row=1, column=1, sticky='ew', padx=(0, 6), pady=4)
        self._input_ent.bind('<Return>', self._on_enter)
        self._input_ent.focus_set()

    # ── Tag configuration ─────────────────────────────────────────────────────

    def _apply_tags(self, widget):
        for name, opts in self._TAGS.items():
            widget.tag_configure(name, **opts)

    # ── ART refresh ───────────────────────────────────────────────────────────

    def _refresh_art(self):
        t = self._art_txt
        t.configure(state='normal')
        t.delete('1.0', 'end')

        s = self._state
        if s.mode == 'combat':
            self._art_hdr.configure(text='  ⚔  COMBAT', fg=self.C_YELLOW)
            self._draw_combat(t, s)
        else:
            name = s.room.name if s.room else '…'
            self._art_hdr.configure(text=f'  {name}', fg=self.C_CYAN)
            self._draw_explore(t, s)

        t.configure(state='disabled')

    def _draw_combat(self, t, s):
        try:
            from utils.ascii_art import ENEMY_ART
            from utils.status_effects import format_statuses, is_stunned
            from utils.helpers import make_bar
        except ImportError:
            t.insert('end', '\n  (imports not ready)\n')
            return

        alive = [e for e in s.enemies if e.health > 0]
        if not alive:
            t.insert('end', '\n  ✦ All enemies defeated!\n', 'green')
            return

        for idx, enemy in enumerate(alive, 1):
            hpct  = enemy.health / max(enemy.max_health, 1)
            hcol  = 'green' if hpct > 0.5 else ('yellow' if hpct > 0.25 else 'red')
            hp_b  = make_bar(enemy.health,     enemy.max_health, 14)
            ap_b  = make_bar(enemy.current_ap, enemy.max_ap, 8, '◆', '◇')

            t.insert('end', f'\n  [{idx}] ', 'dim')
            t.insert('end', f'{enemy.name}', 'bold')

            # Intent
            if is_stunned(enemy):
                t.insert('end', '  →  ⚡ STUNNED\n', 'yellow')
            elif getattr(enemy, '_planned_moves', []):
                m0 = enemy._planned_moves[0]
                sx = f' +{len(enemy._planned_moves)-1}' if len(enemy._planned_moves) > 1 else ''
                t.insert('end', '  →  ', 'dim')
                t.insert('end', m0.name, 'red')
                t.insert('end', f'({m0.ap_cost}){sx}\n', 'dim')
            else:
                t.insert('end', '  →  ???\n', 'dim')

            # HP / AP bars
            t.insert('end', '      HP[', 'dim')
            t.insert('end', hp_b, hcol)
            t.insert('end', f'] {enemy.health}/{enemy.max_health}', hcol)
            t.insert('end', '    AP[', 'dim')
            t.insert('end', ap_b, 'ap')
            t.insert('end', f'] {enemy.current_ap}/{enemy.max_ap}\n', 'ap')

            # Statuses
            st = _strip(format_statuses(enemy))
            if st:
                t.insert('end', f'      [{st}]\n', 'yellow')

            # ASCII portrait
            for art_line in ENEMY_ART.get(enemy.name, [])[:4]:
                t.insert('end', f'      {art_line}\n', 'dim')

    def _draw_explore(self, t, s):
        try:
            from utils.ascii_art import ROOM_ART
        except ImportError:
            ROOM_ART = {}

        room = s.room
        if not room:
            return

        art_str = ROOM_ART.get(room.name, '')
        if art_str:
            for ln in art_str.strip('\n').splitlines()[:5]:
                t.insert('end', f'  {ln}\n', 'dim')
            t.insert('end', '\n')

        alive = [e for e in room.enemies if e.health > 0]
        if alive:
            t.insert('end', '  Enemies:  ', 'bold')
            t.insert('end', ', '.join(e.name for e in alive) + '\n', 'red')
        if room.relics:
            t.insert('end', '  Relics:   ', 'bold')
            t.insert('end', ', '.join(r.name for r in room.relics) + '\n', 'cyan')
        if room.items:
            t.insert('end', '  Items:    ', 'bold')
            t.insert('end', ', '.join(room.items) + '\n', 'white')
        if getattr(room, 'event', None) and not room.event.resolved:
            t.insert('end', '  Event:    ', 'bold')
            t.insert('end', room.event.name + '  (interact)\n', 'cyan')
        if getattr(room, 'puzzle', None) and not room.puzzle.solved:
            t.insert('end', '  Puzzle:   ', 'bold')
            t.insert('end', room.puzzle.name + '  (examine / solve)\n', 'magenta')

        exits = list(room.connections.keys())
        locked = room.locked_connections
        exs = [f'{d}🔒' if d in locked else d for d in exits]
        t.insert('end', '  Exits:    ', 'bold')
        t.insert('end', ', '.join(exs) + '\n', 'green')

    # ── HUD refresh ───────────────────────────────────────────────────────────
    def _make_bar(self, cur, mx, width=10, full='█', empty='░'):
        if mx <= 0:
            return empty * width

        pct = max(0, min(1, cur / mx))
        filled = int(round(pct * width))

        return full * filled + empty * (width - filled)

    def _refresh_hud(self):
        t = self._hud_txt

        t.configure(state='normal')
        t.delete('1.0', 'end')

        p = self._state.player
        if not p:
            t.configure(state='disabled')
            return

        try:
            from utils.constants import (
                MAX_AP,
                BASE_COMMANDS,
                HEAL_MP_COST
            )
            from utils.status_effects import format_statuses
            from entities.class_data import (
                get_command_def,
                cmd_ap_cost as _apc
            )
        except ImportError:
            t.configure(state='disabled')
            return

        # ── Bars ─────────────────────────

        hp_bar = self._make_bar(p.health, p.max_health)
        ap_bar = self._make_bar(p.current_ap, MAX_AP)
        mp_bar = self._make_bar(p.mana, p.max_mana)

        t.insert(
            'end',
            f"HP [{hp_bar}] {p.health}/{p.max_health}   ",
            'hp'
        )

        t.insert(
            'end',
            f"AP [{ap_bar}] {p.current_ap}/{MAX_AP}   ",
            'ap'
        )

        t.insert(
            'end',
            f"MP [{mp_bar}] {p.mana}/{p.max_mana}   ",
            'mp'
        )

        t.insert(
            'end',
            f"Lv{p.level}  XP {p.xp}\n",
            'yellow'
        )

        # ── Status + relics ─────────────

        st = _strip(format_statuses(p))
        rls = '  ·  '.join(r.name for r in p.relics)

        mid = '  '.join(filter(None, [st, rls]))

        if mid:
            t.insert('end', mid + '\n', 'dim')

        # ── Commands ────────────────────

        base = (
            f"attack({BASE_COMMANDS['attack']['ap_cost']}) "
            f"heal({BASE_COMMANDS['heal']['ap_cost']}+{HEAL_MP_COST}MP) "
            f"block({BASE_COMMANDS['block']['ap_cost']})"
        )

        kp = []

        for cn in sorted(p.known_commands)[:10]:
            d = get_command_def(p.char_class, cn)

            kp.append(
                f"{cn}({_apc(d) if d else len(cn)})"
            )

        if kp:
            base += '  │  ' + ' '.join(kp)

        t.insert('end', base + '\n', 'dim')

        t.configure(state='disabled')

    # ── LOG append ────────────────────────────────────────────────────────────

    def _append_log(self, line: str):
        """Append one line to the log widget (UI thread)."""
        t = self._log_txt
        t.configure(state='normal')
        self._insert_ansi(t, line + '\n')
        t.configure(state='disabled')
        t.see('end')

    def _insert_ansi(self, widget, text: str):
        """Split text on ANSI codes and insert with colour tags."""
        parts  = _ANSI_SPLIT.split(text)
        active = []
        for part in parts:
            m = re.fullmatch(r'\x1b\[([0-9;]*)m', part)
            if m:
                codes = m.group(1).split(';') if m.group(1) else ['0']
                for code in codes:
                    if code in ('0', ''):
                        active = []
                    elif code == '1':
                        if 'bold' not in active:
                            active.append('bold')
                    elif code == '2':
                        if 'dim' not in active:
                            active.append('dim')
                    elif code in _CODE_TAG:
                        # Replace any existing colour tag
                        active = [t for t in active if t not in _CODE_TAG.values()]
                        active.append(_CODE_TAG[code])
            elif part:
                widget.insert('end', part, tuple(active) if active else ())

    # ── Input handling ────────────────────────────────────────────────────────

    def _handle_input(self, prompt: str) -> str:
        """
        Blocking input replacement (called from game thread).
        Schedules a prompt update then waits for the user to press Enter.
        """
        self._input_event.clear()
        self._input_result = ''

        clean = _strip(prompt).strip()

        # Update prompt label on UI thread
        self._schedule(lambda: self._prompt_lbl.configure(
            text=f'  {clean}  ' if clean else '>  '))

        # For "Press Enter" pauses, log a separator
        _cont = ('press enter', 'continue', 'enter to', 'enter...')
        if clean.lower() and any(kw in clean.lower() for kw in _cont):
            self._schedule(lambda: self._append_log(
                f'  ── {clean} ──'))

        # Refresh HUD before each real command prompt
        self._schedule(self._refresh_hud)

        self._input_event.wait()
        result = self._input_result

        # Echo non-empty user input to log
        if result.strip():
            self._schedule(lambda r=result: (
                self._log_txt.configure(state='normal'),
                self._log_txt.insert('end', f'  › {r}\n', 'input'),
                self._log_txt.configure(state='disabled'),
                self._log_txt.see('end'),
            ))

        return result

    def _on_enter(self, _event=None):
        """Called on UI thread when user presses Enter in the input box."""
        val = self._input_var.get()
        self._input_var.set('')
        self._input_result = val
        self._input_event.set()
        # Keep focus in the entry
        self._input_ent.focus_set()
        return 'break'

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _schedule(self, fn):
        """Schedule fn on the UI thread. Safe to call from any thread."""
        if self._root:
            self._root.after(0, fn)

    def _game_thread(self, game_fn):
        try:
            game_fn()
        except SystemExit:
            pass
        except Exception as e:
            self._schedule(lambda: self._append_log(f'\n  [Unhandled error: {e}]'))
        finally:
            # Unblock any waiting input() so the UI can stay responsive
            self._input_result = ''
            self._input_event.set()

    def _on_close(self):
        self._input_result = ''
        self._input_event.set()
        if self._root:
            self._root.destroy()
        sys.exit(0)


# ── Module-level singleton ────────────────────────────────────────────────────

window = GameWindow()