# entities/enemy.py
import random


class EnemyMove:
    def __init__(self, name, weight, effect, cooldown=0, ap_cost=4):
        self.name          = name
        self.weight        = weight
        self.effect        = effect
        self.cooldown      = cooldown
        self.ap_cost       = ap_cost   # AP this enemy must spend to use this move
        self._cd_remaining = 0

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
    AP system
    ─────────
    max_ap      : AP ceiling for this enemy (set per factory).
    current_ap  : computed at turn start = max(1, max_ap - burden_stacks).
                  Burden (hard cap debuff) is the only thing that reduces it;
                  Speed adds to it.

    Telegraphing
    ────────────
    _planned_moves : full intended sequence for the coming turn, set by
                     plan_turn() before the player acts. The HUD shows all
                     of them. Actual execution re-rolls independently.

    drops           : list of (item_name, chance) tuples, each rolled on death.
    guaranteed_relic: relic name string or None — dropped on death (elite/boss).
    """
    def __init__(self, name, health, attack_power, xp_reward=10,
                 moves=None, drops=None, guaranteed_relic=None, max_ap=8):
        self.name             = name
        self.health           = health
        self.max_health       = health
        self.attack_power     = attack_power
        self.xp_reward        = xp_reward
        self.statuses         = {}
        self.moves            = moves or []
        self.drops            = drops or []
        self.guaranteed_relic = guaranteed_relic

        # AP
        self.max_ap     = max_ap
        self.current_ap = max_ap

        # Telegraphing
        self._planned_moves: list = []   # full simulated turn sequence
        self._planned_move          = None  # first move (back-compat)

    # ── Telegraphing ──────────────────────────────────────────────────────────

    def plan_turn(self):
        """
        Simulate this turn's move sequence for the HUD display.
        Uses the same AP-spending logic as _enemy_act but does NOT fire effects,
        tick cooldowns, or mark moves as used for real — it's preview-only.

        Moves are not repeated in the same simulated sequence (matching the
        execution rule in CombatSession._enemy_act).
        """
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
        """
        Return a weighted-random ready move that:
          • costs ≤ available_ap
          • has not already been used this turn (tracked by used_ids / id())
        Returns None if nothing qualifies.
        """
        candidates = [
            m for m in self.moves
            if m.is_ready() and m.ap_cost <= available_ap and id(m) not in used_ids
        ]
        if not candidates:
            return None
        weights = [m.weight for m in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    # ── Legacy choose_move (used by plan_turn fallback / tests) ───────────────

    def choose_move(self):
        ready = [m for m in self.moves if m.is_ready()]
        if not ready:
            return None
        return random.choices(ready, weights=[m.weight for m in ready], k=1)[0]

    # ── Other helpers ─────────────────────────────────────────────────────────

    def tick_move_cooldowns(self):
        for m in self.moves:
            m.tick_cooldown()

    def roll_drops(self):
        return [name for name, chance in self.drops if random.random() < chance]

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)

    def is_alive(self):
        return self.health > 0