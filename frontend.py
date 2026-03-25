from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Static, ListView, ListItem, Label, Input
from textual.containers import Center, Horizontal, Vertical
import pyfiglet
from textual_image.widget import Image as TerminalImage
from backend import search_artwork
from rich.text import Text


class HomeScreen(Screen):

    OPTIONS = {
        "album": "Album",
        "artist": "Artist",
        "song": "Song"
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
        yield Static(self.welcome_text)
        with Horizontal(id="main-layout"):
            with Vertical(id="left-column"):
                yield ListView(
                    ListItem(Label("  Album"), id="album"),
                    ListItem(Label("  Artist"), id="artist"),
                    ListItem(Label("  Song"), id="song")
                )
            yield Static("", id="connector")
            with Vertical(id="right-column"):
                yield Input(placeholder="Search...", id="search-input")
        yield Footer()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        for item_id, label_text in self.OPTIONS.items():
            item = self.query_one(f"#{item_id}", ListItem)
            item.query_one(Label).update(f"  {label_text}")
            item.remove_class("selected-item")

        if event.item:
            event.item.query_one(Label).update(f"* {self.OPTIONS[event.item.id]}")
            event.item.add_class("selected-item")
            self.query_one("#search-input", Input).placeholder = f"Search {self.OPTIONS[event.item.id]}..."

    def on_input_submitted(self, event: Input.Submitted) -> None:
        search_type = None
        for item_id in self.OPTIONS:
            item = self.query_one(f"#{item_id}", ListItem)
            if "selected-item" in item.classes:
                search_type = item_id
                break
        if search_type and event.value:
            results = search_artwork(search_type, event.value)
            self.notify(f"Found {len(results)} results for '{event.value}'")


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