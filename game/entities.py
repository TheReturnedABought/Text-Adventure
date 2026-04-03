"""Entity classes: Entity (base), Player, Enemy.

Handles HP, AP, MP, inventory, equipment, effects, and AI.
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

    def __post_init__(self):
        if self.current_hp is None:
            self.current_hp = self.max_hp
        self.effects = EffectManager()

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def receive_damage(self, amount: int) -> int:
        """Apply damage after block and defense. Returns HP lost."""
        blocked = min(self.block, amount)
        self.block -= blocked
        remainder = amount - blocked
        hp_damage = max(0, remainder - self.defense)
        self.current_hp = max(0, self.current_hp - hp_damage)
        return hp_damage

    def heal(self, amount: int) -> int:
        amount = max(0, int(amount))
        old = self.current_hp
        self.current_hp = min(self.max_hp, old + amount)
        return self.current_hp - old

    def add_block(self, amount: int) -> None:
        self.block = max(0, self.block + amount)

    def clear_block(self) -> None:
        self.block = 0

    def apply_effect(self, effect: "StatusEffect") -> str:
        return self.effects.apply(effect, self)

    def tick_effects(self, trigger: "EffectTrigger") -> list[str]:
        return self.effects.tick_all(trigger, self)

    def status_line(self) -> str:
        return f"{self.name} HP {self.current_hp}/{self.max_hp} | Block {self.block} | Effects: {self.effects.summary()}"

    def hp_bar(self, width: int = 20) -> str:
        filled = int(round(width * (self.current_hp / max(self.max_hp, 1))))
        return "[" + "#" * filled + "-" * (width - filled) + "]"


@dataclass
class Player(Entity):
    """Player character with inventory, equipment, AP, MP, XP."""
    char_class: CharacterClass | None = None
    level: int = 1
    xp: int = 0
    xp_to_next_level: int = 100
    total_ap: int = 24
    current_ap: int = 0
    max_mana: int = 0
    mana: int = 0
    inventory: list[EquippableItem] = field(default_factory=list)
    equipped: dict[str, EquippableItem] = field(default_factory=dict)
    unlocked_commands: set[str] = field(default_factory=set)

    # Conversation memory (for pronoun resolution)
    turn_stack: list = field(default_factory=list)
    entity_log: list = field(default_factory=list)
    turn_number: int = 0

    def __post_init__(self):
        super().__post_init__()
        self.current_ap = self.total_ap
        self.mana = self.max_mana

    def reset_ap(self) -> None:
        self.current_ap = self.total_ap

    def spend_ap(self, amount: int) -> bool:
        if amount > self.current_ap:
            return False
        self.current_ap -= max(0, int(amount))
        return True

    def has_unlocked(self, command_name: str) -> bool:
        return command_name.lower() in {c.lower() for c in self.unlocked_commands}

    def unlock_command(self, command_name: str) -> None:
        self.unlocked_commands.add(command_name)

    # Equipment
    def equip(self, item_name: str) -> str:
        item = self.find_in_inventory(item_name)
        if not item:
            return f"You don't have '{item_name}'."
        ok, reason = self.can_equip(item)
        if not ok:
            return reason
        previous = self.equipped.get(item.slot)
        self.equipped[item.slot] = item
        if item in self.inventory:
            self.inventory.remove(item)
        if previous:
            self.inventory.append(previous)
            return f"Equipped {item.name}. {previous.name} returned to inventory."
        return f"Equipped {item.name}."

    def unequip(self, slot: str) -> str:
        item = self.equipped.pop(slot, None)
        if not item:
            return f"Nothing equipped in {slot}."
        self.inventory.append(item)
        return f"Unequipped {item.name}."

    def can_equip(self, item: EquippableItem) -> tuple[bool, str]:
        req = item.equip_requirements or {}
        if self.level < req.get("min_level", 1):
            return False, f"You must be level {req['min_level']} to equip {item.name}."
        classes = req.get("classes", [])
        class_id = getattr(self.char_class, "id", "") if self.char_class else ""
        if classes and class_id not in classes:
            return False, f"{item.name} cannot be equipped by your class."
        return True, ""

    def attack_value(self) -> int:
        base = self.attack
        base += sum(i.stat_modifiers.get("attack", 0) for i in self.equipped.values())
        base += self.effects.stat_bonus("attack")
        return base

    def defense_value(self) -> int:
        base = self.defense
        base += sum(i.stat_modifiers.get("defense", 0) for i in self.equipped.values())
        base += self.effects.stat_bonus("defense")
        return base

    def ap_cost_reduction_for(self, command_name: str) -> int:
        total = 0
        for item in self.equipped.values():
            for name, amount in item.ability_cost_reductions.items():
                if name.lower() == command_name.lower():
                    total += amount
        return total

    def mp_cost_reduction_for(self, command_name: str) -> int:
        total = 0
        for item in self.equipped.values():
            for name, amount in item.ability_cost_reductions.items():
                if name.lower() == command_name.lower():
                    total += amount
        return total

    def pick_up(self, item: EquippableItem) -> str:
        self.inventory.append(item)
        return f"Picked up {item.name}."

    def drop(self, item_name: str) -> tuple[EquippableItem | None, str]:
        item = self.find_in_inventory(item_name)
        if item:
            self.inventory.remove(item)
            return item, f"Dropped {item.name}."
        for slot, equipped in list(self.equipped.items()):
            if item_name.lower() in equipped.name.lower():
                self.equipped.pop(slot)
                return equipped, f"Dropped {equipped.name}."
        return None, f"You don't have '{item_name}'."

    def find_in_inventory(self, name: str) -> EquippableItem | None:
        needle = name.lower()
        for item in self.inventory:
            if needle in item.name.lower():
                return item
        return None

    def gain_xp(self, amount: int) -> tuple[list[str], list[list[str]]]:
        self.xp += max(0, amount)
        lines = [f"Gained {amount} XP."]
        all_choices = []
        while self.xp >= self.xp_to_next_level:
            self.xp -= self.xp_to_next_level
            lvl_lines, choices = self.level_up()
            lines.extend(lvl_lines)
            all_choices.extend(choices)
        return lines, all_choices

    def level_up(self) -> tuple[list[str], list[list[str]]]:
        self.level += 1
        self.max_hp += 5
        self.current_hp = min(self.max_hp, self.current_hp + 5)
        self.attack += 1
        self.defense += 1
        self.total_ap += 1
        self.current_ap = self.total_ap
        self.max_mana += 1
        self.mana = self.max_mana

        unlocked = []
        choices = []
        if self.char_class:
            unlocked = self.char_class.level_unlocks.get(self.level, [])
            choices = self.char_class.choice_unlocks.get(self.level, [])
            for cmd in unlocked:
                self.unlock_command(cmd)
        lines = [f"Level up! You are now level {self.level}."]
        if unlocked:
            lines.append("Unlocked: " + ", ".join(unlocked))
        return lines, choices

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
    combat_room_id: str | None = None   # where it is during combat
    patrol_index: int = 0
    pack_id: str = ""
    pack_range: int = 2
    loot_carried: list[str] = field(default_factory=list)
    scout_range_min: int = 2
    scout_range_max: int = 4
    trap_placed: bool = False
    trap_room_id: str | None = None

    def __post_init__(self):
        super().__post_init__()
        self.current_ap = self.total_ap

    def reset_ap(self) -> None:
        self.current_ap = self.total_ap

    def spend_ap(self, amount: int) -> bool:
        if amount > self.current_ap:
            return False
        self.current_ap -= max(0, amount)
        return True

    def plan_turn(self, player: Player) -> list[EnemyIntent]:
        """Greedy selection of intents using remaining AP."""
        self.active_intents = []
        remaining = self.current_ap
        while remaining > 0:
            available = [i for i in self.intent_pool if i.ap_cost <= remaining and self._check_condition(i.condition, player)]
            if not available:
                break
            chosen = random.choices(available, weights=[max(1, i.weight) for i in available], k=1)[0]
            self.active_intents.append(chosen)
            remaining -= chosen.ap_cost
        return self.active_intents

    def _check_condition(self, condition: str | None, player: Player) -> bool:
        cond = (condition or "always").strip().lower()
        if cond in ("", "always"):
            return True
        if cond == "hp_below_half":
            return self.hp_fraction < 0.5
        if cond.startswith("player_has_buff:"):
            effect_id = cond.split(":", 1)[1]
            return player.effects.has(effect_id)
        return True

    def modify_ap(self, delta: int, player: Player) -> str:
        old = self.current_ap
        self.current_ap = max(0, min(self.total_ap, self.current_ap + delta))
        self.plan_turn(player)
        sign = "+" if delta >= 0 else ""
        return f"{self.name} AP {old}->{self.current_ap} ({sign}{delta})."

    def roll_loot(self) -> list[str]:
        drops = []
        for entry in self.loot_table:
            if random.random() <= entry.chance:
                drops.append(entry.item_id)
        return drops

    def intent_display(self) -> str:
        if not self.active_intents:
            return "(no intents)"
        return ", ".join(i.id for i in self.active_intents)

    def choose_world_move(self, world: "WorldMap", player_zone: str | None = None) -> str | None:
        """Return next zone id to move to outside combat."""
        if self.current_zone is None:
            return None
        profile = self.ai_profile.lower()
        neighbors = world.neighbor_rooms(self.current_zone)
        neighbors = [z for z in neighbors if z not in self.forbidden_zones]
        if not neighbors:
            return None

        # Pack AI
        if profile == "pack" and self.pack_id:
            pack_positions = []
            for room in world.rooms.values():
                for other in room.living_enemies():
                    if other is not self and other.pack_id == self.pack_id:
                        pack_positions.append(room.id)
            if pack_positions:
                nearest = min(pack_positions, key=lambda p: world.distance_between(self.current_zone, p))
                path = world.shortest_path(self.current_zone, nearest, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else random.choice(neighbors)

        # Looter AI
        if profile == "looter":
            if self.loot_carried and self.guard_home:
                if self.current_zone == self.guard_home:
                    return None
                path = world.shortest_path(self.current_zone, self.guard_home, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else None
            # Find nearest room with items
            target = None
            best_dist = 999999
            for rid, room in world.rooms.items():
                if room.items_on_ground:
                    d = world.distance_between(self.current_zone, rid)
                    if d < best_dist:
                        best_dist = d
                        target = rid
            if target:
                path = world.shortest_path(self.current_zone, target, blocked=self.forbidden_zones)
                if len(path) > 1:
                    return path[1]
                elif self.current_zone == target and world.get_room(target).items_on_ground:
                    self.loot_carried.append(world.get_room(target).items_on_ground.pop(0))
                    return None
            return random.choice(neighbors) if neighbors else None

        # Scout AI
        if profile == "scout" and player_zone:
            dist = world.distance_between(self.current_zone, player_zone)
            if dist < self.scout_range_min:
                best = max(neighbors, key=lambda n: world.distance_between(n, player_zone))
                return best
            elif dist > self.scout_range_max:
                path = world.shortest_path(self.current_zone, player_zone, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else random.choice(neighbors)
            else:
                return random.choice(neighbors) if random.random() < 0.3 else None

        # Guard AI
        if profile == "guard":
            if self.guard_home and self.current_zone != self.guard_home:
                path = world.shortest_path(self.current_zone, self.guard_home, blocked=self.forbidden_zones)
                return path[1] if len(path) > 1 else None
            return None

        # Trap AI
        if profile == "trap" and not self.trap_placed:
            target = None
            best_dist = 999999
            for rid, room in world.rooms.items():
                is_choke = len(room.exits) == 1
                has_trap_tag = hasattr(room, 'tags') and 'trap' in room.tags
                if is_choke or has_trap_tag:
                    d = world.distance_between(self.current_zone, rid)
                    if d < best_dist:
                        best_dist = d
                        target = rid
            if target:
                path = world.shortest_path(self.current_zone, target, blocked=self.forbidden_zones)
                if len(path) > 1:
                    return path[1]
                elif self.current_zone == target:
                    self.trap_placed = True
                    self.trap_room_id = target
                    return None
            return random.choice(neighbors) if neighbors else None

        # Patrol
        if profile == "patrol" and self.patrol_points:
            target = self.patrol_points[self.patrol_index % len(self.patrol_points)]
            if self.current_zone == target:
                self.patrol_index += 1
                target = self.patrol_points[self.patrol_index % len(self.patrol_points)]
            path = world.shortest_path(self.current_zone, target, blocked=self.forbidden_zones)
            return path[1] if len(path) > 1 else None

        # Wander
        if profile == "wander":
            return random.choice(neighbors)

        # Hunter
        if profile == "hunter" and player_zone:
            path = world.shortest_path(self.current_zone, player_zone, blocked=self.forbidden_zones)
            if len(path) - 1 < 10:
                return path[1] if len(path) > 1 else random.choice(neighbors)
            return None

        # Fearful
        if profile == "fearful" and player_zone:
            safe = [z for z in neighbors if world.distance_between(z, player_zone) >= 3 and z not in self.fear_zones]
            return random.choice(safe) if safe else None

        # Default: return home
        if self.guard_home and self.current_zone != self.guard_home:
            path = world.shortest_path(self.current_zone, self.guard_home, blocked=self.forbidden_zones)
            return path[1] if len(path) > 1 else None
        return None