How To Contribute
=================

First off, thank you for considering contributing to ``bandcamp-dl``!
It's people like *you* who make it is such a great tool for everyone.

Here are a few guidelines to get you started (but don't be afraid to
open half-finished PRs and ask questions if something is unclear!):


Workflow
--------

- No contribution is too small!
  Please submit as many fixes for typos and grammar bloopers as you can!
- Try to limit each pull request to *one* change only.
- Once you've addressed review feedback, make sure to bump the pull 
  request with a short note.


Code
----

- To get started, use `uv sync` to install dev environment
  - If you don't know what uv is, check how uv projects work (`uv.lock`, `uv add`, `uv remove`, etc.) 
- To verify everything is correct, run `uv run pyrefly check`, `uv run ruff check --fix`, `uv run ruff format`
  - `pyrefly check`: runs static type analysis and is strict (annotations aren't optional)
  - `ruff check`: for conventions and possible bugs 
  - `ruff format`: for code formatting
- If you are using VSCode, you will be prompted to install pyrefly and ruff extensions upon opening the repo since it's convenient. 
  It's recommended to disable other lsps like Pylance so that the info you see in IDE is identical to what other devs and CI see ("python.languageServer": "None")

*****

Again, this list is mainly to help you to get started by codifying 
tribal knowledge and expectations. If something is unclear, feel free
to ask for help!

Thank you for considering contributing to ``bandcamp-dl``!
