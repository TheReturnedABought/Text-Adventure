# game/window.py
"""GameWindow — Tkinter 4-panel UI: ART / STATUS / LOG / INPUT"""
import re, sys, traceback, threading, tkinter as tk
from pathlib import Path
from collections import deque, Counter

_ANSI_RE    = re.compile(r'\x1b\[[0-9;]*m')
_ANSI_SPLIT = re.compile(r'(\x1b\[[0-9;]*m)')
_CODE_TAG   = {'31':'red','32':'green','33':'yellow','34':'blue',
               '35':'magenta','36':'cyan','37':'white','90':'gray','94':'blue'}

def _strip(s):          return _ANSI_RE.sub('', str(s))
def _bar(v,mx,w,f='█',e='░'): n=int(round(v/max(mx,1)*w)) if mx else 0; return f*n+e*(w-n)
def _stacked(items):    return [f"{n} x {k}" if n>1 else k for k,n in Counter(items).items()]
def _stunned(e):        return hasattr(e,'effects') and e.effects.has("stunned")
def _statuses(e):
    return ", ".join(f"{x.name}({x.duration if x.duration>=0 else '∞'})"
                     for x in (e.effects.get_all() if hasattr(e,'effects') else []))

_P = dict(bg='#000000',panel='#111111',border='#222222',sep='#1a1a1a',
          text='#cccccc',dim='#666666',gold='#ffcc44',ap='#4488ff',mp='#aa44ff',
          red='#ff4444',green='#44ff88',yellow='#ffcc44',blue='#4488ff',
          cyan='#44ffcc',magenta='#ff44cc',gray='#666666',white='#cccccc')
_F = {'n':('Courier New',9),'b':('Courier New',9,'bold'),'sm':('Courier New',6),
      'com':('Courier New',10,'bold'),'log':('Courier New',12),'xs':('Courier New',11)}

_TAG_DEFS = [('bold',None,True),('dim','#666666',False),('red','#ff4444',False),
             ('green','#44ff88',False),('yellow','#ffcc44',False),('blue','#4488ff',False),
             ('magenta','#ff44cc',False),('cyan','#44ffcc',False),('gray','#666666',False),
             ('white','#cccccc',False),('input','#ffcc44',False),('ap','#4488ff',False),
             ('mp','#aa44ff',False),('hp_good','#44ff88',False),('hp_mid','#ffcc44',False),
             ('hp_low','#ff4444',False)]

def _apply_tags(w):
    for name,fg,bold in _TAG_DEFS:
        opts=({'font':_F['b']} if bold else {})
        if fg: opts['foreground']=fg
        w.tag_configure(name,**opts)

class UIState:
    __slots__ = ('player','room','enemies','mode','world','turn')
    def __init__(self):     self.player=self.room=self.world=None; self.enemies=[]; self.mode='explore'; self.turn=0
    def set_explore(self,p,r,w=None): self.player,self.room,self.mode,self.enemies,self.world=p,r,'explore',[],w
    def set_combat(self,p,r,es,w=None): self.player,self.room,self.mode,self.enemies,self.world=p,r,'combat',list(es),w

