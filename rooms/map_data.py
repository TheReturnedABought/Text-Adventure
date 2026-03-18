# rooms/map_data.py
from rooms.room import Room
from entities.enemy import Enemy
from entities.enemy_moves import (
    move, basic_attack, heavy_attack, poison_attack,
    enrage_self, apply_enemy_vulnerable, apply_enemy_weak,
    stun_attack, self_heal, double_hit, volatile_self, disorient_attack,
)
from utils.relics import get_relic


def setup_rooms():
    """
    Map layout:
        [Crypt] (north)
           |
        [Hall] (start)
           |
        [Kitchen] (south)
           |
        [Garden] (south)
    """

    hall = Room(
        "Entrance Hall",
        "A dimly lit hall with cobwebs stretching from wall to wall.\n"
        "Torches flicker on the stone walls. Exits lead north and south.",
        items=["torch", "key"],
        relics=[r for r in [get_relic("frog statue")] if r],
    )

    kitchen = Room(
        "Abandoned Kitchen",
        "A musty kitchen that reeks of rot. Pots and pans lie scattered\n"
        "across the floor. A door leads north back to the hall, and south\n"
        "to what appears to be a garden.",
        items=["apple", "bread"],
        relics=[r for r in [get_relic("venom gland")] if r],
    )

    garden = Room(
        "Overgrown Garden",
        "A once-beautiful garden, now wild and tangled. Strange mushrooms\n"
        "glow faintly in the dark corners. The air smells of damp earth.\n"
        "You can go north back to the kitchen.",
        items=["mushroom"],
        relics=[r for r in [get_relic("thorn bracelet")] if r],
    )

    crypt = Room(
        "Ancient Crypt",
        "The air is cold and still. Stone coffins line the walls.\n"
        "An inscription above the entrance reads: 'The dead do not sleep here.'\n"
        "The only exit is south.",
        items=["gold coin", "old scroll"],
        relics=[r for r in [get_relic("storm ring")] if r],
    )

    hall.link("south", kitchen)
    kitchen.link("south", garden)
    hall.link("north", crypt)

    goblin = Enemy(
        "Goblin", health=30, attack_power=10, xp_reward=15,
        moves=[
            move("Scratch",      weight=5, effect_fn=basic_attack()),
            move("Dirty Bite",   weight=3, effect_fn=poison_attack(stacks=1)),
            move("Double Swipe", weight=2, effect_fn=double_hit()),
        ]
    )
    kitchen.enemies.append(goblin)


    skeleton = Enemy(
        "Skeleton", health=20, attack_power=8, xp_reward=10,
        moves=[
            move("Bone Strike",   weight=5, effect_fn=basic_attack()),
            move("Rattling Blow", weight=3, effect_fn=apply_enemy_weak(stacks=2)),
        ]
    )
    garden.enemies.append(skeleton)


    crypt_boss = Enemy(
        "Crypt Warden", health=60, attack_power=18, xp_reward=50,
        moves=[
            move("Spectral Slash",    weight=4, effect_fn=basic_attack()),
            move("Death Grip",        weight=3, effect_fn=heavy_attack(2.0, "DEATH GRIP"),  cooldown=2),
            move("Soul Drain",        weight=2, effect_fn=poison_attack(stacks=3)),
            move("Blood Frenzy",      weight=1, effect_fn=enrage_self(),                    cooldown=3),
            move("Disorienting Wail", weight=1, effect_fn=disorient_attack(),               cooldown=3),
        ]
    )
    crypt.enemies.append(crypt_boss)

    return hall