# rooms/map_data.py
from rooms.room import Room
from entities.enemy import Enemy


def setup_rooms():
    """
    Build and return the starting room of the world.

    Map layout:
        [Crypt] (north)
           |
        [Hall] (start)
           |
        [Kitchen] (south)
           |
        [Garden] (south)
    """

    # --- Room definitions ---
    hall = Room(
        "Entrance Hall",
        "A dimly lit hall with cobwebs stretching from wall to wall.\n"
        "Torches flicker on the stone walls. Exits lead north and south.",
        items=["torch", "key"],
    )

    kitchen = Room(
        "Abandoned Kitchen",
        "A musty kitchen that reeks of rot. Pots and pans lie scattered\n"
        "across the floor. A door leads north back to the hall, and south\n"
        "to what appears to be a garden.",
        items=["apple", "bread"],
    )

    garden = Room(
        "Overgrown Garden",
        "A once-beautiful garden, now wild and tangled. Strange mushrooms\n"
        "glow faintly in the dark corners. The air smells of damp earth.\n"
        "You can go north back to the kitchen.",
        items=["mushroom"],
    )

    crypt = Room(
        "Ancient Crypt",
        "The air is cold and still. Stone coffins line the walls.\n"
        "An inscription above the entrance reads: 'The dead do not sleep here.'\n"
        "The only exit is south.",
        items=["gold coin", "old scroll"],
    )

    # --- Link rooms ---
    hall.link("south", kitchen)
    kitchen.link("south", garden)
    hall.link("north", crypt)

    # --- Enemies ---
    goblin = Enemy("Goblin", health=30, attack_power=10, xp_reward=15)
    kitchen.enemies.append(goblin)

    skeleton = Enemy("Skeleton", health=20, attack_power=8, xp_reward=10)
    garden.enemies.append(skeleton)

    crypt_boss = Enemy("Crypt Warden", health=60, attack_power=18, xp_reward=50)
    crypt.enemies.append(crypt_boss)

    return hall  # Starting room
