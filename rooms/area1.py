# rooms/area1.py
"""
Area 1 — Castle Complex Entrance

Layout (matches design diagram):

                   [Entrance Hall]
                         |
   [Puzzle Room] ─── [Riddle Hall] ─🔒─ [Crypt Gate]
         |                 |
         └──────────── [Ratssss!] ─── [Servants' Quarters]

  * east exit locked — requires "crypt key" (found in Servants' Quarters)
"""
from rooms.room import Room
from rooms.puzzle import Puzzle
from rooms.enemy_data import (
    make_castle_guard,
    make_goblin_guard, make_goblin_archer,
    make_giant_rat, make_rat_swarm,
    make_skeleton_servant,
    make_crypt_warden, make_wraith, make_bone_archer,
)
from utils.relics import get_relic
from utils.helpers import print_slow


def setup_area1():
    """Build and connect all Area 1 rooms. Returns the starting room."""

    # ── Entrance Hall ─────────────────────────────────────────────────────────

    entrance = Room(
        "Entrance Hall",
        "Grand arched doors loom behind you, caked with decades of dust.\n"
        "Faded tapestries hang between crumbling stone pillars.\n"
        "A long corridor stretches south.",
        items=["torch"],
        ambient=[
            "A cold draught moves through the hall. Whatever warmth once lived here is long gone.",
            "Your footsteps echo against stone. The silence feels deliberate.",
            "One tapestry still holds its shape — a crowned figure surrounded by kneeling subjects.",
            "Dust motes drift through a beam of pale light from a cracked ceiling.",
            "Somewhere deep in the castle, something shifts. Stone on stone.",
        ],
    )

    # ── Riddle Hall ───────────────────────────────────────────────────────────
    # Description includes directional hints for all four passages.

    riddle_hall = Room(
        "Riddle Hall",
        "Carved riddles line every wall, each answer worn smooth by centuries\n"
        "of curious fingers. Torchlight flickers from iron sconces.\n"
        "\n"
        "  North  — the way you came in. Cold air drifts from the entrance.\n"
        "  West   — a heavy silence presses from beyond. The stones seem to wait.\n"
        "  South  — something skitters below. The stench of vermin seeps upward.\n"
        "  East🔒 — a sealed door bears the words: 'Here the dead live.'",
        items=["old scroll"],
        relics=[r for r in [get_relic("iron will")] if r],
        ambient=[
            "The riddles on the walls seem to shift when you are not looking directly at them.",
            "One inscription catches your eye: 'The more you take, the more you leave behind.'",
            "The torches burn without flickering. No wind reaches this room.",
            "You run a finger along one carved answer. The stone is worn glassy-smooth.",
            "The sealed eastern door hums faintly, as if something breathes just behind it.",
        ],
    )

    # ── Puzzle Room ───────────────────────────────────────────────────────────

    puzzle_room = Room(
        "Puzzle Room",
        "A circular chamber dominated by a carved stone dais at its centre.\n"
        "Ancient symbols are etched into the floor in a ring around it.\n"
        "A corridor leads east to the Riddle Hall, south to the lower passages.",
        ambient=[
            "The symbols on the floor seem to rearrange themselves at the edge of your vision.",
            "Your voice sounds different here — flatter, absorbed by the stone.",
            "The dais hums faintly, charged with some latent expectation.",
            "The air is perfectly still. Not even the torches gutter.",
            "You feel as though the room is listening.",
        ],
    )

    # ── Ratssss! ──────────────────────────────────────────────────────────────

    ratssss = Room(
        "Ratssss!",
        "The moment you step in, the floor writhes. Hundreds of beady eyes\n"
        "catch the torchlight. The smell is indescribable.\n"
        "Exits lead north to the hall above, west to a strange chamber, and east.",
        items=["bread", "apple"],
        ambient=[
            "Something brushes your ankle. You do not look down.",
            "The squeaking never stops. You wonder how many there are.",
            "The smell is a physical thing. You have learned to breathe through your mouth.",
            "They part around your feet like water, but they are watching.",
            "One rat sits apart from the others, perfectly still, studying you.",
        ],
    )

    # ── Servants' Quarters ────────────────────────────────────────────────────

    servants_quarters = Room(
        "Servants' Quarters",
        "Rows of mouldering cots line the walls. Tattered uniforms hang\n"
        "from pegs. Something moves in the shadows between the beds.\n"
        "The only exit is west.",
        items=["crypt key"],
        relics=[r for r in [get_relic("thorn bracelet")] if r],
        ambient=[
            "The cots are still made. Whoever left did not plan to.",
            "A child's drawing is pinned above one bed. You look away quickly.",
            "The shadows between the beds are deeper than they should be.",
            "A uniform sways gently from its peg. There is no wind.",
            "You find a name scratched into the wall beside a cot. Just a name.",
        ],
    )

    # ── Crypt Gate ────────────────────────────────────────────────────────────

    crypt_gate = Room(
        "The Crypt Gate",
        "A vaulted chamber of black stone. At its far end, an enormous iron door\n"
        "bears the sigil of the Crypt Warden — who stands before it, waiting.\n"
        "The passage west leads back to the Riddle Hall.",
        items=["gold coin"],
        relics=[r for r in [get_relic("vampiric blade")] if r],
        ambient=[
            "The air tastes of iron and old stone.",
            "The Warden does not blink. It simply waits.",
            "The sigil on the door pulses faintly — a slow, cold heartbeat.",
            "Your torch dims here, as if the darkness is consuming the light.",
            "The silence is absolute, except for the sound of your own breathing.",
        ],
    )

    # ── Connections ───────────────────────────────────────────────────────────

    entrance.link("south", riddle_hall)
    riddle_hall.link("west", puzzle_room)
    riddle_hall.link("south", ratssss)

    # Curved arrow in diagram: Puzzle Room exits south into Ratssss,
    # and Ratssss returns west back to Puzzle Room (north stays → Riddle Hall).
    puzzle_room.link("south", ratssss, reverse="west")

    # Crypt Gate — locked from Riddle Hall side only
    riddle_hall.link("east", crypt_gate, reverse="west")
    riddle_hall.lock("east", "crypt key")

    ratssss.link("east", servants_quarters)

    # ── Puzzle ────────────────────────────────────────────────────────────────

    puzzle_room.puzzle = Puzzle(
        name="The Dais Inscription",
        description=(
            "The dais bears an inscription carved in archaic script:\n"
            "\n"
            "  'Speak me and I vanish.\n"
            "   Hold me and I am forever kept.\n"
            "   What am I?'"
        ),
        clues=[
            "  Hint: It is something everyone possesses,",
            "        but loses the moment they share it.",
        ],
        solution="silence",
        # reward_fn=None — wired but unassigned for now
    )

    # ── on_enter dialogue ─────────────────────────────────────────────────────

    def _entrance_enter(player):
        from utils.ascii_art import ENTRANCE_HALL, print_art
        print_art(ENTRANCE_HALL, indent=6)
        print_slow("\n  A figure steps from the shadow of a pillar — a Castle Guard,")
        print_slow("  still in the old king's livery, though the colours have faded.")
        print_slow('  "Halt. You should not be here."')
        print_slow("  He raises his weapon. There is no warmth in his eyes.")
        input("\n  Press Enter to continue...")
    entrance.on_enter = _entrance_enter

    def _riddle_hall_enter(player):
        from utils.ascii_art import RIDDLE_HALL, print_art
        print_art(RIDDLE_HALL, indent=6)
        print_slow("\n  Two goblins wheel around as you enter, blades already drawn.")
        print_slow('  "Fresh meat!" one shrieks, in a voice like grinding gravel.')
        print_slow("  The other simply grins.")
        input("\n  Press Enter to continue...")
    riddle_hall.on_enter = _riddle_hall_enter

    def _puzzle_room_enter(player):
        from utils.ascii_art import PUZZLE_ROOM, print_art
        print_art(PUZZLE_ROOM, indent=8)
        print_slow("\n  The room is empty of living things.")
        print_slow("  The dais hums faintly as you approach, as if recognising you.")
        print_slow("  Something about it feels like a question waiting to be answered.")
        input("\n  Press Enter to continue...")
    puzzle_room.on_enter = _puzzle_room_enter

    def _ratssss_enter(player):
        from utils.ascii_art import RATSSSS, print_art
        print_art(RATSSSS, indent=6)
        print_slow("\n  You smell it before you see it.")
        print_slow("  Then the floor moves, and you realise the smell is the least of your problems.")
        input("\n  Press Enter to continue...")
    ratssss.on_enter = _ratssss_enter

    def _servants_enter(player):
        from utils.ascii_art import SERVANTS_QUARTERS, print_art
        print_art(SERVANTS_QUARTERS, indent=6)
        print_slow("\n  The door creaks open onto rows of mouldering cots.")
        print_slow("  Two shapes rise from the shadows — they were servants once.")
        print_slow("  Now they are something else entirely, and they are looking at you.")
        input("\n  Press Enter to continue...")
    servants_quarters.on_enter = _servants_enter

    def _crypt_enter(player):
        from utils.ascii_art import CRYPT_GATE, print_art
        print_art(CRYPT_GATE, indent=8)
        print_slow("\n  The sealed door stands open. You don't remember unlocking it.")
        print_slow("  The Crypt Warden turns its head — slowly, deliberately —")
        print_slow('  and speaks in a voice like stone scraping stone:')
        print_slow('  "You carry the scent of the living. That ends here."')
        input("\n  Press Enter to continue...")
    crypt_gate.on_enter = _crypt_enter

    entrance.enemies.append(make_castle_guard())

    riddle_hall.enemies.append(make_goblin_guard())
    riddle_hall.enemies.append(make_goblin_archer())

    ratssss.enemies.append(make_giant_rat())
    ratssss.enemies.append(make_giant_rat())
    ratssss.enemies.append(make_rat_swarm())

    servants_quarters.enemies.append(make_skeleton_servant())
    servants_quarters.enemies.append(make_skeleton_servant())

    crypt_gate.enemies.append(make_crypt_warden())
    crypt_gate.enemies.append(make_wraith())
    crypt_gate.enemies.append(make_bone_archer())

    return entrance