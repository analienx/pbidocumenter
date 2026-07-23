# Contoso Retail sample

This fictional PBIP fixture is safe to share and exists for documentation and
smoke testing. It models a conventional retail star schema: `Fact Sales` holds
transactional measures and keys, while Date, Customer, Product, and Store are
single-direction dimensions. The report binds its visuals to these model
objects so generated documentation demonstrates relationships, DAX measures,
and report lineage.

```powershell
pbip-documenter examples/contoso-retail --mode full -o contoso-retail.docx
```
