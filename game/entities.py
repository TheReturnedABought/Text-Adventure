"""Entity classes: Entity, Player, Enemy.

Added turn stack, entity log, MP reduction, and proper inventory handling.
Extended AI profiles: pack, looter, scout, guard, trap.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from game.effects import EffectManager
from game.models import CharacterClass, EquippableItem, EnemyIntent, LootEntry

if TYPE_CHECKING:
    from game.effects import StatusEffect, EffectTrigger
    from game.world import WorldMap


@dataclass
class Entity:
    """Base combat entity with HP, block, effects."""
    name: str
    max_hp: int
    attack: int
    defense: int
    current_hp: int | None = None
    block: int = 0
    material: str = "flesh"

    def __post_init__(self) -> None:
        if self.current_hp is None:
            self.current_hp = self.max_hp
        self.effects: EffectManager = EffectManager()

    @property
    def is_alive(self) -> bool:
        return int(self.current_hp or 0) > 0

    @property
    def hp_fraction(self) -> float:
        return max(0.0, min(1.0, (self.current_hp or 0) / max(self.max_hp, 1)))

    def receive_damage(self, amount: int) -> int:
        """Apply damage after block and defense. Returns actual HP lost."""
        _, hp_damage = self.receive_block_damage(amount)
        return hp_damage

    def receive_block_damage(self, amount: int) -> tuple[int, int]:
        incoming = max(0, int(amount))
        blocked = min(self.block, incoming)
        self.block -= blocked
        remainder = incoming - blocked
        hp_damage = max(0, remainder - self.defense)
        self.current_hp = max(0, int(self.current_hp or 0) - hp_damage)
        return blocked, hp_damage

    def heal(self, amount: int) -> int:
        amount = max(0, int(amount))
        old = int(self.current_hp or 0)
        self.current_hp = min(self.max_hp, old + amount)
        return self.current_hp - old

    def add_block(self, amount: int) -> None:
        self.block = max(0, self.block + int(amount))

    def clear_block(self) -> None:
        self.block = 0

    def apply_effect(self, effect: "StatusEffect") -> str:
        return self.effects.apply(effect, self)

    def tick_effects(self, trigger: "EffectTrigger") -> list[str]:
        return self.effects.tick_all(trigger, self)

    def status_line(self) -> str:
        return f"{self.name} HP {self.current_hp}/{self.max_hp} | Block {self.block} | Effects: {self.effects.summary()}"

    def hp_bar(self, width: int = 20) -> str:
        filled = int(round(width * self.hp_fraction))
        return "[" + "#" * filled + "-" * (width - filled) + "]"


@dataclass
class Player(Entity):
    """Player character with inventory, equipment, AP, XP, and conversation memory."""
    char_class: CharacterClass | None = None
    level: int = 1
    xp: int = 0
    xp_to_next_level: int = 100
    total_ap: int = 24
    current_ap: int = 0
    inventory: list[EquippableItem] = field(default_factory=list)
    equipped: dict[str, EquippableItem] = field(default_factory=dict)
    unlocked_commands: set[str] = field(default_factory=set)

    # Conversation memory for parser (pronouns, "the one I fought earlier")
    turn_stack: list = field(default_factory=list)      # list of TurnEntry
    entity_log: list = field(default_factory=list)      # list of EntityLogEntry
    turn_number: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        self.current_ap = self.total_ap

    def reset_ap(self) -> None:
        self.current_ap = self.total_ap

    def spend_ap(self, amount: int) -> bool:
        if amount > self.current_ap:
            return False
        self.current_ap -= max(0, int(amount))
        return True

    def has_ap_for(self, amount: int) -> bool:
        return self.current_ap >= int(amount)

    def has_unlocked(self, command_name: str) -> bool:
        return str(command_name).lower() in {c.lower() for c in self.unlocked_commands}

    # ── Equipment ──────────────────────────────────────────────────────────
    def equip(self, item_name: str) -> str:
        item = self.find_in_inventory(item_name)
        if item is None:
            return f"You don't have '{item_name}'."
        ok, reason = self.can_equip(item)
        if not ok:
            return reason
        previous = self.equipped.get(item.slot)
        self.equipped[item.slot] = item
        if item in self.inventory:
            self.inventory.remove(item)
        if previous is not None:
            self.inventory.append(previous)
            return f"Equipped {item.name} ({item.slot}). {previous.name} returned to inventory."
        return f"Equipped {item.name} ({item.slot})."

    def unequip(self, slot: str) -> str:
        item = self.equipped.pop(slot, None)
        if item is None:
            return f"Nothing equipped in {slot}."
        self.inventory.append(item)
        return f"Unequipped {item.name}."

    def can_equip(self, item: EquippableItem) -> tuple[bool, str]:
        req = item.equip_requirements or {}
        min_level = int(req.get("min_level", 1))
        if self.level < min_level:
            return False, f"You must be level {min_level} to equip {item.name}."
        classes = req.get("classes", [])
        class_id = getattr(self.char_class, "id", "") if self.char_class else ""
        if classes and class_id not in classes:
            return False, f"{item.name} cannot be equipped by your class."
        return True, ""

    # ── Stat calculation with equipment & effects ─────────────────────────
    def attack_value(self) -> int:
        return self.attack + sum(i.stat_modifiers.get("attack", 0) for i in self.equipped.values()) + self.effects.stat_bonus("attack")

    def defense_value(self) -> int:
        return self.defense + sum(i.stat_modifiers.get("defense", 0) for i in self.equipped.values()) + self.effects.stat_bonus("defense")

    # AP reduction from equipped items (e.g., "b" -> letter 'b' costs 1 less)
    def ap_cost_reduction_for(self, command_name: str) -> int:
        key = command_name.lower()
        total = 0
        for item in self.equipped.values():
            for name, amount in item.ability_cost_reductions.items():
                if name.lower() == key:
                    total += int(amount)
        return total

    # MP reduction (not used in core but required by parser)
    def mp_cost_reduction_for(self, command_name: str) -> int:
        # Stub: can be expanded later for MP system
        return 0

    # ── Inventory ─────────────────────────────────────────────────────────
    def pick_up(self, item: EquippableItem) -> str:
        self.inventory.append(item)
        return f"Picked up {item.name}."

    def drop(self, item_name: str) -> tuple[EquippableItem | None, str]:
        item = self.find_in_inventory(item_name)
        if item:
            self.inventory.remove(item)
            return item, f"Dropped {item.name}."
        for slot, equipped_item in list(self.equipped.items()):
            if item_name.lower() in equipped_item.name.lower():
                self.equipped.pop(slot)
                return equipped_item, f"Dropped {equipped_item.name}."
        return None, f"You don't have '{item_name}'."

    def find_in_inventory(self, name: str) -> EquippableItem | None:
        needle = name.lower().strip()
        for item in self.inventory:
            if needle in item.name.lower():
                return item
        return None

    # ── Progression ───────────────────────────────────────────────────────
    def gain_xp(self, amount: int) -> list[str]:
        self.xp += max(0, int(amount))
        lines = [f"Gained {amount} XP."]
        while self.xp >= self.xp_to_next_level:
            self.xp -= self.xp_to_next_level
            lines.extend(self.level_up())
        return lines

    def level_up(self) -> list[str]:
        self.level += 1
        self.max_hp += 5
        self.current_hp = min(self.max_hp, (self.current_hp or 0) + 5)
        self.attack += 1
        self.defense += 1
        self.total_ap += 1
        self.current_ap = self.total_ap
        unlocked = []
        if self.char_class:
            unlocked = self.char_class.level_unlocks.get(self.level, [])
            for cmd in unlocked:
                self.unlock_command(cmd)
        lines = [f"Level up! You are now level {self.level}."]
        if unlocked:
            lines.append("Unlocked: " + ", ".join(unlocked))
        return lines

    def unlock_command(self, command_name: str) -> None:
        self.unlocked_commands.add(command_name)

    def inventory_summary(self) -> str:
        lines = ["Equipped:"]
        if self.equipped:
            for slot, item in sorted(self.equipped.items()):
                lines.append(f"  {slot}: {item.name}")
        else:
            lines.append("  (none)")
        lines.append("Inventory:")
        if self.inventory:
            for item in self.inventory:
                lines.append(f"  - {item.name}")
        else:
            lines.append("  (empty)")
        return "\n".join(lines)

    def equipped_summary(self) -> str:
        if not self.equipped:
            return "No equipment"
        return ", ".join(f"{slot}:{item.name}" for slot, item in sorted(self.equipped.items()))


@dataclass
class Enemy(Entity):
    """Enemy with AI, AP pool, intent system, and world movement."""
    template_id: str = ""
    ai_profile: str = "basic"
    total_ap: int = 18
    current_ap: int = 0
    intent_pool: list[EnemyIntent] = field(default_factory=list)
    active_intents: list[EnemyIntent] = field(default_factory=list)
    loot_table: list[LootEntry] = field(default_factory=list)
    xp_reward: int = 0
    patrol_points: list[str] = field(default_factory=list)
    guard_home: str | None = None
    forbidden_zones: set[str] = field(default_factory=set)
    fear_zones: set[str] = field(default_factory=set)
    current_zone: str | None = None
    patrol_index: int = 0

    # New AI profile attributes
    pack_id: str = ""                     # group identifier for pack AI
    pack_range: int = 2                   # max rooms distance to consider pack mates
    loot_carried: list[str] = field(default_factory=list)  # item IDs looted
    scout_range_min: int = 2              # desired minimum distance from player
    scout_range_max: int = 4              # desired maximum distance from player
    trap_placed: bool = False             # whether trapper has already set a trap
    trap_room_id: str | None = None       # room where trap is set

    def __post_init__(self) -> None:
        super().__post_init__()
        self.current_ap = self.total_ap

    def plan_turn(self, player: "Player") -> list[EnemyIntent]:
        """Greedily fill active_intents using remaining AP."""
        self.active_intents = []
        remaining = self.current_ap
        while remaining > 0:
            available = [i for i in self.intent_pool if i.ap_cost <= remaining and self.evaluate_condition(i.condition or "always", player)]
            if not available:
                break
            chosen = self.choose_intent(available)
            if chosen is None:
                break
            self.active_intents.append(chosen)
            remaining -= chosen.ap_cost
        return self.active_intents

    def choose_intent(self, available: list[EnemyIntent]) -> EnemyIntent | None:
        if not available:
            return None
        weights = [max(1, i.weight) for i in available]
        return random.choices(available, weights=weights, k=1)[0]

    def evaluate_condition(self, condition: str, player: "Player") -> bool:
        cond = (condition or "always").strip().lower()
        if cond in {"", "always"}:
            return True
        if cond == "hp_below_half":
            return self.hp_fraction < 0.5
        if cond.startswith("player_has_buff:"):
            effect_id = cond.split(":", 1)[1]
            return player.effects.has(effect_id)
        return True

    def reset_ap(self) -> None:
        self.current_ap = self.total_ap

    def spend_ap(self, amount: int) -> bool:
        if amount > self.current_ap:
            return False
        self.current_ap -= max(0, int(amount))
        return True

    def modify_ap(self, delta: int, player: "Player") -> str:
        old = self.current_ap
        self.current_ap = max(0, min(self.total_ap, self.current_ap + int(delta)))
        self.plan_turn(player)
        sign = "+" if delta >= 0 else ""
        return f"{self.name} AP {old}->{self.current_ap} ({sign}{delta})."

    def roll_loot(self) -> list[str]:
        drops: list[str] = []
        for entry in self.loot_table:
            if random.random() <= entry.chance:
                drops.append(entry.item_id)
        return drops

    def intent_display(self) -> str:
        if not self.active_intents:
            return "(no intents)"
        return ", ".join(i.id for i in self.active_intents)

    # World AI movement (used by WorldMap.step_enemy_outside_combat)
    def choose_world_move(self, world: "WorldMap", player_zone: str | None = None) -> str | None:
        """Return the next zone id this enemy wants to move to outside combat."""
        if self.current_zone is None:
            return None
        profile = (self.ai_profile or "guard").strip().lower()
        neighbors = world.neighbor_rooms(self.current_zone)
        neighbors = [z for z in neighbors if z not in self.forbidden_zones]
        if not neighbors:
            return None

        # ──────────────────────────────────────────────────────────────────────────
        # PACK – move toward the centre of nearby pack members
        # ──────────────────────────────────────────────────────────────────────────
        if profile == "pack":
            if not self.pack_id:
                return random.choice(neighbors) if neighbors else None

            # Gather positions of other pack members (alive, same pack_id)
            pack_positions = []
            for room in world.rooms.values():
                for other in room.living_enemies():
                    if other is not self and other.pack_id == self.pack_id:
                        pack_positions.append(room.id)
            if not pack_positions:
                return random.choice(neighbors)

            # Find nearest pack member
            nearest = None
            best_dist = float('inf')
            for pos in set(pack_positions):
                d = world.distance_between(self.current_zone, pos)
                if d < best_dist:
                    best_dist = d
                    nearest = pos
            if nearest is None:
                return random.choice(neighbors)

            # Move one step toward the nearest pack member
            path = world.shortest_path(self.current_zone, nearest, blocked=self.forbidden_zones)
            return path[1] if len(path) > 1 else None

        # ──────────────────────────────────────────────────────────────────────────
        # LOOTER – move toward rooms with items on ground, then loot and flee home
        # ──────────────────────────────────────────────────────────────────────────
        if profile == "looter":
            # If we have loot, flee to guard_home
            if self.loot_carried and self.guard_home:
                if self.current_zone == self.guard_home:
                    # Already home; could drop loot, but stay put
                    return None
                path = world.shortest_path(self.current_zone, self.guard_home, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else None

            # No loot yet: find nearest room with items_on_ground
            target_room = None
            best_dist = 999999
            for rid, room in world.rooms.items():
                if room.items_on_ground:
                    d = world.distance_between(self.current_zone, rid)
                    if d < best_dist:
                        best_dist = d
                        target_room = rid
            if target_room is None:
                return random.choice(neighbors)

            # Move toward that room
            path = world.shortest_path(self.current_zone, target_room, blocked=self.forbidden_zones)
            next_zone = path[1] if len(path) > 1 else None

            # If we arrived at the target room, loot one item
            if next_zone is None and self.current_zone == target_room:
                room = world.get_room(target_room)
                if room and room.items_on_ground:
                    item_id = room.items_on_ground.pop(0)   # take first item
                    self.loot_carried.append(item_id)
            return next_zone

        # ──────────────────────────────────────────────────────────────────────────
        # SCOUT – keep a specific distance from player (2-4 rooms away)
        # ──────────────────────────────────────────────────────────────────────────
        if profile == "scout":
            if player_zone is None:
                return random.choice(neighbors)

            dist = world.distance_between(self.current_zone, player_zone)
            # If too close, move away; if too far, move closer; if in range, stay or wander
            if dist < self.scout_range_min:
                # Move to neighbor that increases distance
                best = None
                best_dist = -1
                for nxt in neighbors:
                    nd = world.distance_between(nxt, player_zone)
                    if nd > best_dist:
                        best_dist = nd
                        best = nxt
                return best if best else random.choice(neighbors)
            elif dist > self.scout_range_max:
                # Move toward player
                path = world.shortest_path(self.current_zone, player_zone, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else random.choice(neighbors)
            else:
                # In ideal range – either stay or wander randomly
                return random.choice(neighbors) if random.random() < 0.3 else None

        # ──────────────────────────────────────────────────────────────────────────
        # GUARD (guardian) – never leave guard_home, if outside return home
        # ──────────────────────────────────────────────────────────────────────────
        if profile == "guard":
            if self.guard_home and self.current_zone != self.guard_home:
                path = world.shortest_path(self.current_zone, self.guard_home, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else None
            return None   # stays in place

        # ──────────────────────────────────────────────────────────────────────────
        # TRAP (trapper) – move to a choke point or room with 'trap' tag, set trap once
        # ──────────────────────────────────────────────────────────────────────────
        if profile == "trap":
            # If trap already placed, just stay or wander
            if self.trap_placed:
                return None

            # Find nearest room that is a choke point (degree 1) or has tag 'trap'
            target = None
            best_dist = 999999
            for rid, room in world.rooms.items():
                # Simple choke detection: only one exit
                is_choke = len(room.exits) == 1
                # Alternatively check for a 'trap' tag on room (if you extend Room with tags)
                has_trap_tag = hasattr(room, 'tags') and 'trap' in room.tags
                if is_choke or has_trap_tag:
                    d = world.distance_between(self.current_zone, rid)
                    if d < best_dist:
                        best_dist = d
                        target = rid
            if target is None:
                return random.choice(neighbors)

            # Move toward target
            path = world.shortest_path(self.current_zone, target, blocked=self.forbidden_zones)
            next_zone = path[1] if len(path) > 1 else None

            # If arrived, set trap
            if next_zone is None and self.current_zone == target:
                self.trap_placed = True
                self.trap_room_id = target
                # Optionally: add a trap effect to the room (requires world method)
                # world.set_trap(target, self)
            return next_zone

        # ──────────────────────────────────────────────────────────────────────────
        # EXISTING PROFILES (patrol, wander, hunter, fearful)
        # ──────────────────────────────────────────────────────────────────────────
        if profile == "patrol":
            if not self.patrol_points:
                return None
            target = self.patrol_points[self.patrol_index % len(self.patrol_points)]
            if self.current_zone == target:
                self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
                target = self.patrol_points[self.patrol_index]
            path = world.shortest_path(self.current_zone, target, blocked=self.forbidden_zones)
            return path[1] if len(path) > 1 else None

        if profile == "wander":
            return random.choice(neighbors)

        if profile == "hunter":
            if player_zone is None:
                return random.choice(neighbors)
            path = world.shortest_path(self.current_zone, player_zone, blocked=self.forbidden_zones)
            distance = len(path) - 1 if path else 999999
            if distance < 10:
                return path[1] if len(path) > 1 else random.choice(neighbors)
            return None

        if profile == "fearful":
            if player_zone is None:
                return random.choice(neighbors)
            safe = [
                z for z in neighbors
                if world.distance_between(z, player_zone) >= 3 and z not in self.fear_zones
            ]
            if safe:
                return random.choice(safe)
            return None

        # guard / default: return to guard_home
        if self.guard_home and self.current_zone != self.guard_home:
            path = world.shortest_path(self.current_zone, self.guard_home, blocked=self.forbidden_zones)
            return path[1] if len(path) > 1 else None
        return None