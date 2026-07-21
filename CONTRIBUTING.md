# Contributing

Use Python 3.10–3.13 and install all development dependencies:

```powershell
python -m pip install -e ".[all]"
python -m pytest pbip_documenter/tests
ruff check .
mypy pbip_documenter
```

Keep pull requests focused, add regression coverage for behavior changes, and
use only fictional or redacted PBIP artifacts. Run the Contoso sample after
changes that affect parsing or Word rendering.
