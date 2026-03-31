# utils/window.py
"""
GameWindow — standalone Tkinter window, 4 panels.

┌─ ART ────────────────────────────────────────────┐
│  Combat: enemies SIDE-BY-SIDE in monospace cols  │
│  Explore: room art + live summary                │
├─ STATUS ──────────────────────────────────────────┤
│  HP / AP / MP bars  ·  relics  ·  commands       │
├─ LOG ─────────────────────────────────────────────┤
│  Scrolling story / combat output                 │
├─ INPUT ───────────────────────────────────────────┤
│  > _                                             │
└──────────────────────────────────────────────────┘

Side-by-side enemy layout
──────────────────────────
Each enemy is rendered as a list of fixed-width text rows.
All columns are padded to the same width and same height, then
zipped together line-by-line into the Text widget. Guaranteed
no misalignment regardless of portrait height differences.
"""

import re
import sys
import threading
import tkinter as tk
import builtins
from collections import deque
from collections import Counter

_ANSI_RE    = re.compile(r'\x1b\[[0-9;]*[mABCDEFGHJKSThlsurp]')
_ANSI_SPLIT = re.compile(r'(\x1b\[[0-9;]*m)')


def _strip(s: str) -> str:
    return _ANSI_RE.sub('', str(s))


def _stacked_items(items):
    counts = Counter(items)
    return [f"{count} x {name}" if count > 1 else name for name, count in counts.items()]


def _move_hint(move):
    hint = getattr(move, "intent_hint", "")
    return f" {hint}" if hint else ""


_CODE_TAG = {
    '31': 'red',    '32': 'green',   '33': 'yellow',
    '34': 'blue',   '35': 'magenta', '36': 'cyan',
    '37': 'white',  '90': 'gray',    '94': 'blue',
}


# ══════════════════════════════════════════════════════════════════════════════

class UIState:
    __slots__ = ('player', 'room', 'enemies', 'mode')

    def __init__(self):
        self.player  = None
        self.room    = None
        self.enemies = []
        self.mode    = 'explore'

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

