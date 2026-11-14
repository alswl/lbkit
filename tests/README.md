# Unit tests

Run `uv run --locked python -m unittest discover tests`.

Keep tests focused on a single component: document parsing, reducer transitions,
version metadata helpers or adapters with mocked transport. Temporary input files
are acceptable when testing a file-oriented component.

CLI and installer execution, workflows spanning services or persistent state,
and real Herdr/model acceptance live in the external verification repository.
Using a fake executable does not make those workflows unit tests. Shared unit
fixtures contain plain data and must not import integration harnesses.
