# game/window.py
"""
GameWindow — standalone Tkinter window, 4 panels.

┌─ ART ─────────────────────────────────────────────┐
│  Combat: enemies SIDE-BY-SIDE in monospace cols   │
│  Explore: room art                                │
├─ STATUS ──────────────────────────────────────────┤
│  HP / AP / MP bars  ·  xp level ·  commands       │
├─ LOG ─────────────────────────────────────────────┤
│  Scrolling story / combat output                  │
├─ INPUT ───────────────────────────────────────────┤
│  > _                                              │
└──────────────────────────────────────────────────┘
"""

import re
import sys
import traceback
import threading
import tkinter as tk
from collections import deque, Counter
from pathlib import Path

# ---------- ANSI helpers ----------
_ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')
_ANSI_SPLIT = re.compile(r'(\x1b\[[0-9;]*m)')

def _strip(s: str) -> str:
    return _ANSI_RE.sub('', str(s))

def _stacked_items(items):
    counts = Counter(items)
    return [f"{count} x {name}" if count > 1 else name for name, count in counts.items()]

def _move_hint(move):
    hint = getattr(move, "intent_hint", "")
    return f" {hint}" if hint else ""

# ANSI colour code mapping
_CODE_TAG = {
    '31': 'red',    '32': 'green',   '33': 'yellow',
    '34': 'blue',   '35': 'magenta', '36': 'cyan',
    '37': 'white',  '90': 'gray',    '94': 'blue',
}

# ---------- simple bar helper ----------
def _make_bar(cur, max_val, width, fill='█', empty='░'):
    if max_val <= 0:
        return empty * width
    filled = int(round((cur / max_val) * width))
    return fill * filled + empty * (width - filled)

# ---------- simple status effect formatter ----------
def _format_statuses(entity):
    if not hasattr(entity, 'effects') or not entity.effects:
        return ""
    active = entity.effects.get_all()
    if not active:
        return ""
    parts = []
    for eff in active:
        dur = "∞" if eff.duration < 0 else str(eff.duration)
        parts.append(f"{eff.name}({dur})")
    return ", ".join(parts)

def _is_stunned(entity):
    return hasattr(entity, 'effects') and entity.effects.has("stunned")

# ---------- UIState ----------
class UIState:
    __slots__ = ('player', 'room', 'enemies', 'mode')
    def __init__(self):
        self.player = None
        self.room = None
        self.enemies = []
        self.mode = 'explore'

    def set_explore(self, player, room):
        self.player = player
        self.room = room
        self.mode = 'explore'
        self.enemies = []

    def set_combat(self, player, room, enemies):
        self.player = player
        self.room = room
        self.mode = 'combat'
        self.enemies = list(enemies)

