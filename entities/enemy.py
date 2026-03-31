# entities/enemy.py
import random


class EnemyMove:
    def __init__(self, name, weight, effect, cooldown=0, ap_cost=4, tags=None):
        self.name          = name
        self.weight        = weight
        self.effect        = effect
        self.cooldown      = cooldown
        self.ap_cost       = ap_cost
        self._cd_remaining = 0
        self.tags          = set(tags or [])

    def is_ready(self):
        return self._cd_remaining <= 0

    def use(self, enemy, player):
        self.effect(enemy, player)
        self._cd_remaining = self.cooldown

    def tick_cooldown(self):
        if self._cd_remaining > 0:
            self._cd_remaining -= 1


class Enemy:
    """
    damage_dice      : dice expression ("1d8+2") for basic attacks.
                       Falls back to random.randint(4, attack_power) if None.
    fled             : True if the enemy escaped (no drops, no XP).
    on_death_effect  : str tag read by CombatSession (e.g. "shatter").
    _current_player_ref : set by _enemy_act so conditional choose fns can read HP.
    """

    def __init__(self, name, health, attack_power, xp_reward=10,
                 moves=None, drops=None, guaranteed_relic=None,
                 max_ap=8, damage_dice=None, on_death_effect=None,
                 damage_type="physical", weaknesses=None, resistances=None,
                 phase_triggers=None, reactive_counters=None, combo_scripts=None, combat_intro=None):
        self.name             = name
        self.health           = health
        self.max_health       = health
        self.attack_power     = attack_power
        self.xp_reward        = xp_reward
        self.statuses         = {}
        self.moves            = moves or []
        self.drops            = drops or []
        self.guaranteed_relic = guaranteed_relic
        self.damage_dice      = damage_dice
        self.on_death_effect  = on_death_effect

        self.damage_type      = damage_type
        self.weaknesses       = set(weaknesses or [])
        self.resistances      = set(resistances or [])

        self.phase_triggers   = list(phase_triggers or [])
        self.reactive_counters = reactive_counters or {}
        self.combo_scripts    = list(combo_scripts or [])
        self._triggered_phases = set()
        self._combo_history    = []
        self.combat_intro      = combat_intro

        self.max_ap     = max_ap
        self.current_ap = max_ap

        self.fled                = False
        self._current_player_ref = None

        self._planned_moves: list = []
        self._planned_move        = None

    # ── Telegraphing ──────────────────────────────────────────────────────────

    def plan_turn(self):
        burden = self.statuses.get("burden", 0)
        speed  = self.statuses.get("speed", 0)
        budget = max(1, self.max_ap - burden) + speed

        self._planned_moves = []
        used_ids: set = set()

        while budget > 0:
            candidates = [
                m for m in self.moves
                if m.is_ready() and m.ap_cost <= budget and id(m) not in used_ids
            ]
            if not candidates:
                break
            weights = [m.weight for m in candidates]
            chosen  = random.choices(candidates, weights=weights, k=1)[0]
            self._planned_moves.append(chosen)
            used_ids.add(id(chosen))
            budget -= chosen.ap_cost

        self._planned_move = self._planned_moves[0] if self._planned_moves else None

    # ── Move selection ────────────────────────────────────────────────────────

    def choose_affordable_move(self, available_ap: int, used_ids: set):
        candidates = [
            m for m in self.moves
            if m.is_ready() and m.ap_cost <= available_ap and id(m) not in used_ids
        ]
        if not candidates:
            return None
        weights = [m.weight for m in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def choose_move(self):
        ready = [m for m in self.moves if m.is_ready()]
        if not ready:
            return None
        return random.choices(ready, weights=[m.weight for m in ready], k=1)[0]

    # ── Damage roll ───────────────────────────────────────────────────────────

    def roll_damage(self) -> int:
        """Roll using damage_dice expression, or fall back to (4, attack_power)."""
        if self.damage_dice and self.damage_dice != "0":
            from utils.dice import roll
            return roll(self.damage_dice)
        return random.randint(4, max(4, self.attack_power))

    # ── Dynamic boss scripting hooks ─────────────────────────────────────────

    def _check_phase_triggers(self, attacker=None, combat_session=None, ctx=None):
        if self.max_health <= 0:
            return
        ratio = self.health / self.max_health
        for i, trig in enumerate(self.phase_triggers):
            threshold = trig.get("threshold", 1.0)
            if i in self._triggered_phases:
                continue
            if ratio <= threshold:
                fn = trig.get("fn")
                if callable(fn):
                    fn(self, attacker, combat_session, ctx or {})
                self._triggered_phases.add(i)

    def _run_reactive(self, event: str, attacker=None, combat_session=None, ctx=None):
        for fn in self.reactive_counters.get(event, []):
            if callable(fn):
                fn(self, attacker, combat_session, ctx or {})

    def _run_combo_scripts(self, combat_session=None, ctx=None):
        names = self._combo_history
        for script in self.combo_scripts:
            seq = script.get("sequence", [])
            if not seq or len(names) < len(seq):
                continue
            if names[-len(seq):] != seq:
                continue

            if script.get("grant_ap", 0):
                self.current_ap += script["grant_ap"]
            msg = script.get("message")
            if msg:
                from utils.helpers import print_slow
                print_slow(f"  {self.name} combo — {msg}")

            next_move = script.get("queue_move")
            if next_move:
                for m in self.moves:
                    if m.name == next_move and m.is_ready() and m.ap_cost <= self.current_ap:
                        m.use(self, self._current_player_ref)
                        self.current_ap -= m.ap_cost
                        break

    def on_move_used(self, move_name: str, combat_session=None, ctx=None):
        self._combo_history.append(move_name)
        if len(self._combo_history) > 5:
            self._combo_history = self._combo_history[-5:]
        self._run_combo_scripts(combat_session, ctx)

    def on_combat_start(self, player=None, combat_session=None):
        if callable(self.combat_intro):
            self.combat_intro(self, player, combat_session)

    def on_damaged(self, attacker=None, damage=0, damage_type="physical", combat_session=None, ctx=None):
        payload = {"damage": damage, "damage_type": damage_type, **(ctx or {})}
        self._check_phase_triggers(attacker=attacker, combat_session=combat_session, ctx=payload)
        self._run_reactive("on_damaged", attacker=attacker, combat_session=combat_session, ctx=payload)

    # ── Misc ──────────────────────────────────────────────────────────────────

    def tick_move_cooldowns(self):
        for m in self.moves:
            m.tick_cooldown()

    def roll_drops(self):
        if self.fled:
            return []
        return [name for name, chance in self.drops if random.random() < chance]

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)

    def is_alive(self):
        return self.health > 0

    def __repr__(self):
        return f"<Enemy '{self.name}' HP:{self.health}/{self.max_health}>"