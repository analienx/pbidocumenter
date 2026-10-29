# Example outputs

The public repository uses the fictional [Contoso Retail sample](../examples/contoso-retail/).

```powershell
pbip-documenter examples/contoso-retail --mode default -o contoso-default.docx
pbip-documenter examples/contoso-retail --mode full -o contoso-full.docx
```

The full document includes the semantic model, DAX inventory, report-page
wireframe, lineage, and observations.

GitHub-hosted CI generates the DOCX and renders every page with LibreOffice
to PDF and page JPEGs, uploading short-retention review artifacts. The acceptance
check compares PBIP pages, table/measure/relationship and visual inventories
with the generated document and rendered PDF.

**LibreOffice output is engineering evidence, not Microsoft Word-exact
pagination certification.** Final Word appearance and editorial approval
still require examining rendered pages in the target environment.

PBIP source cannot establish business exclusions, operational refresh SLAs,
or users' intentions. These fields are left for the report owner to confirm.
