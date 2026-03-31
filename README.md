# PureArt

> A Python TUI application for downloading high-resolution album artwork via the iTunes Search API.

PureArt is a terminal-based app that lets you search for any album, artist, or song and download its full-resolution artwork directly to your computer — no subscriptions, no accounts, no browser required. Built with Textual and Rich for a polished terminal experience.

---

## Screenshots

### Main Menu
![Main Menu](screenshots/main_menu.png)

### Results
![Results](screenshots/results.png)

### Save Dialog
![Save Dialog](screenshots/save_dialog.png)

---

## Features

- Search by **album name**, **artist name**, or **song name**
- Retrieves up to 25 results per search from the iTunes Search API
- Downloads artwork at the **highest available resolution** (up to 10000×10000)
- **Inline image preview** in supported terminals (iTerm2, Kitty, WezTerm)
- **Fallback text mode** for unsupported terminals — shows album name, artist, and direct download links
- Built-in **file browser** to choose exactly where artwork is saved
- **Filter results** by artist or year on the results screen
- Paginated results — browse through all matches across multiple pages
- No API key, no account, no subscription required

---

## Requirements

- Python **3.11** or higher
- macOS, Linux, or Windows with a modern terminal

### Terminal Image Support (Optional)

Inline album art previews are available in:

| Terminal | Support |
|---|---|
| iTerm2 | ✅ Full |
| Kitty | ✅ Full |
| WezTerm | ✅ Full |
| Terminal.app | ❌ Text fallback |
| Other terminals | Varies |

If your terminal does not support inline images, PureArt automatically falls back to displaying the album name and artist as styled text with a download button — no configuration needed.

---

## Installation

### Via pip (recommended)

```bash
pip install pureart
```

### From source

```bash
git clone https://github.com/SrikarC6/PureArt.git
cd PureArt
pip install .
```

---

## Usage

Launch PureArt from any terminal:

```bash
pureart
```

---

## How It Works

### Step 1 — Choose a Search Type

On the main menu, use the arrow keys or the number shortcuts to select what you want to search by:

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate between Album, Artist, Song |
| `1` | Jump to Album |
| `2` | Jump to Artist |
| `3` | Jump to Song |
| `Tab` | Move focus to next element |
| `Shift+Tab` | Move focus to previous element |

Type your search query into the **Query** input box and press `Ctrl+R` or `Enter` to search.

---

### Step 2 — Browse Results

The results screen displays all matching albums in a **two-column grid**. Each result shows:

- Album artwork (if your terminal supports inline images)
- Album name
- Artist name
- Release year
- A **Download** button

Use these controls to navigate the results screen:

| Key | Action |
|---|---|
| `Tab` / `Shift+Tab` | Move between results |
| `Esc` | Go back to the main menu |
| `/` | Focus the filter bar |
| `Ctrl+~` | Previous page |
| `Ctrl+^` | Next page |
| `Ctrl+Q` | Quit |

You can type in the **Filter** bar at the top to narrow results by artist name or release year without making a new search.

---

### Step 3 — Download Artwork

Press the **Download** button on any result to open the **Save** dialog. A file browser lets you navigate your entire directory tree and select exactly where to save the artwork.

| Key | Action |
|---|---|
| `↑` / `↓` | Navigate folders and files |
| `Enter` | Open a folder |
| `Ctrl+S` | Save to the selected location |
| `Esc` | Cancel |

The artwork is saved as a `.jpg` file named after the album and artist. A confirmation toast appears when the download is complete.

---

## Dependencies

| Package | Purpose |
|---|---|
| `textual` | TUI framework |
| `textual-image` | Inline terminal image rendering |
| `rich` | Text styling and gradient logo |
| `pyfiglet` | ASCII art logo |
| `requests` | iTunes API calls and image downloading |
| `Pillow` | Image processing |

---

## How the API Works

PureArt uses Apple's public **iTunes Search API** — no API key or authentication required. Search results include a thumbnail artwork URL which PureArt then modifies to request the maximum available resolution from Apple's CDN:

```
100x100bb.jpg  →  10000x10000bb.jpg
```

Apple's CDN serves the highest resolution it has available for that specific release, typically between 1400×1400 and 3000×3000 pixels for most modern albums.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

## Author

Made by [Srikar Chundury](https://github.com/SrikarC6)