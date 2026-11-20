"""Compatibility entry point; detect the current patch without source rewriting."""
from draft_assistant.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["--update-meta"]))
