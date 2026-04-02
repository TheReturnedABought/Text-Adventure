from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

# FIX: add optional jsonschema validation (if installed)
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from game.commands import CommandRegistry
from game.entities import Enemy
from game.models import Ability, CharacterClass, EnemyIntent, EquippableItem, IntentType, LootEntry
from game.world import Material, Room, WorldMap, WorldObject

if TYPE_CHECKING:
    pass


class AssetLoader:
    def __init__(self, assets_root: str | Path) -> None:
        self.assets_root = Path(assets_root)
        # FIX: asset cache
        self._item_cache: dict[str, EquippableItem] = {}
        self._enemy_template_cache: dict[str, dict] = {}
        self._class_cache: dict[str, CharacterClass] = {}
        self._room_cache: dict[str, Room] = {}

    # ── Validation helpers (using jsonschema) ─────────────────────────────────
    def _validate_against_schema(self, data: dict, schema_path: Path) -> list[str]:
        if not HAS_JSONSCHEMA:
            return []  # skip validation if not installed
        if not schema_path.exists():
            return []
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(data, schema)
            return []
        except jsonschema.ValidationError as e:
            return [str(e)]

    # ── Room loading (with enemy_spawns fix) ─────────────────────────────────
    def load_room(self, path: Path) -> "Room":
        data = self._read_json(path)
        # Validate against schema if available
        schema_path = self.assets_root / "rooms" / "_schema.json"
        errors = self._validate_against_schema(data, schema_path)
        if errors:
            print(f"Warning: Room {path} validation errors: {errors}")

        material = Material(data.get("material", "stone")) if str(data.get("material", "stone")) in {m.value for m in Material} else Material.STONE
        room = Room(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem.title()),
            description=data.get("description", ""),
            material=material,
            is_outdoor=bool(data.get("is_outdoor", False)),
            light_level=int(data.get("light_level", 10)),
            exits=dict(data.get("exits", {})),
            line_of_sight=list(data.get("line_of_sight", [])),
            ambient=data.get("ambient", ""),
            is_start=bool(data.get("is_start", False)),
            # FIX: store enemy_spawns
            enemy_spawns=list(data.get("enemy_spawns", [])),
        )
        for obj_data in data.get("objects", []):
            obj = self.load_world_object(obj_data)
            room.objects[obj.id] = obj
        room.items_on_ground = list(data.get("items_on_ground", []))
        return room

    def load_all_rooms(self) -> dict[str, "Room"]:
        if self._room_cache:
            return self._room_cache
        rooms = {}
        for path in self._glob_json("rooms"):
            if path.name.startswith("_"):
                continue
            room = self.load_room(path)
            rooms[room.id] = room
        self._room_cache = rooms
        return rooms

    def load_world_object(self, data: dict) -> "WorldObject":
        material_raw = str(data.get("material", "wood"))
        material = next((m for m in Material if m.value == material_raw), Material.WOOD)
        obj = WorldObject(
            id=data.get("id", data.get("name", "object").lower().replace(" ", "_")),
            name=data.get("name", "Object"),
            description=data.get("description", ""),
            material=material,
            is_container=bool(data.get("is_container", False)),
            is_moveable=bool(data.get("is_moveable", False)),
            is_locked=bool(data.get("is_locked", False)),
            key_item_id=data.get("key_item_id"),
            hidden=bool(data.get("hidden", False)),
            reveals=list(data.get("reveals", [])),
            on_interact=dict(data.get("on_interact", {})),
            required_commands=dict(data.get("required_commands", {})),
        )
        obj.contents = [self.load_world_object(c) for c in data.get("contents", [])]
        obj.items_inside = list(data.get("items_inside", []))
        return obj

    # ── Item loading with cache ──────────────────────────────────────────────
    def load_item(self, path: Path) -> "EquippableItem":
        data = self._read_json(path)
        schema_path = self.assets_root / "items" / "_schema.json"
        errors = self._validate_against_schema(data, schema_path)
        if errors:
            print(f"Warning: Item {path} validation errors: {errors}")

        abilities = [self.load_ability(a) for a in data.get("abilities", [])]
        return EquippableItem(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem.title()),
            slot=data.get("slot", "trinket"),
            description=data.get("description", ""),
            material=data.get("material", "metal"),
            rarity=data.get("rarity", "common"),
            tier=int(data.get("tier", 1)),
            stat_modifiers=dict(data.get("stat_modifiers", {})),
            ability_cost_reductions=dict(data.get("ability_cost_reductions", {})),
            abilities=abilities,
            equip_requirements=dict(data.get("equip_requirements", {})),
            upgrade_path=data.get("upgrade_path"),
        )

    def load_all_items(self) -> dict[str, "EquippableItem"]:
        if self._item_cache:
            return self._item_cache
        items = {}
        for path in self._glob_json("items"):
            if path.name.startswith("_"):
                continue
            item = self.load_item(path)
            items[item.id] = item
        self._item_cache = items
        return items

    def load_ability(self, data: dict) -> "Ability":
        return Ability(
            id=data.get("id", data.get("name", "ability").lower().replace(" ", "_")),
            name=data.get("name", "Ability"),
            description=data.get("description", ""),
            ap_cost=data.get("ap_cost"),
            dice_expression=data.get("dice_expression"),
            effect_on_hit=data.get("effect_on_hit"),
            effect_duration=int(data.get("effect_duration", 1)),
            effect_stacks=int(data.get("effect_stacks", 1)),
            tags=list(data.get("tags", [])),
        )

    def load_ability_file(self, path: Path) -> dict[str, dict]:
        data = self._read_json(path)
        if isinstance(data, dict) and "abilities" in data:
            entries = data.get("abilities", [])
        elif isinstance(data, list):
            entries = data
        else:
            entries = [data]
        return {entry.get("id", entry.get("name", "ability")): entry for entry in entries}

    # ── Enemy loading ────────────────────────────────────────────────────────
    def load_enemy_template(self, path: Path) -> dict:
        data = self._read_json(path)
        schema_path = self.assets_root / "enemies" / "_schema.json"
        errors = self._validate_against_schema(data, schema_path)
        if errors:
            print(f"Warning: Enemy {path} validation errors: {errors}")
        return data

    def load_all_enemy_templates(self) -> dict[str, dict]:
        if self._enemy_template_cache:
            return self._enemy_template_cache
        out = {}
        for p in self._glob_json("enemies"):
            if p.name.startswith("_"):
                continue
            d = self.load_enemy_template(p)
            out[d.get("id", p.stem)] = d
        self._enemy_template_cache = out
        return out

    def instantiate_enemy(self, template_id: str, templates: dict[str, dict]) -> "Enemy":
        t = templates[template_id]
        intents = []
        for i in t.get("intent_pool", []):
            intent_type = IntentType[str(i.get("intent_type", "ATTACK")).upper()] if str(i.get("intent_type", "ATTACK")).upper() in IntentType.__members__ else IntentType.ATTACK
            intents.append(EnemyIntent(
                id=i.get("id", "action"),
                intent_type=intent_type,
                description=i.get("description", "acts"),
                dice_expression=i.get("dice_expression"),
                ap_cost=int(i.get("ap_cost", 6)),
                weight=int(i.get("weight", 1)),
                condition=i.get("condition"),
                effect_on_hit=i.get("effect_on_hit"),
                effect_duration=int(i.get("effect_duration", 1)),
                tags=i.get("tags", []),
            ))
        loot = [LootEntry(item_id=row.get("item_id", ""), chance=float(row.get("chance", 0.0)), count_expression=str(row.get("count_expression", "1"))) for row in t.get("loot_table", [])]
        return Enemy(
            template_id=template_id,
            name=t.get("name", template_id),
            max_hp=int(t.get("max_hp", 10)),
            attack=int(t.get("attack", 3)),
            defense=int(t.get("defense", 0)),
            material=t.get("material", "flesh"),
            ai_profile=t.get("ai_profile", "basic"),
            total_ap=int(t.get("ap", t.get("total_ap", 18))),
            intent_pool=intents,
            loot_table=loot,
            xp_reward=int(t.get("xp_reward", 0)),
            patrol_points=list(t.get("patrol_points", [])),
            guard_home=t.get("guard_home"),
            forbidden_zones=set(t.get("forbidden_zones", [])),
            fear_zones=set(t.get("fear_zones", [])),
        )

    def instantiate_enemies_for_room(self, spawn_list: list[dict], templates: dict[str, dict]) -> list["Enemy"]:
        enemies: list[Enemy] = []
        for spawn in spawn_list:
            tid = spawn.get("template_id")
            if tid not in templates:
                continue
            for _ in range(int(spawn.get("count", 1))):
                enemy = self.instantiate_enemy(tid, templates)
                enemy.current_zone = spawn.get("zone_id")
                enemies.append(enemy)
        return enemies

    # ── Class loading ────────────────────────────────────────────────────────
    def load_class(self, path: Path) -> "CharacterClass":
        data = self._read_json(path)
        schema_path = self.assets_root / "classes" / "_schema.json"
        errors = self._validate_against_schema(data, schema_path)
        if errors:
            print(f"Warning: Class {path} validation errors: {errors}")

        level_unlocks = {int(k): list(v) for k, v in (data.get("level_unlocks", {}) or {}).items()}
        choice_unlocks = {int(k): [list(g) for g in v] for k, v in (data.get("choice_unlocks", {}) or {}).items()}
        return CharacterClass(
            id=data.get("id", path.stem),
            name=data.get("name", path.stem.title()),
            description=data.get("description", ""),
            base_stats=dict(data.get("base_stats", {})),
            starting_items=list(data.get("starting_items", [])),
            level_unlocks=level_unlocks,
            choice_unlocks=choice_unlocks,
        )

    def load_all_classes(self) -> dict[str, "CharacterClass"]:
        if self._class_cache:
            return self._class_cache
        classes = {}
        for p in self._glob_json("classes"):
            if p.name.startswith("_"):
                continue
            c = self.load_class(p)
            classes[c.id] = c
        self._class_cache = classes
        return classes

    # ── Commands ─────────────────────────────────────────────────────────────
    def load_commands_into(self, registry: "CommandRegistry") -> None:
        path = self.assets_root / "commands" / "commands.json"
        if path.exists():
            registry.load_from_dict(self._read_json(path))

    # ── World building (FIX: use enemy_spawns) ───────────────────────────────
    def build_world_map(self, enemy_templates: dict[str, dict]) -> "WorldMap":
        rooms = self.load_all_rooms()
        world = WorldMap()
        for room in rooms.values():
            # FIX: use room.enemy_spawns to add enemies
            for enemy in self.instantiate_enemies_for_room(room.enemy_spawns, enemy_templates):
                room.add_enemy(enemy)
            world.add_room(room)
        if world.start_room_id:
            world.current_room_id = world.start_room_id
        return world

    # ── Validation methods (kept for compatibility) ──────────────────────────
    def validate_room(self, data: dict) -> list[str]:
        errs = []
        for key in ("id", "name", "description"):
            if key not in data:
                errs.append(f"missing '{key}'")
        return errs

    def validate_item(self, data: dict) -> list[str]:
        errs = []
        for key in ("id", "name", "slot"):
            if key not in data:
                errs.append(f"missing '{key}'")
        return errs

    def validate_enemy(self, data: dict) -> list[str]:
        errs = []
        for key in ("id", "name", "max_hp"):
            if key not in data:
                errs.append(f"missing '{key}'")
        return errs

    def validate_class(self, data: dict) -> list[str]:
        errs = []
        for key in ("id", "name", "base_stats"):
            if key not in data:
                errs.append(f"missing '{key}'")
        return errs

    def validate_all(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        validators = {
            "rooms": self.validate_room,
            "items": self.validate_item,
            "enemies": self.validate_enemy,
            "classes": self.validate_class,
        }
        for folder, fn in validators.items():
            for p in self._glob_json(folder):
                if p.name.startswith("_"):
                    continue
                errs = fn(self._read_json(p))
                if errs:
                    out[str(p)] = errs
        return out

    # ── Internal helpers ─────────────────────────────────────────────────────
    def _read_json(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Failed to parse JSON at {path}: {exc}") from exc

    def _glob_json(self, subfolder: str) -> list[Path]:
        """Recursively find all .json files under assets/subfolder."""
        base = self.assets_root / subfolder
        if not base.exists():
            return []
        return list(base.rglob("*.json"))

    def load_all_rooms(self) -> dict[str, "Room"]:
        if self._room_cache:
            return self._room_cache
        rooms = {}
        for path in self._glob_json("rooms"):
            if path.name.startswith("_"):
                continue
            room = self.load_room(path)
            rooms[room.id] = room
        self._room_cache = rooms
        return rooms

    def _resolve_item_refs(self, item_ids: list[str], item_catalog: dict[str, "EquippableItem"]) -> list["EquippableItem"]:
        items = []
        for iid in item_ids:
            if iid not in item_catalog:
                raise KeyError(f"Unknown item id: {iid}")
            items.append(item_catalog[iid])
        return items