from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, ListView, ListItem, Label, Input, Button
from textual.containers import Center, VerticalScroll
import pyfiglet, 
from backend import search_artwork

class HomeScreen(Screen):
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(pyfiglet.figlet_format("PureArt", "block"))
        yield ListView(
            ListItem(Label("Search Album")),
            ListItem(Label("Search Artist")),
            ListItem(Label("Search Song"))
        )
        yield Footer()


class SearchName(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Enter Album/Artist/Song Name")
        yield Footer()


class ShowResults(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        # yield whatever can display images
        yield Footer()


class PureArt(App):
    
    SCREENS = {"home": HomeScreen}
    
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode"),
        ("ctrl+q", "quit", "Quit")]
    
    def on_mount(self) -> None:
        self.push_screen("home")

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )
        
    
# To run app, don't touch!
if __name__ == "__main__":
    app = PureArt()
    app.run()