class GameWindow:
    # ── Palette ───────────────────────────────────────────────────────────────
    C_BG      = '#0d0d1a';  C_PANEL   = '#11111f';  C_BORDER  = '#2a2a50'
    C_SEP     = '#1e1e38';  C_TEXT    = '#d0d0e8';  C_DIM     = '#505068'
    C_HP      = '#e05555';  C_AP      = '#5588ee';  C_MP      = '#9955ee'
    C_GOLD    = '#ddaa33'
    C_RED     = '#e05555';  C_GREEN   = '#55cc88';  C_YELLOW  = '#ddcc44'
    C_BLUE    = '#5588ee';  C_CYAN    = '#44cccc';  C_MAGENTA = '#cc55cc'
    C_GRAY    = '#505068';  C_WHITE   = '#d0d0e8'

    FONT    = ('Courier New', 10)
    FONT_B  = ('Courier New', 10, 'bold')
    FONT_SM = ('Courier New', 9)

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
        'ap':      {'foreground': '#5588ee'},
        'mp':      {'foreground': '#9955ee'},
        'hp_good': {'foreground': '#55cc88'},
        'hp_mid':  {'foreground': '#ddcc44'},
        'hp_low':  {'foreground': '#e05555'},
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

    def set_explore(self, player, room):
        self._state.set_explore(player, room)
        self._schedule(self._refresh_art)
        self._schedule(self._refresh_hud)

    def set_combat(self, player, room, enemies):
        self._state.set_combat(player, room, enemies)
        self._schedule(self._refresh_art)
        self._schedule(self._refresh_hud)

    def refresh(self):
        self._schedule(self._refresh_art)
        self._schedule(self._refresh_hud)

    def log(self, text: str):
        for line in str(text).splitlines():
            self._log.append(line)
            self._schedule(lambda ln=line: self._append_log(ln))

    def enable(self):
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
        """Build window → patch builtins → start game thread → mainloop."""
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
        root.geometry('960x720')
        root.minsize(720, 540)
        root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._root = root

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
        lbl = tk.Label(parent, text=f'  {text}',
                       bg=self.C_BORDER, fg=color,
                       font=self.FONT_B, anchor='w', padx=6, pady=2)
        lbl.grid(row=row, column=0, columnspan=2, sticky='ew')
        return lbl

    # ── Panel 1 — ART ─────────────────────────────────────────────────────────

    def _build_art(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=0, column=0, sticky='nsew', padx=4, pady=(4, 0))
        frm.columnconfigure(0, weight=1)

        self._art_hdr = self._hdr(frm, 0, 'EXPLORE', self.C_CYAN)

        self._art_txt = tk.Text(
            frm, height=12, bg=self.C_PANEL, fg=self.C_TEXT,
            font=self.FONT_SM, bd=0, relief='flat',
            state='disabled', wrap='none', cursor='arrow',
        )
        self._art_txt.grid(row=1, column=0, sticky='nsew')
        self._apply_tags(self._art_txt)
        self._art_txt.bind('<Configure>',
                           lambda _: self._schedule(self._refresh_art))

    # ── Panel 2 — STATUS ──────────────────────────────────────────────────────

    def _build_status(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=1, column=0, sticky='nsew', padx=4, pady=(2, 0))
        frm.columnconfigure(0, weight=1)

        self._hdr(frm, 0, 'STATUS', self.C_GREEN)

        self._hud_canvas = tk.Canvas(
            frm, height=68, bg=self.C_PANEL,
            bd=0, relief='flat', highlightthickness=0,
        )
        self._hud_canvas.grid(row=1, column=0, sticky='ew')
        self._hud_canvas.bind('<Configure>',
                              lambda _: self._schedule(self._refresh_hud))

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

    # ── Panel 4 — INPUT ───────────────────────────────────────────────────────

    def _build_input(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=3, column=0, sticky='nsew', padx=4, pady=(2, 4))
        frm.columnconfigure(1, weight=1)

        self._hdr(frm, 0, 'INPUT', self.C_MAGENTA)

        self._prompt_lbl = tk.Label(
            frm, text='>  ', bg=self.C_PANEL, fg=self.C_GOLD,
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

    def _apply_tags(self, w):
        for name, opts in self._TAGS.items():
            w.tag_configure(name, **opts)

    # ── ART panel ─────────────────────────────────────────────────────────────

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

    # ── SIDE-BY-SIDE combat ───────────────────────────────────────────────────

    def _draw_combat(self, t, s):
        alive = [e for e in s.enemies if e.health > 0 and not getattr(e, 'fled', False)]
        if not alive:
            t.insert('end', '\n  ✦ All enemies defeated!\n', 'green')
            return

        n = len(alive)

        # Estimate column width from widget pixel width
        px_w   = max(t.winfo_width(), 480)
        ch_px  = 7          # Courier New 9 ≈ 7px/char
        total  = px_w // ch_px - 4
        gap    = 2
        col_w  = max(26, (total - gap * (n - 1)) // n)

        # Build all cards as equal-height lists of (text, tag) row lists
        cards  = [self._enemy_card_rows(e, s.enemies, col_w) for e in alive]
        height = max(len(c) for c in cards)

        # Pad all cards to same height with blank rows
        for card in cards:
            while len(card) < height:
                card.append([(' ' * col_w, '')])

        t.insert('end', '\n')
        for ri in range(height):
            t.insert('end', '  ')
            for ci, card in enumerate(cards):
                used = 0
                for text, tag in card[ri]:
                    t.insert('end', text, (tag,) if tag else ())
                    used += len(text)
                # Pad to col_w
                pad = max(0, col_w - used)
                if pad:
                    t.insert('end', ' ' * pad)
                if ci < n - 1:
                    t.insert('end', ' ' * gap)
            t.insert('end', '\n')

    def _enemy_card_rows(self, enemy, all_enemies, col_w):
        """
        Returns list of rows. Each row = list of (plain_text, tag) pairs.
        Total visible characters per row <= col_w.
        Enemies are guaranteed to render side-by-side with no overlap.
        """
        try:
            from utils.ascii_art import ENEMY_ART
            from utils.status_effects import format_statuses, is_stunned
            from utils.helpers import make_bar
        except ImportError:
            return [[(f'[?] {enemy.name}'[:col_w].ljust(col_w), 'bold')]]

        idx  = all_enemies.index(enemy) + 1 if enemy in all_enemies else '?'
        hpct = enemy.health / max(enemy.max_health, 1)
        hcol = 'hp_good' if hpct > 0.5 else ('hp_mid' if hpct > 0.25 else 'hp_low')
        bw   = max(6, min(12, col_w - 15))
        hp_b = make_bar(enemy.health,     enemy.max_health, bw)
        ap_b = make_bar(enemy.current_ap, enemy.max_ap,     6, '◆', '◇')

        if is_stunned(enemy):
            intent, itag = '→ ⚡STUNNED', 'yellow'
        elif getattr(enemy, '_planned_moves', []):
            m0    = enemy._planned_moves[0]
            extra = f'+{len(enemy._planned_moves)-1}' if len(enemy._planned_moves) > 1 else ''
            intent, itag = f'→{m0.name}({m0.ap_cost}){_move_hint(m0)}{extra}', 'red'
        else:
            intent, itag = '→ ???', 'dim'

        st = _strip(format_statuses(enemy))

        def row(*segs):
            return list(segs)

        def txt(s, tag='', width=col_w):
            return (s[:width].ljust(width), tag)

        rows = [
            row(txt(f'[{idx}] {enemy.name}', 'bold')),
            row(txt(intent, itag)),
            row(txt(f'HP[{hp_b}] {enemy.health}/{enemy.max_health}', hcol)),
            row(txt(f'AP[{ap_b}] {enemy.current_ap}/{enemy.max_ap}', 'ap')),
            row(txt(f'[{st}]' if st else '', 'yellow')),
        ]

        for art_line in ENEMY_ART.get(enemy.name, [])[:4]:
            rows.append(row(txt(art_line, 'dim')))

        return rows

    # ── Explore art ───────────────────────────────────────────────────────────

    def _draw_explore(self, t, s):
        try:
            from utils.ascii_art import ROOM_ART
        except ImportError:
            ROOM_ART = {}

        room = s.room
        if not room:
            return

        desc = str(getattr(room, "description", "")).strip()
        if desc:
            for ln in desc.splitlines()[:3]:
                t.insert('end', f'  {ln}\n', 'white')
            t.insert('end', '\n')

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
            t.insert('end', ', '.join(_stacked_items(room.items)) + '\n', 'white')
        ev = getattr(room, 'event', None)
        if ev and not getattr(ev, 'resolved', True):
            t.insert('end', '  Event:    ', 'bold')
            t.insert('end', ev.name + '  (interact)\n', 'cyan')
        pz = getattr(room, 'puzzle', None)
        if pz and not pz.solved:
            t.insert('end', '  Puzzle:   ', 'bold')
            t.insert('end', pz.name + '  (examine / solve)\n', 'magenta')

        exits  = list(room.connections.keys())
        locked = room.locked_connections
        exs    = [f'{d}🔒' if d in locked else d for d in exits]
        t.insert('end', '  Exits:    ', 'bold')
        t.insert('end', ', '.join(exs) + '\n', 'green')

    # ── STATUS / HUD ──────────────────────────────────────────────────────────

    def _refresh_hud(self):
        c = self._hud_canvas
        c.delete('all')
        p = self._state.player
        if not p:
            return

        try:
            from utils.constants import MAX_AP, BASE_COMMANDS, HEAL_MP_COST
            from utils.status_effects import format_statuses
            from entities.class_data import get_command_def, cmd_ap_cost as _apc
        except ImportError:
            return

        W   = max(c.winfo_width(), 700)
        pad = 10

        label_w = 26
        value_w = 46
        min_bar = 70
        min_step = label_w + min_bar + value_w
        available = max(min_step * 3, W - pad * 2 - 16)
        step = available // 3
        bar_w = max(min_bar, step - label_w - value_w)
        step = label_w + bar_w + value_w
        bar_h = 14
        y1    = 8

        def _bar(x, label, cur, mx, fill_col, txt_col=None):
            txt_col = txt_col or fill_col
            c.create_text(x, y1 + bar_h // 2, text=label,
                          fill=self.C_DIM, font=self.FONT_SM, anchor='w')
            bx = x + 26
            c.create_rectangle(bx, y1, bx + bar_w, y1 + bar_h,
                               fill=self.C_SEP, outline='')
            fw = max(0, int((cur / max(mx, 1)) * bar_w))
            if fw:
                c.create_rectangle(bx, y1, bx + fw, y1 + bar_h,
                                   fill=fill_col, outline='')
            c.create_text(bx + bar_w + 4, y1 + bar_h // 2,
                          text=f'{cur}/{mx}', fill=txt_col,
                          font=self.FONT_SM, anchor='w')

        hpct = p.health / max(p.max_health, 1)
        hfil = self.C_GREEN if hpct > 0.5 else (self.C_YELLOW if hpct > 0.25 else self.C_RED)

        _bar(pad,          'HP', p.health,     p.max_health, hfil)
        _bar(pad + step,   'AP', p.current_ap, MAX_AP,       self.C_AP)
        _bar(pad + step*2, 'MP', p.mana,        p.max_mana,   self.C_MP)

        c.create_text(W - pad, y1 + bar_h // 2,
                      text=f'Lv{p.level}  XP {p.xp}  Gold {getattr(p, "gold", 0)}',
                      fill=self.C_GOLD, font=self.FONT_SM, anchor='e')

        y2  = y1 + bar_h + 8
        st  = _strip(format_statuses(p))
        rls = '  ·  '.join(r.name for r in p.relics)
        mid = '  '.join(filter(None, [st, rls]))
        if mid:
            c.create_text(pad, y2 + 6, text=mid[:130],
                          fill=self.C_DIM, font=self.FONT_SM, anchor='w')

        y3   = y2 + 18
        base = (f"attack({BASE_COMMANDS['attack']['ap_cost']}) "
                f"heal({BASE_COMMANDS['heal']['ap_cost']}+{HEAL_MP_COST}MP) "
                f"block({BASE_COMMANDS['block']['ap_cost']})")
        kp = []
        for cn in sorted(p.known_commands)[:12]:
            d = get_command_def(p.char_class, cn)
            kp.append(f'{cn}({_apc(d) if d else len(cn)})')
        if kp:
            base += '  │  ' + ' '.join(kp)
        c.create_text(pad, y3 + 6, text=base[:170],
                      fill=self.C_DIM, font=self.FONT_SM, anchor='w')

    # ── LOG ───────────────────────────────────────────────────────────────────

    def _append_log(self, line: str):
        t = self._log_txt
        t.configure(state='normal')
        self._insert_ansi(t, line + '\n')
        t.configure(state='disabled')
        t.see('end')

    def _insert_ansi(self, widget, text: str):
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
                        active = [t for t in active if t not in _CODE_TAG.values()]
                        active.append(_CODE_TAG[code])
            elif part:
                widget.insert('end', part, tuple(active) if active else ())

    # ── Input ─────────────────────────────────────────────────────────────────

    def _handle_input(self, prompt: str) -> str:
        self._input_event.clear()
        self._input_result = ''
        clean = _strip(prompt).strip()

        self._schedule(lambda: self._prompt_lbl.configure(
            text=f'  {clean}  ' if clean else '>  '))

        _cont = ('press enter', 'continue', 'enter to', 'enter...')
        if clean.lower() and any(kw in clean.lower() for kw in _cont):
            self._schedule(lambda: self._append_log(f'  ── {clean} ──'))

        self._schedule(self._refresh_hud)
        self._input_event.wait()
        result = self._input_result

        if result.strip():
            self._schedule(lambda r=result: (
                self._log_txt.configure(state='normal'),
                self._log_txt.insert('end', f'  › {r}\n', ('input',)),
                self._log_txt.configure(state='disabled'),
                self._log_txt.see('end'),
            ))
        return result

    def _on_enter(self, _event=None):
        val = self._input_var.get()
        self._input_var.set('')
        self._input_result = val
        self._input_event.set()
        self._input_ent.focus_set()
        return 'break'

    # ── Misc ──────────────────────────────────────────────────────────────────

    def _schedule(self, fn):
        if self._root:
            self._root.after(0, fn)

    def _game_thread(self, game_fn):
        try:
            game_fn()
        except SystemExit:
            pass
        except Exception as exc:
            self._schedule(lambda err=exc: self._append_log(f'\n  [Error: {err}]'))
        finally:
            self._input_result = ''
            self._input_event.set()

    def _on_close(self):
        self._input_result = ''
        self._input_event.set()
        if self._root:
            self._root.destroy()
        sys.exit(0)


window = GameWindow()
