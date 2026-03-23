from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, ListView, ListItem, Label, Input
from textual.containers import Center
import pyfiglet
from textual_image.widget import Image as TerminalImage
from backend import search_artwork
from rich.text import Text


class BaseScreen(Screen):
    def make_logo(self) -> Text:
        logo = pyfiglet.figlet_format("PureArt", font="larry3d", width=200)
        text = Text(logo)
        length = len(logo)
        text.stylize("bold #FF6B6B", 0, length // 3)
        text.stylize("bold #FF8E53", length // 3, length * 2 // 3)
        text.stylize("bold #FFC300", length * 2 // 3, length)
        return text

    def compose(self) -> ComposeResult:
        yield Static(self.make_logo(), id="logo")


class HomeScreen(BaseScreen):
    OPTIONS = {
        "album": "Search Album",
        "artist": "Search Artist",
        "song": "Search Song"
    }

    welcome_text = """
    [bold]TUI app to download album art[/bold]
    
    [underline]How to use:[/underline]
        1. Select to search for an album name, artist name, or song name
        2. Search for the respective name
        3. Scroll through the options and download the one you want
        4. Enjoy!
    
    [underline]Disclaimer:[/underline]
        * Not every terminal supports inline image viewing
        * If your terminal app supports it, a preview of the album art will be automatically visible
        * If not, you can manually click on each link for a preview of each album cover and download the one you want
    """

    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Static(self.welcome_text)
        with Center():
            yield ListView(
                ListItem(Label("  Search Album"), id="album"),
                ListItem(Label("  Search Artist"), id="artist"),
                ListItem(Label("  Search Song"), id="song")
            )

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        for item_id, label_text in self.OPTIONS.items():
            item = self.query_one(f"#{item_id}", ListItem)
            item.query_one(Label).update(f"  {label_text}")
            item.remove_class("selected-item")

        if event.item:
            event.item.query_one(Label).update(f"* {self.OPTIONS[event.item.id]}")
            event.item.add_class("selected-item")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        selected = event.item.id
        self.app.switch_screen(SearchName(selected))  # switch_screen not push_screen


class SearchName(BaseScreen):
    def __init__(self, search_type: str) -> None:
        self.search_type = search_type
        super().__init__()

    def compose(self) -> ComposeResult:
        yield from super().compose()
        with Center():
            yield Input(placeholder=f"Enter {self.search_type} name", id="search-input")

    def on_mount(self) -> None:
        # call_after_refresh ensures focus isn't stolen by a subsequent cycle
        self.call_after_refresh(self.query_one("#search-input", Input).focus)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        name = event.value
        self.app.switch_screen(ShowResults(self.search_type, name))


class ShowResults(BaseScreen):
    def __init__(self, search_type: str, name: str) -> None:
        self.search_type = search_type
        self.name = name
        super().__init__()

    def compose(self) -> ComposeResult:
        yield from super().compose()


class PureArt(App):
    CSS_PATH = "styles.tcss"
    SCREENS = {"home": HomeScreen}
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
        ("ctrl+q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen("home")

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )


if __name__ == "__main__":
    app = PureArt()
    app.run()