class GameWindow:
    def __init__(self):
        self._state=UIState(); self._log=deque(maxlen=600)
        self._input_event=threading.Event(); self._input_result=''
        self._root=self._char_width=self._art_font_mode=None; self._art_cache={}

    # ── public API ───────────────────────────────────────────────────────────
    def set_explore(self,p,r,w=None):   self._state.set_explore(p,r,w);   self._redraw()
    def set_combat(self,p,r,es,w=None): self._state.set_combat(p,r,es,w); self._redraw()
    def refresh(self):                  self._redraw()
    def set_turn(self,n):               self._state.turn=n; self._schedule(self._refresh_hud)
    def update_status(self):            self._schedule(self._refresh_hud)
    def update_art(self,content):
        def _do(c=content):
            self._art_txt.configure(state='normal'); self._art_txt.delete('1.0','end')
            self._art_txt.insert('end',c,'white'); self._art_txt.configure(state='disabled')
        self._schedule(_do)
    def append_log(self,text):
        for ln in str(text).splitlines():
            self._log.append(ln); self._schedule(lambda l=ln: self._append_log(l))
    def get_input(self,prompt=''):
        self._input_event.clear(); self._input_result=''
        self._schedule(lambda: self._prompt_lbl.configure(
            text=f'  {_strip(prompt).strip()}  ' if prompt.strip() else '>  '))
        self._schedule(self._refresh_hud); self._input_event.wait()
        r=self._input_result
        if r.strip():
            self._schedule(lambda v=r: (self._log_txt.configure(state='normal'),
                self._log_txt.insert('end',f'  › {v}\n',('input',)),
                self._log_txt.configure(state='disabled'), self._log_txt.see('end')))
        return r
    def run_game(self,fn):
        self._build_window()
        threading.Thread(target=self._game_thread,args=(fn,),daemon=True).start()
        self._root.mainloop()

    # ── build ────────────────────────────────────────────────────────────────
    def _build_window(self):
        r=tk.Tk(); r.title('Text Adventure'); r.configure(bg=_P['bg'])
        r.geometry('800x600'); r.minsize(720,540)
        r.protocol('WM_DELETE_WINDOW',self._on_close)
        try: r.state('zoomed')
        except tk.TclError:
            try: r.attributes('-fullscreen',True)
            except tk.TclError: pass
        self._root=r; r.columnconfigure(0,weight=1)
        for i,w in enumerate([2,0,1,0]): r.rowconfigure(i,weight=w)

        def hdr(f,row,txt,col):
            l=tk.Label(f,text=f'  {txt}',bg=_P['border'],fg=col,font=_F['b'],anchor='w',padx=6,pady=6)
            l.grid(row=row,column=0,columnspan=2,sticky='ew'); return l
        def panel(row,pad=(2,0)):
            f=tk.Frame(r,bg=_P['bg']); f.grid(row=row,column=0,sticky='nsew',padx=4,pady=pad)
            f.columnconfigure(0,weight=1); return f

        f=panel(0,(4,0)); self._art_hdr=hdr(f,0,'EXPLORE',_P['cyan'])
        self._art_txt=tk.Text(f,height=49,bg=_P['panel'],fg=_P['text'],font=_F['sm'],
                              bd=0,state='disabled',wrap='none',cursor='arrow')
        self._art_txt.grid(row=1,column=0,sticky='nsew'); _apply_tags(self._art_txt)
        self._art_txt.bind('<Configure>',lambda _:self._schedule(self._refresh_art))

        f=panel(1); hdr(f,0,'STATUS',_P['green'])
        self._hud_canvas=tk.Canvas(f,height=130,bg=_P['panel'],bd=0,highlightthickness=0)
        self._hud_canvas.grid(row=1,column=0,sticky='ew')
        self._hud_canvas.bind('<Configure>',lambda _:self._schedule(self._refresh_hud))

        f=panel(2); f.rowconfigure(1,weight=1); hdr(f,0,'LOG',_P['blue'])
        self._log_txt=tk.Text(f,bg=_P['panel'],fg=_P['text'],font=_F['log'],
                              bd=0,state='disabled',wrap='word')
        sb=tk.Scrollbar(f,command=self._log_txt.yview,bg=_P['border'],
                        troughcolor=_P['sep'],relief='flat',bd=0)
        self._log_txt.configure(yscrollcommand=sb.set)
        self._log_txt.grid(row=1,column=0,sticky='nsew'); sb.grid(row=1,column=1,sticky='ns')
        _apply_tags(self._log_txt)

        f=panel(3,(2,4)); f.columnconfigure(0,weight=0); f.columnconfigure(1,weight=1); hdr(f,0,'INPUT',_P['magenta'])
        self._prompt_lbl=tk.Label(f,text='>  ',bg=_P['panel'],fg=_P['gold'],font=_F['b'],padx=6)
        self._prompt_lbl.grid(row=1,column=0,sticky='w')
        self._input_var=tk.StringVar()
        self._input_ent=tk.Entry(f,textvariable=self._input_var,bg=_P['panel'],fg=_P['text'],
                                 insertbackground=_P['text'],font=_F['n'],relief='flat',bd=4)
        self._input_ent.grid(row=1,column=1,sticky='ew',padx=(0,6),pady=4)
        self._input_ent.bind('<Return>',self._on_enter); self._input_ent.focus_set()

    # ── art ──────────────────────────────────────────────────────────────────
    def _redraw(self): self._schedule(self._refresh_art); self._schedule(self._refresh_hud)

    def _refresh_art(self):
        t,s=self._art_txt,self._state; t.configure(state='normal'); t.delete('1.0','end')
        if s.mode=='combat':
            if self._art_font_mode!='combat':
                t.configure(font=_F['com']); self._char_width=None; self._art_font_mode='combat'
            self._art_hdr.configure(text='  ⚔  COMBAT',fg=_P['yellow']); self._draw_combat(t,s)
        else:
            if self._art_font_mode!='explore':
                t.configure(font=_F['sm']); self._char_width=None; self._art_font_mode='explore'
            self._art_hdr.configure(text=f'  {s.room.name if s.room else "…"}',fg=_P['cyan'])
            self._draw_explore(t,s)
        t.configure(state='disabled')

    def _char_px(self):
        if self._char_width is None:
            import tkinter.font as tkf
            self._char_width=tkf.Font(font=self._art_txt['font']).measure('0') or 5
        return self._char_width

    def _draw_combat(self,t,s):
        alive=[e for e in s.enemies if e.is_alive and not getattr(e,'fled',False)]
        if not alive: t.insert('end','\n  ✦ All enemies defeated!\n','green'); return
        n=len(alive); col=max(26,(max(t.winfo_width(),480)//self._char_px()-4-2*(n-1))//n)
        cards=[self._enemy_card(i,e,col) for i,e in enumerate(alive,1)]
        h=max(len(c) for c in cards)
        for c in cards:
            while len(c)<h: c.append([(' '*col,'')])
        t.insert('end','\n')
        for ri in range(h):
            t.insert('end','  ')
            for ci,card in enumerate(cards):
                used=0
                for txt,tag in card[ri]:
                    t.insert('end',txt,(tag,) if tag else ()); used+=len(txt)
                if max(0,col-used): t.insert('end',' '*(col-used))
                if ci<n-1: t.insert('end','  ')
            t.insert('end','\n')

    def _enemy_card(self,idx,e,col):
        hpct=e.current_hp/max(e.max_hp,1)
        hcol='hp_good' if hpct>0.5 else('hp_mid' if hpct>0.25 else 'hp_low')
        bw=max(6,min(12,col-15)); row=lambda s,tg='':[(s[:col].ljust(col),tg)]
        hp_b=_bar(e.current_hp,e.max_hp,bw)
        ap_b=_bar(getattr(e,'current_ap',0),getattr(e,'total_ap',18),6,'◆','◇')
        if _stunned(e): intent,itag='→ ⚡STUNNED','yellow'
        elif hasattr(e,'active_intents') and e.active_intents:
            m=e.active_intents[0]; hint=getattr(m,'intent_hint','')
            extra=f'+{len(e.active_intents)-1}' if len(e.active_intents)>1 else ''
            intent,itag=f'→{m.id}({m.ap_cost}){" "+hint if hint else ""}{extra}','red'
        else: intent,itag='→ ???','dim'
        crest=''
        if getattr(e,'art_asset',None):
            art=self._load_art(getattr(e,'template_id',None) or e.name.lower(),e.art_asset)
            if art: crest=art.splitlines()[0].strip()[:8]
        title=f'[{idx}] {e.name}'+(' '+crest if crest else ''); st=_strip(_statuses(e))
        rows=[row(title,'bold'),row(intent,itag),
              row(f'HP[{hp_b}] {e.current_hp}/{e.max_hp}',hcol),
              row(f'AP[{ap_b}] {getattr(e,"current_ap",0)}/{getattr(e,"total_ap",18)}','ap'),
              row(f"Room: {getattr(e,'combat_room_id','unknown')}",'dim'),
              row(f"Move: {getattr(e,'movement_hint','?')}",'cyan')]
        if st: rows.append(row(f'[{st}]','yellow'))
        return rows

    def _load_art(self,room_id,art_asset=None):
        if art_asset:
            p=Path(art_asset) if Path(art_asset).is_absolute() else Path.cwd()/art_asset
            k=str(p.resolve())
            if k not in self._art_cache and p.is_file():
                try: self._art_cache[k]=p.read_text('utf-8').rstrip('\n')
                except OSError: pass
            return self._art_cache.get(k)
        for p in (Path('assets')/'rooms').rglob(f'{room_id}.txt'):
            k=str(p.resolve())
            if k not in self._art_cache:
                try: self._art_cache[k]=p.read_text('utf-8').rstrip('\n')
                except OSError: pass
            return self._art_cache.get(k)
        return None

    def _draw_explore(self,t,s):
        room=s.room
        if not room: return
        art=self._load_art(room.id,getattr(room,'art_asset',None))
        if art:
            for ln in art.splitlines(): t.insert('end',f'  {ln}\n','white')
            t.insert('end','\n')
        else:
            desc=str(getattr(room,'description','')).strip()
            for ln in desc.splitlines()[:3]: t.insert('end',f'  {ln}\n','white')
            if desc: t.insert('end','\n')
        alive=[e for e in getattr(room,'enemies',[]) if e.is_alive]
        if alive:
            t.insert('end','  Enemies:  ','bold'); t.insert('end',', '.join(e.name for e in alive)+'\n','red')
        if getattr(room,'items_on_ground',None):
            t.insert('end','  Items:    ','bold'); t.insert('end',', '.join(_stacked(room.items_on_ground))+'\n','white')
        if getattr(room,'objects',None):
            vis=[o.name for o in room.objects.values() if not o.hidden]
            if vis:
                t.insert('end','  Objects:  ','bold'); t.insert('end',', '.join(vis)+'\n','cyan')

    # ── hud ──────────────────────────────────────────────────────────────────
    def _refresh_hud(self):
        c,p=self._hud_canvas,self._state.player; c.delete('all')
        if not p: return
        W,pad,y0,bh=max(c.winfo_width(),700),8,6,10; bw,lw=400,30
        chunk=lw+bw+50; gap=max(10,(W-2*pad-3*chunk)//2)
        xs=[pad+i*(chunk+gap) for i in range(3)]
        def bar(x,lbl,cur,mx,col):
            c.create_text(x,y0+bh//2,text=lbl,fill=_P['dim'],font=_F['xs'],anchor='w')
            bx=x+lw; c.create_rectangle(bx,y0,bx+bw,y0+bh,fill=_P['sep'],outline='')
            fw=max(0,int(cur/max(mx,1)*bw))
            if fw: c.create_rectangle(bx,y0,bx+fw,y0+bh,fill=col,outline='')
            c.create_text(bx+bw+3,y0+bh//2,text=f'{cur}/{mx}',fill=col,font=_F['xs'],anchor='w')
        hpct=p.current_hp/max(p.max_hp,1)
        bar(xs[0],'HP',p.current_hp,p.max_hp,_P['green'] if hpct>0.5 else(_P['yellow'] if hpct>0.25 else _P['red']))
        bar(xs[1],'AP',p.current_ap,getattr(p,'total_ap',20),_P['ap'])
        bar(xs[2],'MP',getattr(p,'mana',0),getattr(p,'max_mana',0),_P['mp'])
        y2=y0+bh+8
        mid='  '.join(filter(None,[_strip(_statuses(p)),'  ·  '.join(getattr(p,'relics',[]))]))
        if mid: c.create_text(pad,y2+5,text=mid[:120],fill=_P['dim'],font=_F['n'],anchor='w'); y2+=20
        else: y2+=8
        c.create_text(pad,y2+5,text=f"Lv {p.level}  XP {p.xp}  Gold {getattr(p,'gold',0)}",
                      fill=_P['gold'],font=_F['b'],anchor='w')

    # ── log ──────────────────────────────────────────────────────────────────
    def _append_log(self,line):
        t=self._log_txt; t.configure(state='normal'); self._insert_ansi(t,line+'\n')
        t.configure(state='disabled'); t.see('end')

    def _insert_ansi(self,w,text):
        active=[]
        for part in _ANSI_SPLIT.split(text):
            m=re.fullmatch(r'\x1b\[([0-9;]*)m',part)
            if m:
                for code in (m.group(1).split(';') if m.group(1) else ['0']):
                    if code in('0',''): active=[]
                    elif code=='1' and 'bold' not in active: active.append('bold')
                    elif code=='2' and 'dim'  not in active: active.append('dim')
                    elif code in _CODE_TAG:
                        active=[x for x in active if x not in _CODE_TAG.values()]
                        active.append(_CODE_TAG[code])
            elif part: w.insert('end',part,tuple(active) if active else())

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def _on_enter(self,_=None):
        self._input_result=self._input_var.get(); self._input_var.set('')
        self._input_event.set(); self._input_ent.focus_set(); return 'break'
    def _schedule(self,fn):
        if self._root: self._root.after(0,fn)
    def _game_thread(self,fn):
        try: fn()
        except SystemExit: pass
        except Exception:
            tb=traceback.format_exc(); frm=traceback.extract_tb(sys.exc_info()[2])[-1]; exc=sys.exc_info()[1]
            msg=f"{type(exc).__name__}: {exc}\n  File: {frm.filename}, Line {frm.lineno}: {frm.line}"
            self._schedule(lambda m=msg: self._append_log(f'\n  [Error]\n  {m}'))
            print(tb,file=sys.stderr)
        finally: self._input_result=''; self._input_event.set()
    def _on_close(self):
        self._input_result=''; self._input_event.set()
        if self._root: self._root.destroy()
        sys.exit(0)

window=GameWindow()