from database.schema import initialize_database
from ui.app import App


def main() -> None:
    initialize_database()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()

