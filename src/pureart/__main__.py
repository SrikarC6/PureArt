"""Entry point for PureArt — invoked by `pureart` command or `python -m pureart`."""

from pureart.frontend import PureArt


def main() -> None:
    PureArt().run()


if __name__ == "__main__":
    main()
