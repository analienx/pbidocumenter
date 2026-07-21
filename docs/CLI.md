# CLI reference

```text
pbip-documenter [reports_dir] [--mode default|full] [-o OUTPUT]
                [--logo LOGO] [--template TEMPLATE] [--version]
```

`reports_dir` may be a PBIP project folder or a directory containing projects.
When omitted, the command uses `PBIP_REPORTS` or a sibling `Reports/` folder.
It exits with status `2` when the directory is missing or contains no valid
project.

| Option | Purpose |
| --- | --- |
| `--mode full` | Include expanded technical detail. |
| `-o`, `--output` | Write to an explicit `.docx` path. |
| `--logo` | Add a logo image to the document header. |
| `-t`, `--template` | Use a Word template. |
| `--version` | Print the installed package version. |
