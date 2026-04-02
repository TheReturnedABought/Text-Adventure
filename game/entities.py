from __future__ import annotations

from dataclasses import dataclass, field

from game.models import CharacterClass, EquippableItem


@dataclass
class Entity:
    name: str
    max_hp: int
    attack: int
    defense: int
    current_hp: int | None = None

    def __post_init__(self) -> None:
        if self.current_hp is None:
            self.current_hp = self.max_hp

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def receive_damage(self, amount: int) -> int:
        final_damage = max(0, amount - self.defense)
        self.current_hp = max(0, self.current_hp - final_damage)
        return final_damage


@dataclass
class Player(Entity):
    char_class: CharacterClass | None = None
    ap: int = 2
    inventory: list[EquippableItem] = field(default_factory=list)
    equipped: dict[str, EquippableItem] = field(default_factory=dict)

    def equip(self, item_name: str) -> str:
        item = next((it for it in self.inventory if it.name.lower() == item_name.lower()), None)
        if item is None:
            return f"You do not have '{item_name}'."

        previous = self.equipped.get(item.slot)
        self.equipped[item.slot] = item
        if previous:
            return f"You swap {previous.name} for {item.name}."
        return f"You equip {item.name}."

    def attack_value(self) -> int:
        bonus = sum(it.stat_modifiers.get("attack", 0) for it in self.equipped.values())
        return self.attack + bonus


@dataclass
class Enemy(Entity):
    ai_profile: str = "basic"

    def choose_action(self) -> str:
        return "attack"
