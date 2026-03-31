"""PureArt — TUI app to download high-resolution album artwork."""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("pureart")
except PackageNotFoundError:
    __version__ = "unknown"
