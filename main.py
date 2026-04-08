from game import TextAdventureGame

DEBUG = True

def main() -> None:
    game = TextAdventureGame(debug=DEBUG)
    game.run()

if __name__ == "__main__":
    main()
