# rooms/area1.py
"""
Area 1 — Castle Complex Entrance
                      [Entrance Hall]
                            |
    [Puzzle Room] ─── [Riddle Hall] ─🔒─ [The Crypt Gate] ──► Area 2
          |                 |
          └──────────── [Ratssss!]
                             |
  [Puzzle Alcove] ─── [The Crossroads 🔥] ─── [Servants' Quarters]
         |                   |                  (holds crypt key)
  [Hidden Armory]      [Locked Hall]
                       (🔒►Area 3)(🔒►Area 4)
                       (stranger on 2nd visit)
                             |
                         [Servants' Kitchen] ─── [The Pantry]
"""
from rooms.room     import Room, EnvObject, Puzzle, RevealObject
from rooms.enemy_data import (
    make_tutorial_guard, make_castle_guard, make_crossbowman,
    make_giant_rat, make_rat_swarm,
    make_skeleton_servant,
    make_crypt_warden, make_wraith, make_bone_archer, make_skeleton_guard
)
from utils.relics   import get_relic
from utils.helpers  import print_slow
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
            "A cold draught moves through the hall.",
            "Your footsteps echo against stone. The silence feels deliberate.",
            "One tapestry still holds its shape — a crowned figure surrounded by kneeling subjects.",
            "Dust motes drift through a beam of pale light from a cracked ceiling.",
            "Somewhere deep in the castle, something shifts. Stone on stone.",
        ],
    )
    entrance_corridor = Room(
        "Entrance Corridor",
        "A narrow corridor lined with cracked statues of forgotten knights.\n"
        "Boot-scuffs and snapped bolts litter the stones.\n"
        "Exits lead north to the entrance and south toward the halls beyond.",
        ambient=[
            "You hear a bowstring tighten before silence swallows the sound.",
            "The corridor funnels every footstep into a warning drumbeat.",
            "Fresh scratches in the stone mark recent fighting.",
        ],
    )
    # ── Riddle Hall ───────────────────────────────────────────────────────────
    riddle_hall = Room(
        "Riddle Hall",
        "Carved riddles line every wall, each answer worn smooth by centuries\n"
        "of curious fingers. Torchlight flickers from iron sconces.\n"
        "\n"
        "  North  — the way you came in.\n"
        "  West   — a heavy silence presses from beyond.\n"
        "  South  — something skitters below. The stench of vermin seeps upward.\n"
        "  East🔒 — a sealed door bears the words: 'Here the dead live.'",
        items=["old scroll"],
        relics=[r for r in [get_relic("iron will")] if r],
        ambient=[
            "The riddles on the walls seem to shift when you are not looking directly at them.",
            "One inscription catches your eye: 'The more you take, the more you leave behind.'",
            "The torches burn without flickering. No wind reaches this room.",
            "The sealed eastern door hums faintly, as if something breathes just behind it.",
        ],
    )
    # ── Puzzle Room ───────────────────────────────────────────────────────────
    puzzle_room = Room(
        "Puzzle Room",
        "A circular chamber dominated by a carved stone dais at its centre.\n"
        "Ancient symbols are etched into the floor in a ring around it.\n"
        "A corridor leads east back to the Riddle Hall.",
        ambient=[
            "The symbols on the floor seem to rearrange themselves at the edge of your vision.",
            "Your voice sounds different here — flatter, absorbed by the stone.",
            "The dais hums faintly, charged with some latent expectation.",
            "The air is perfectly still. Not even the torches gutter.",
        ],
    )
    # ── Ratssss! ──────────────────────────────────────────────────────────────
    ratssss = Room(
        "Ratssss!",
        "The moment you step in, the floor writhes. Hundreds of beady eyes\n"
        "catch the torchlight. The smell is indescribable.\n"
        "Exits lead north, west, and south.",
        items=["bread", "apple"],
        ambient=[
            "Something brushes your ankle. You do not look down.",
            "The squeaking never stops.",
            "One rat sits apart from the others, perfectly still, studying you.",
        ],
    )
    # ── The Crossroads ────────────────────────────────────────────────────────
    crossroads = Room(
        "The Crossroads",
        "A wide vaulted chamber where four passages meet beneath a low arch.\n"
        "A rusted brazier stands cold in the centre, filled with old ash.\n"
        "Exits lead north, east, west, and south.",
        ambient=[
            "The brazier is filled with old ash. Something is scratched into its base.",
            "The silence here feels expectant.",
            "Three ways. The castle holds its breath.",
            "You notice old boot prints in the dust, leading in from every direction.",
        ],
    )
    # ── Puzzle Alcove ─────────────────────────────────────────────────────────
    puzzle_alcove = Room(
        "Puzzle Alcove",
        "A low alcove branching west off the main hall. A thick iron chest\n"
        "sits against the far wall, sealed with an engraved lock mechanism.\n"
        "The east exit leads back to the Crossroads.",
        ambient=[
            "The chest hums faintly — there is something inside worth keeping.",
            "The lock mechanism is ornate. Someone valued what is within.",
            "Dust on the chest has been disturbed recently.",
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
            "A uniform sways gently from its peg. There is no wind.",
        ],
    )
    # ── Locked Hall ───────────────────────────────────────────────────────────
    locked_hall = Room(
        "Locked Hall",
        "A wide corridor with two sealed iron doors — one to the east,\n"
        "one to the west. Both bear heavy padlocks stamped with unfamiliar\n"
        "sigils. The north exit leads back to the Crossroads.\n"
        "A narrower passage continues south.",
        items=["gold coin"],
        ambient=[
            "The locked doors radiate a faint cold. Whatever is behind them is waiting.",
            "You try one padlock. It doesn't budge. Not with any key you carry.",
            "Silence presses in from behind both sealed doors.",
            "Someone has scratched a rough map into the stone beside the eastern door.",
        ],
    )
    # Placeholder rooms for Area 3 / 4 (not yet implemented)
    area3_stub = Room(
        "Eastern Passage",
        "The passage beyond is sealed. The lock holds fast.",
        ambient=["Cold air seeps under the door."],
    )
    area4_stub = Room(
        "Western Passage",
        "The passage beyond is sealed. The lock holds fast.",
        ambient=["Cold air seeps under the door."],
    )
    # ── Servants' Kitchen ───────────────────────────────────────────────────────────────
    servants_kitchen = Room(
        "Servants' Kitchen",
        "A Small Kitchen. Iron pots hang from chains above a dead hearth.\n"
        "The north exit leads back to the Locked Hall.",
        items=["apple"],
        ambient=[
            "The smell of old grease and something worse lingers.",
            "The hearth is cold. Whatever was cooked here was a long time ago.",
        ],
    )
    pantry = Room(
        "Pantry",
        "A tight pantry packed with foodstuffs.",
        items=["bread", "bread", "bread", "apple"],
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
        ],
    )
    hidden_armory = Room(
        "Hidden Armory",
        "A small dust-filled chamber. Racks of old weapons line the walls.\n"
        "Shields and rusty armor lie scattered across the floor.\n"
        "The only exit is north, back to the Puzzle Alcove.",
        items=["rusty sword", "iron shield", "torch"],
        relics=[r for r in [get_relic("steel gauntlets")] if r],
        ambient=[
            "The metal smells of old iron and oil.",
            "You hear a faint creak as if something shifts in the shadows.",
            "Dust motes dance in the sparse light, revealing glimmers from weapon hilts.",
        ],
    )
    # ── Connections ───────────────────────────────────────────────────────────
    entrance.link("south", entrance_corridor)
    entrance_corridor.link("south", riddle_hall)
    riddle_hall.link("west", puzzle_room)
    riddle_hall.link("south", ratssss)
    # Puzzle room south drops into Ratssss; return is west
    puzzle_room.link("south", ratssss, reverse="west")
    # Crypt Gate locked
    riddle_hall.link("east", crypt_gate, reverse="west")
    riddle_hall.lock("east", "crypt key")
    # Crossroads hub
    ratssss.link("south", crossroads)
    crossroads.link("west", puzzle_alcove)
    crossroads.link("east", servants_quarters)
    crossroads.link("south", locked_hall)
    # Locked Hall
    locked_hall.link("south", servants_kitchen)
    locked_hall.link("east", area3_stub)
    locked_hall.link("west", area4_stub)
    locked_hall.lock("east", "silver key")
    locked_hall.lock("west", "brass key")
    pantry.link("east", servants_kitchen)
    # ── Env Objects ───────────────────────────────────────────────────────────────
    # Cold Brazier — crossroads (NEW MULTI-OPTION SYSTEM)
    def light_brazier(player, room, enemies=None):
        print_slow(
            "You touch your torch to the old kindling.\\n"
            "  The brazier roars to life. Warmth floods the chamber."
        )
        # Add your queue_effect('rage', 1)(player, room) here if needed
    def move_on_brazier(player, room, enemies=None):
        print_slow("You move on, leaving the brazier to sit in silence.")
        # Add your mprestore(1)(player, room) here if needed
    brazier = EnvObject(name="cold brazier")
    brazier.add_options(
        description="A rusted brazier stands cold at the centre of the room.\\n"
                    "Old ash fills the bowl. Scratched into its base:\\n"
                    "  'Fire remembers courage.'",
        options=[
            {
                'label': 'Light brazier',
                'requires': 'torch',
                'consumes': True,
                'action': light_brazier
            },
            {
                'label': 'Move on',
                'requires': None,
                'action': move_on_brazier
            }
        ]
    )
    crossroads.add_env_object(brazier)
    def standard_chest():
        entrance.add_item("gold coin")
        print_slow("A gold coin is in the chest")
    standard_chest = EnvObject(
        name="alcove walls",
        use_fn=standard_chest,
        examine_fn=lambda p, r, e=None: print_slow("A normal chest."),
        uses=1
    )
    entrance.add_env_object(standard_chest)
    # Puzzle Alcove — alcove walls (examine to reveal hidden corner)
    def examine_alcove_for_hidden_corner(player, room):
        print_slow(
            "Aside from the chest, the alcove walls are lined with faint carvings.\\n"
            "One corner seems slightly out of place, almost hidden."
        )
        # Reveal the hidden corner RevealObject
        if "suspicious corner" not in [o.name for o in room.env_objects]:
            hidden_corner = RevealObject(
                name="suspicious corner",
                direction="south",
                target_room=hidden_armory,
                use_fn=reveal_hidden_armory,
                reveal_fn=lambda p, r: print_slow(
                    "You push aside a loose stone in the corner. "
                    "The wall grinds aside to reveal a narrow passage to the south!"
                )
            )
            room.add_env_object(hidden_corner)
    alcove_exam = EnvObject(
        name="alcove walls",
        examine_fn=examine_alcove_for_hidden_corner,
        use_fn=lambda p, r, e=None: print_slow("There's nothing to interact with here yet."),
        uses=1
    )
    puzzle_alcove.add_env_object(alcove_exam)
    def reveal_hidden_armory(player, room):
        puzzle_alcove.reveal_connection("south", hidden_armory)
        print_slow("  A hidden passage opens south, revealing a new room!")
    # Chest puzzle (unchanged - Puzzle class works fine)
    def _alcove_puzzle_reward(player, room):
        puzzle_alcove.add_item("healing draught")
        print_slow("  The chest clicks open. Inside: a healing draught and a glint of something else.")
    chest = Puzzle(
        name="Sealed Chest",
        description=(
            "The chest's lock bears three rotating rings of symbols.\\n"
            "Beneath them, a worn inscription reads:\\n"
            "\\n"
            "  'I have cities, but no houses live there.\\n"
            "   I have mountains, but no trees grow there.\\n"
            "   I have water, but no fish swim there.\\n"
            "   What am I?'"
        ),
        clues=["  Hint: You might carry one in your pocket."],
        solution="map",
        reward_fn=_alcove_puzzle_reward,
        mini=True
    )
    puzzle_alcove.add_env_object(chest)
    # Puzzle Room — main puzzle (unchanged)
    def _main_puzzle_reward(player, room):
        puzzle_room.add_relic("etched stone")
        print_slow("\\n  ✦ The dais yields a relic!")
    main_dais = Puzzle(
        name="The Dais Inscription",
        description=(
            "The dais bears an inscription carved in archaic script:\\n"
            "\\n"
            "  'Speak me and I vanish.\\n"
            "   Hold me and I am forever kept.\\n"
            "   What am I?'"
        ),
        clues=[
            "  Hint: It is something everyone possesses,",
            "        but loses the moment they share it.",
        ],
        solution="silence",
        reward_fn=_main_puzzle_reward
    )
    puzzle_room.add_env_object(main_dais)
    # ── on_enter hooks ────────────────────────────────────────────────────────
    def _entrance_enter(player):
        from utils.ascii_art import ENTRANCE_HALL, print_art
        print_art(ENTRANCE_HALL, indent=6)
        print()
        print_slow("  Tutorial — Area 1 Basics")
        print_slow("  • Movement: north/south/east/west")
        print_slow("  • Combat: attack, block, heal, end")
        print_slow("  • Watch enemy intent in combat HUD before acting.")
        print_slow("  • Damage hints now show type effectiveness (very effective / not very effective).")
        print_slow("  A Castle Guard steps forward and raises his shield.")
        print_slow('  "Show me you can survive these halls," he says.')
        input("  Press Enter to continue...")
    entrance.on_enter = _entrance_enter
    def _corridor_enter(player):
        print()
        print_slow("  A guard and crossbowman block the corridor in a coordinated stance.")
        print_slow("  Tutorial tip: block can blunt heavy hits; typed damage may overperform or underperform.")
        print_slow("  Soldier basic attack is Piercing, Rogue is Slashing, Mage is Force.")
        input("  Press Enter to continue...")
    entrance_corridor.on_enter = _corridor_enter
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
        input("\n  Press Enter to continue...")
    puzzle_room.on_enter = _puzzle_room_enter
    def _ratssss_enter(player):
        from utils.ascii_art import RATSSSS, print_art
        print_art(RATSSSS, indent=6)
        print_slow("\n  You smell it before you see it.")
        print_slow("  Then the floor moves, and you realise the smell is the least of your problems.")
        input("\n  Press Enter to continue...")
    ratssss.on_enter = _ratssss_enter
    def _crossroads_enter(player):
        from utils.ascii_art import CROSSROADS, print_art
        print_art(CROSSROADS, indent=8)
        print_slow("\n  Four passages meet at a cold brazier.")
        print_slow("  Something is scratched into the base of the bowl.")
        input("\n  Press Enter to continue...")
    crossroads.on_enter = _crossroads_enter
    def _alcove_enter(player):
        print_slow("\n  The alcove is quiet. A sealed iron chest dominates the far wall.")
        print_slow("  Type 'examine chest' to inspect the lock, 'solve <answer>' to try it.")
        input("\n  Press Enter to continue...")
    puzzle_alcove.on_enter = _alcove_enter
    def _servants_enter(player):
        from utils.ascii_art import SERVANTS_QUARTERS, print_art
        print_art(SERVANTS_QUARTERS, indent=6)
        print_slow("\n  The door creaks open onto rows of mouldering cots.")
        print_slow("  Two shapes rise from the shadows — they were servants once.")
        print_slow("  Now they are something else entirely, and they are looking at you.")
        input("\n  Press Enter to continue...")
    servants_quarters.on_enter = _servants_enter
    def _locked_hall_enter(player):
        # Stranger appears on the 2nd visit (visit_count will be 1 on first call,
        # incremented to 2 by Game._travel before on_enter fires — so we check >= 2)
        if locked_hall.visit_count >= 2 and not getattr(locked_hall, "_stranger_seen", False):
            locked_hall._stranger_seen = True
            print_slow("\n  You stop. A hooded figure stands by the eastern door.")
            print_slow("  They do not startle. They were waiting.")
            print_slow('  "Two locked doors. Two distant places."')
            print_slow('  "The Courtyard Key lies deep in the crypt below.')
            print_slow('   Find it, and the other keys will follow."')
            print_slow("  Before you can speak, they are gone.")
            player.journal.add_lore(
                "The Stranger at the Locked Hall",
                "A hooded figure told you:\n"
                "  'The Courtyard Key lies deep in the crypt below.\n"
                "   Find it, and the other keys will follow.'\n"
                "Two locked doors in the hall lead to Areas 3 and 4.\n"
                "Keys: silver key (east) and brass key (west).",
            )
        else:
            print_slow("\n  The corridor is quiet. Two locked doors loom in the shadows.")
            print_slow("  You need a silver key for the east door and a brass key for the west.")
        input("\n  Press Enter to continue...")
    locked_hall.on_enter = _locked_hall_enter
    def servants_kitchen_enter(player):
        print_slow("\n  Two skeletons work tirelessly, kneading dust like flour.")
        print_slow("  As you enter, their heads turn toward you and they ready their weapons.")
        input("\n  Press Enter to continue...")
    servants_kitchen.on_enter = servants_kitchen_enter
    def pantry_enter(player):
        from utils.ascii_art import PANTRY, print_art
        print_art(PANTRY, indent=6)
        print_slow('  "You enter a walk-in pantry."')
        print_slow('  "There is food here."')
    pantry.on_enter = pantry_enter
    def _crypt_enter(player):
        from utils.ascii_art import CRYPT_GATE, print_art
        print_art(CRYPT_GATE, indent=8)
        print_slow("\n  The sealed door stands open. You don't remember unlocking it.")
        print_slow("  The Crypt Warden turns its head — slowly, deliberately —")
        print_slow('  and speaks in a voice like stone scraping stone:')
        print_slow('  "You carry the scent of the living. That ends here."')
        input("\n  Press Enter to continue...")
    crypt_gate.on_enter = _crypt_enter
    # ── Enemies ───────────────────────────────────────────────────────────────
    entrance.enemies.append(make_tutorial_guard())
    entrance_corridor.enemies.append(make_castle_guard())
    entrance_corridor.enemies.append(make_crossbowman())
    ratssss.enemies.append(make_giant_rat())
    ratssss.enemies.append(make_giant_rat())
    ratssss.enemies.append(make_rat_swarm())
    servants_quarters.enemies.append(make_skeleton_servant())
    servants_quarters.enemies.append(make_skeleton_servant())
    servants_kitchen.enemies.append(make_skeleton_servant())
    servants_kitchen.enemies.append(make_skeleton_servant())
    servants_kitchen.enemies.append(make_skeleton_servant())
    hidden_armory.enemies.append(make_skeleton_guard())
    hidden_armory.enemies.append(make_skeleton_servant())
    crypt_gate.enemies.append(make_crypt_warden())
    crypt_gate.enemies.append(make_wraith())
    crypt_gate.enemies.append(make_bone_archer())
    return entrance
