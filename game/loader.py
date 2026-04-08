# game/loader.py
import json
from pathlib import Path
from typing import Dict, List, Optional

from game.commands import CommandRegistry
from game.entities import Enemy
from game.models import Ability, CharacterClass, EnemyIntent, EquippableItem, IntentType, LootEntry
from game.world import Material, Room, WorldMap, WorldObject

class AssetLoader:
    def __init__(self, assets_root: str | Path):
        self.assets_root = Path(assets_root)

    # Rooms
    def load_room(self, path: Path) -> Room:
        data = self._read_json(path)
        material = Material(data.get("material", "stone"))
        art_asset = data.get("art_asset")
        if not art_asset:
            default_art = path.parent / "art" / f"{path.stem}.txt"
            art_asset = str(default_art.as_posix()) if default_art.exists() else None
        room = Room(
            id=data.get("id", path.stem), name=data.get("name", path.stem.title()),
            description=data.get("description", ""), material=material,
            is_outdoor=bool(data.get("is_outdoor", False)), light_level=int(data.get("light_level", 10)),
            exits=dict(data.get("exits", {})), exit_requirements=dict(data.get("exit_requirements", {})),
            line_of_sight=list(data.get("line_of_sight", [])), ambient=list(data.get("ambient", [])),
            is_start=bool(data.get("is_start", False)), enemy_spawns=list(data.get("enemy_spawns", [])),
            interaction_rules=list(data.get("interaction_rules", [])), combat_won_snippet=data.get("combat_won_snippet", ""),
            art_asset=art_asset
        )
        room.description_snippets.update(data.get("description_snippets", {}))
        for obj_data in data.get("objects", []):
            obj = self._load_world_object(obj_data)
            room.objects[obj.id] = obj
            if "description_snippet" in obj_data:
                room.description_snippets[obj.id] = obj_data["description_snippet"]
        room.items_on_ground = list(data.get("items_on_ground", []))
        return room

    def load_all_rooms(self) -> Dict[str, Room]:
        rooms = {}
        for path in self._glob_json("rooms"):
            if path.name.startswith("_"): continue
            room = self.load_room(path)
            rooms[room.id] = room
        return rooms

    def _load_world_object(self, data: dict) -> WorldObject:
        material_raw = str(data.get("material", "wood"))
        material = next((m for m in Material if m.value == material_raw), Material.WOOD)
        obj = WorldObject(
            id=data.get("id", data.get("name", "object").lower().replace(" ", "_")),
            name=data.get("name", "Object"), description=data.get("description", ""), material=material,
            is_container=bool(data.get("is_container", False)), is_moveable=bool(data.get("is_moveable", False)),
            is_locked=bool(data.get("is_locked", False)), key_item_id=data.get("key_item_id"),
            hidden=bool(data.get("hidden", False)), reveals=list(data.get("reveals", [])),
            on_interact=dict(data.get("on_interact", {})), required_commands=dict(data.get("required_commands", {})),
            set_flags_on_interact=dict(data.get("set_flags_on_interact", {}))
        )
        obj.contents = [self._load_world_object(c) for c in data.get("contents", [])]
        obj.items_inside = list(data.get("items_inside", []))
        return obj

    # Items
    def load_item(self, path: Path) -> EquippableItem:
        data = self._read_json(path)
        abilities = [self._load_ability(a) for a in data.get("abilities", [])]
        return EquippableItem(
            id=data.get("id", path.stem), name=data.get("name", path.stem.title()), slot=data.get("slot", "trinket"),
            description=data.get("description", ""), material=data.get("material", "metal"), rarity=data.get("rarity", "common"),
            tier=int(data.get("tier", 1)), stat_modifiers=dict(data.get("stat_modifiers", {})),
            letter_cost_reductions=dict(data.get("letter_cost_reductions", {})),
            ability_cost_reductions=dict(data.get("ability_cost_reductions", {})), abilities=abilities,
            equip_requirements=dict(data.get("equip_requirements", {})), upgrade_path=data.get("upgrade_path"),
            item_flags=data.get("item_flags", []), on_hit_effects=dict(data.get("on_hit_effects", {})),
            passive_effects=dict(data.get("passive_effects", {})), value=int(data.get("value", 0))
        )

    def load_all_items(self) -> Dict[str, EquippableItem]:
        items = {}
        for path in self._glob_json("items"):
            if path.name.startswith("_"): continue
            item = self.load_item(path)
            items[item.id] = item
        return items

    def _load_ability(self, data: dict) -> Ability:
        known = {"id","name","description","ap_cost","dice_expression","effect_on_hit","effect_duration","effect_stacks","tags"}
        return Ability(
            id=data.get("id", data.get("name", "ability").lower().replace(" ", "_")),
            name=data.get("name", "Ability"), description=data.get("description", ""),
            ap_cost=data.get("ap_cost"), dice_expression=data.get("dice_expression"),
            effect_on_hit=data.get("effect_on_hit"), effect_duration=int(data.get("effect_duration", 1)),
            effect_stacks=int(data.get("effect_stacks", 1)), tags=list(data.get("tags", [])),
            payload={k:v for k,v in data.items() if k not in known}
        )

    # Enemies
    def load_enemy_template(self, path: Path) -> dict:
        return self._read_json(path)

    def load_all_enemy_templates(self) -> Dict[str, dict]:
        out = {}
        for p in self._glob_json("enemies"):
            if p.name.startswith("_"): continue
            d = self.load_enemy_template(p)
            out[d.get("id", p.stem)] = d
        return out

    def instantiate_enemy(self, template_id: str, templates: Dict[str, dict]) -> Enemy:
        t = templates[template_id]
        intents = []
        for i in t.get("intent_pool", []):
            intent_type = IntentType[str(i.get("intent_type", "ATTACK")).upper()]
            intents.append(EnemyIntent(
                id=i.get("id", "action"), intent_type=intent_type, description=i.get("description", "acts"),
                dice_expression=i.get("dice_expression"), ap_cost=int(i.get("ap_cost", 6)),
                weight=int(i.get("weight", 1)), condition=i.get("condition"), effect_on_hit=i.get("effect_on_hit"),
                effect_duration=int(i.get("effect_duration", 1)), tags=i.get("tags", [])
            ))
        loot = [LootEntry(item_id=row["item_id"], chance=float(row["chance"]), count_expression=str(row.get("count_expression", "1")))
                for row in t.get("loot_table", [])]
        return Enemy(
            template_id=template_id, name=t.get("name", template_id), max_hp=int(t.get("max_hp", 10)),
            attack=int(t.get("attack", 3)), defense=int(t.get("defense", 0)), material=t.get("material", "flesh"),
            ai_profile=t.get("ai_profile", "basic"), total_ap=int(t.get("ap", t.get("total_ap", 18))),
            intent_pool=intents, loot_table=loot, xp_reward=int(t.get("xp_reward", 0)),
            patrol_points=list(t.get("patrol_points", [])), guard_home=t.get("guard_home"),
            forbidden_zones=set(t.get("forbidden_zones", [])), fear_zones=set(t.get("fear_zones", [])),
            vulnerabilities=t.get("vulnerabilities", []), resistances=t.get("resistances", []),
            art_asset=t.get("art_asset")
        )

    def instantiate_enemies_for_room(self, spawn_list: List[dict], templates: Dict[str, dict], room_id: str) -> List[Enemy]:
        enemies = []
        for spawn in spawn_list:
            tid = spawn.get("template_id")
            if tid not in templates: continue
            for _ in range(int(spawn.get("count", 1))):
                enemy = self.instantiate_enemy(tid, templates)
                if enemy.guard_home is None and enemy.ai_profile == "guard": enemy.guard_home = room_id
                enemy.current_zone = room_id
                enemy.combat_room_id = room_id
                enemies.append(enemy)
        return enemies

    # Classes
    def load_class(self, path: Path) -> CharacterClass:
        data = self._read_json(path)
        level_unlocks = {int(k): list(v) for k, v in data.get("level_unlocks", {}).items()}
        choice_unlocks = {int(k): [list(g) for g in v] for k, v in data.get("choice_unlocks", {}).items()}
        return CharacterClass(
            id=data.get("id", path.stem), name=data.get("name", path.stem.title()), description=data.get("description", ""),
            base_stats=dict(data.get("base_stats", {})), starting_items=list(data.get("starting_items", [])),
            level_unlocks=level_unlocks, choice_unlocks=choice_unlocks
        )

    def load_all_classes(self) -> Dict[str, CharacterClass]:
        classes = {}
        for p in self._glob_json("classes"):
            if p.name.startswith("_"): continue
            c = self.load_class(p)
            classes[c.id] = c
        return classes

    # World building
    def build_world_map(self, enemy_templates: Dict[str, dict]) -> WorldMap:
        rooms = self.load_all_rooms()
        world = WorldMap()
        for room in rooms.values():
            enemies = self.instantiate_enemies_for_room(room.enemy_spawns, enemy_templates, room.id)
            for enemy in enemies: room.add_enemy(enemy)
            world.add_room(room)
        if world.start_room_id: world.current_room_id = world.start_room_id
        return world

    # Helpers
    def _read_json(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {path}: {e}")
            return {}
    def _glob_json(self, subfolder: str) -> List[Path]:
        base = self.assets_root / subfolder
        return list(base.rglob("*.json")) if base.exists() else []