# ---------- GameWindow ----------
class GameWindow:
    # Black palette
    C_BG      = '#000000'
    C_PANEL   = '#111111'
    C_BORDER  = '#222222'
    C_SEP     = '#1a1a1a'
    C_TEXT    = '#cccccc'
    C_DIM     = '#666666'
    C_HP      = '#ff4444'
    C_AP      = '#4488ff'
    C_MP      = '#aa44ff'
    C_GOLD    = '#ffcc44'
    C_RED     = '#ff4444'
    C_GREEN   = '#44ff88'
    C_YELLOW  = '#ffcc44'
    C_BLUE    = '#4488ff'
    C_CYAN    = '#44ffcc'
    C_MAGENTA = '#ff44cc'
    C_GRAY    = '#666666'
    C_WHITE   = '#cccccc'

    # Fonts: separate sizes for different panels
    FONT     = ('Courier New', 9)       # input, general
    FONT_B   = ('Courier New', 9, 'bold')
    FONT_SM  = ('Courier New', 6)       # ART panel in explore mode
    FONT_COMBAT = ('Courier New', 10, 'bold')  # ART panel in combat mode for readability
    FONT_LOG = ('Courier New', 12)      # LOG panel - larger
    FONT_XS  = ('Courier New', 9)       # STATUS panel

    _TAGS = {
        'bold':    {'font': ('Courier New', 9, 'bold')},
        'dim':     {'foreground': '#666666'},
        'red':     {'foreground': '#ff4444'},
        'green':   {'foreground': '#44ff88'},
        'yellow':  {'foreground': '#ffcc44'},
        'blue':    {'foreground': '#4488ff'},
        'magenta': {'foreground': '#ff44cc'},
        'cyan':    {'foreground': '#44ffcc'},
        'gray':    {'foreground': '#666666'},
        'white':   {'foreground': '#cccccc'},
        'input':   {'foreground': '#ffcc44'},
        'ap':      {'foreground': '#4488ff'},
        'mp':      {'foreground': '#aa44ff'},
        'hp_good': {'foreground': '#44ff88'},
        'hp_mid':  {'foreground': '#ffcc44'},
        'hp_low':  {'foreground': '#ff4444'},
    }

    def __init__(self):
        self._state = UIState()
        self._log = deque(maxlen=600)
        self._input_event = threading.Event()
        self._input_result = ''
        self._active = False
        self._root = None
        self._char_width = None   # will be computed lazily
        self._art_font_mode = None

    # Public API ------------------------------------------------------------
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

    def update_art(self, content: str):
        """Manually replace content in the ART panel."""
        self._schedule(lambda c=content: self._set_art_text(c))

    def update_status(self):
        """Refresh current player/room status."""
        self._schedule(self._refresh_hud)

    def append_log(self, text: str):
        """Append text to the LOG panel."""
        for line in str(text).splitlines():
            self._log.append(line)
            self._schedule(lambda ln=line: self._append_log(ln))

    def get_input(self, prompt: str = '') -> str:
        """Get input from the INPUT panel."""
        self._input_event.clear()
        self._input_result = ''
        clean = _strip(prompt).strip()
        self._schedule(lambda: self._prompt_lbl.configure(
            text=f'  {clean}  ' if clean else '>  '))
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

    def run_game(self, game_fn):
        """Run the game loop."""
        self._build_window()
        t = threading.Thread(target=self._game_thread, args=(game_fn,), daemon=True)
        t.start()
        self._root.mainloop()

    # Window construction ----------------------------------------------------
    def _build_window(self):
        root = tk.Tk()
        root.title('Text Adventure')
        root.configure(bg=self.C_BG)
        # Smaller default geometry, will be overridden by zoomed state
        root.geometry('800x600')
        root.minsize(720, 540)
        root.protocol('WM_DELETE_WINDOW', self._on_close)
        # Auto full screen (maximized)
        try:
            root.state('zoomed')
        except tk.TclError:
            try:
                root.attributes('-fullscreen', True)
            except tk.TclError:
                pass
        self._root = root

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=2)
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

    # Panel 1 — ART ---------------------------------------------------------
    def _build_art(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=0, column=0, sticky='nsew', padx=4, pady=(4, 0))
        frm.columnconfigure(0, weight=1)

        self._art_hdr = self._hdr(frm, 0, 'EXPLORE', self.C_CYAN)

        self._art_txt = tk.Text(
            frm, height=49, bg=self.C_PANEL, fg=self.C_TEXT,
            font=self.FONT_SM, bd=0, relief='flat',
            state='disabled', wrap='none', cursor='arrow',
        )
        self._art_txt.grid(row=1, column=0, sticky='nsew')
        self._apply_tags(self._art_txt)
        self._art_txt.bind('<Configure>',
                           lambda _: self._schedule(self._refresh_art))

    # Panel 2 — STATUS ------------------------------------------------------
    def _build_status(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=1, column=0, sticky='nsew', padx=4, pady=(2, 0))
        frm.columnconfigure(0, weight=1)

        self._status_hdr = self._hdr(frm, 0, 'STATUS', self.C_GREEN)

        # Increased height to accommodate larger status font
        self._hud_canvas = tk.Canvas(
            frm, height=80, bg=self.C_PANEL,
            bd=0, relief='flat', highlightthickness=0,
        )
        self._hud_canvas.grid(row=1, column=0, sticky='ew')
        self._hud_canvas.bind('<Configure>',
                              lambda _: self._schedule(self._refresh_hud))

    # Panel 3 — LOG ---------------------------------------------------------
    def _build_log(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=2, column=0, sticky='nsew', padx=4, pady=(2, 0))
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(1, weight=1)

        self._log_hdr = self._hdr(frm, 0, 'LOG', self.C_BLUE)

        # Use the larger FONT_LOG for the log text widget
        self._log_txt = tk.Text(
            frm, bg=self.C_PANEL, fg=self.C_TEXT,
            font=self.FONT_LOG, bd=0, relief='flat',
            state='disabled', wrap='word',
        )
        sb = tk.Scrollbar(frm, command=self._log_txt.yview,
                          bg=self.C_BORDER, troughcolor=self.C_SEP,
                          relief='flat', bd=0)
        self._log_txt.configure(yscrollcommand=sb.set)
        self._log_txt.grid(row=1, column=0, sticky='nsew')
        sb.grid(row=1, column=1, sticky='ns')
        self._apply_tags(self._log_txt)

    # Panel 4 — INPUT -------------------------------------------------------
    def _build_input(self, root):
        frm = tk.Frame(root, bg=self.C_BG)
        frm.grid(row=3, column=0, sticky='nsew', padx=4, pady=(2, 4))
        frm.columnconfigure(1, weight=1)

        self._input_hdr = self._hdr(frm, 0, 'INPUT', self.C_MAGENTA)

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

    # ART panel -------------------------------------------------------------
    def _refresh_art(self):
        t = self._art_txt
        t.configure(state='normal')
        t.delete('1.0', 'end')
        s = self._state
        if s.mode == 'combat':
            self._set_art_font(self.FONT_COMBAT, mode='combat')
            self._art_hdr.configure(text='  ⚔  COMBAT', fg=self.C_YELLOW)
            self._draw_combat(t, s)
        else:
            self._set_art_font(self.FONT_SM, mode='explore')
            name = s.room.name if s.room else '…'
            self._art_hdr.configure(text=f'  {name}', fg=self.C_CYAN)
            self._draw_explore(t, s)
        t.configure(state='disabled')

    def _set_art_font(self, font, mode: str):
        """Apply a font to ART panel and reset cached width if changed."""
        if self._art_font_mode != mode:
            self._art_txt.configure(font=font)
            self._char_width = None
            self._art_font_mode = mode

    def _set_art_text(self, content: str):
        """Internal: Set raw art text."""
        t = self._art_txt
        t.configure(state='normal')
        t.delete('1.0', 'end')
        t.insert('end', content, 'white')
        t.configure(state='disabled')

    # SIDE-BY-SIDE combat ---------------------------------------------------
    def _get_char_width(self):
        """Return pixel width of a monospace character in the art Text widget."""
        if self._char_width is None:
            import tkinter.font as tkfont
            font_obj = tkfont.Font(font=self._art_txt['font'])
            self._char_width = font_obj.measure('0')
            if self._char_width <= 0:
                self._char_width = 5   # fallback
        return self._char_width

    def _draw_combat(self, t, s):
        alive = [e for e in s.enemies if e.is_alive and not getattr(e, 'fled', False)]
        if not alive:
            t.insert('end', '\n  ✦ All enemies defeated!\n', 'green')
            return

        n = len(alive)
        ch_px = self._get_char_width()
        px_w = max(t.winfo_width(), 480)
        total = px_w // ch_px - 4
        gap = 2
        col_w = max(26, (total - gap * (n - 1)) // n)

        cards = [self._enemy_card_rows(i, e, col_w) for i, e in enumerate(alive, start=1)]
        height = max(len(c) for c in cards)

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
                pad = max(0, col_w - used)
                if pad:
                    t.insert('end', ' ' * pad)
                if ci < n - 1:
                    t.insert('end', ' ' * gap)
            t.insert('end', '\n')

    def _enemy_card_rows(self, idx, enemy, col_w):
        hpct = enemy.current_hp / max(enemy.max_hp, 1)
        hcol = 'hp_good' if hpct > 0.5 else ('hp_mid' if hpct > 0.25 else 'hp_low')
        bw = max(6, min(12, col_w - 15))
        hp_bar = _make_bar(enemy.current_hp, enemy.max_hp, bw)
        ap_bar = _make_bar(getattr(enemy, 'current_ap', 0), getattr(enemy, 'total_ap', 18), 6, '◆', '◇')

        if _is_stunned(enemy):
            intent, itag = '→ ⚡STUNNED', 'yellow'
        elif hasattr(enemy, 'active_intents') and enemy.active_intents:
            m0 = enemy.active_intents[0]
            extra = f'+{len(enemy.active_intents)-1}' if len(enemy.active_intents) > 1 else ''
            intent, itag = f'→{m0.id}({m0.ap_cost}){_move_hint(m0)}{extra}', 'red'
        else:
            intent, itag = '→ ???', 'dim'

        st = _strip(_format_statuses(enemy))

        def row(*segs):
            return list(segs)

        def txt(s, tag='', width=col_w):
            return (s[:width].ljust(width), tag)

        art_lines = self._load_enemy_art(enemy)
        rows = [
            row(txt(f'[{idx}] {enemy.name}', 'bold')),
            *[row(txt(line, 'white')) for line in art_lines],
            row(txt(intent, itag)),
            row(txt(f'HP[{hp_bar}] {enemy.current_hp}/{enemy.max_hp}', hcol)),
            row(txt(f'AP[{ap_bar}] {getattr(enemy, "current_ap", 0)}/{getattr(enemy, "total_ap", 18)}', 'ap')),
            row(txt(f'[{st}]' if st else '', 'yellow')),
        ]
        return rows

    def _load_enemy_art(self, enemy) -> list[str]:
        inline = str(getattr(enemy, "ascii_art", "") or "").strip("\n")
        if inline.strip():
            return inline.splitlines()[:4]

        enemy_id = str(getattr(enemy, "template_id", "") or "").strip()
        if enemy_id:
            base = Path("assets") / "enemies"
            txt_path = base / f"{enemy_id}.txt"
            if txt_path.is_file():
                try:
                    content = txt_path.read_text(encoding="utf-8").strip("\n")
                    if content.strip():
                        return content.splitlines()[:4]
                except OSError:
                    pass

        return ["?"]

    # Explore art -----------------------------------------------------------
    def _load_room_art(self, room_id: str) -> str | None:
        base = Path("assets") / "rooms"
        for path in base.rglob(f"{room_id}.txt"):
            if path.is_file():
                try:
                    return path.read_text(encoding="utf-8").rstrip("\n")
                except OSError:
                    pass
        return None

    def _draw_explore(self, t, s):
        room = s.room
        if not room:
            return

        art = self._load_room_art(room.id)
        if art:
            for line in art.splitlines():
                t.insert('end', f'  {line}\n', 'white')
            t.insert('end', '\n')
        else:
            t.insert('end', '  ?\n\n', 'white')

        alive = [e for e in getattr(room, 'enemies', []) if e.is_alive]
        if alive:
            t.insert('end', '  Enemies:  ', 'bold')
            t.insert('end', ', '.join(e.name for e in alive) + '\n', 'red')
        if hasattr(room, 'items_on_ground') and room.items_on_ground:
            t.insert('end', '  Items:    ', 'bold')
            t.insert('end', ', '.join(_stacked_items(room.items_on_ground)) + '\n', 'white')
        if hasattr(room, 'objects') and room.objects:
            visible = [obj.name for obj in room.objects.values() if not obj.hidden]
            if visible:
                t.insert('end', '  Objects:  ', 'bold')
                t.insert('end', ', '.join(visible) + '\n', 'cyan')

    # STATUS / HUD ----------------------------------------------------------
    def _refresh_hud(self):
        c = self._hud_canvas
        c.delete('all')
        p = self._state.player
        if not p:
            return

        W = max(c.winfo_width(), 700)
        pad = 8
        y1 = 8
        bar_h = 14

        label_w = 24
        value_w = 42
        min_bar = 65
        min_step = label_w + min_bar + value_w
        available = max(min_step * 3, W - pad * 2 - 12)
        step = available // 3
        bar_w = max(min_bar, step - label_w - value_w)
        font_size = self.FONT_XS

        def _bar(x, label, cur, mx, fill_col, txt_col=None):
            txt_col = txt_col or fill_col
            c.create_text(x, y1 + bar_h // 2, text=label,
                          fill=self.C_DIM, font=font_size, anchor='w')
            bx = x + 24
            c.create_rectangle(bx, y1, bx + bar_w, y1 + bar_h,
                               fill=self.C_SEP, outline='')
            fw = max(0, int((cur / max(mx, 1)) * bar_w))
            if fw:
                c.create_rectangle(bx, y1, bx + fw, y1 + bar_h,
                                   fill=fill_col, outline='')
            c.create_text(bx + bar_w + 3, y1 + bar_h // 2,
                          text=f'{cur}/{mx}', fill=txt_col,
                          font=font_size, anchor='w')

        hpct = p.current_hp / max(p.max_hp, 1)
        hfil = self.C_GREEN if hpct > 0.5 else (self.C_YELLOW if hpct > 0.25 else self.C_RED)

        _bar(pad,          'HP', p.current_hp, p.max_hp, hfil)
        _bar(pad + step,   'AP', p.current_ap, getattr(p, 'total_ap', 20), self.C_AP)
        _bar(pad + step*2, 'MP', getattr(p, 'mana', 0), getattr(p, 'max_mana', 0), self.C_MP)

        c.create_text(W - pad, y1 + bar_h // 2,
                      text=f'Lv{p.level}  XP {p.xp}  Gold {getattr(p, "gold", 0)}',
                      fill=self.C_GOLD, font=font_size, anchor='e')

        y2 = y1 + bar_h + 8
        st = _strip(_format_statuses(p))
        rls = '  ·  '.join(getattr(p, 'relics', []))
        mid = '  '.join(filter(None, [st, rls]))
        if mid:
            c.create_text(pad, y2 + 5, text=mid[:120],
                          fill=self.C_DIM, font=font_size, anchor='w')

        y3 = y2 + 16
        base = "attack heal block"
        if hasattr(p, 'unlocked_commands') and p.unlocked_commands:
            cmds = sorted(p.unlocked_commands)[:10]
            base += '  │  ' + ' '.join(cmds[:8])
        c.create_text(pad, y3 + 5, text=base[:150],
                      fill=self.C_DIM, font=font_size, anchor='w')

    # LOG -------------------------------------------------------------------
    def _append_log(self, line: str):
        t = self._log_txt
        t.configure(state='normal')
        self._insert_ansi(t, line + '\n')
        t.configure(state='disabled')
        t.see('end')

    def _insert_ansi(self, widget, text: str):
        parts = _ANSI_SPLIT.split(text)
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

    # Input -----------------------------------------------------------------
    def _on_enter(self, _event=None):
        val = self._input_var.get()
        self._input_var.set('')
        self._input_result = val
        self._input_event.set()
        self._input_ent.focus_set()
        return 'break'

    # Misc ------------------------------------------------------------------
    def _schedule(self, fn):
        if self._root:
            self._root.after(0, fn)

    def _game_thread(self, game_fn):
        try:
            game_fn()
        except SystemExit:
            pass
        except Exception:
            tb_str = traceback.format_exc()
            last_frame = traceback.extract_tb(sys.exc_info()[2])[-1]
            exc = sys.exc_info()[1]
            short = (
                f"{type(exc).__name__}: {exc}\n"
                f"  File: {last_frame.filename}, "
                f"Line {last_frame.lineno}: {last_frame.line}"
            )
            self._schedule(lambda msg=short: self._append_log(f'\n  [Error]\n  {msg}'))
            print(tb_str, file=sys.stderr)
        finally:
            self._input_result = ''
            self._input_event.set()

    def _on_close(self):
        self._input_result = ''
        self._input_event.set()
        if self._root:
            self._root.destroy()
        sys.exit(0)

# Global instance
window = GameWindow()
