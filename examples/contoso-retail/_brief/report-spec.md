# Contoso Retail — Report Redesign Plan

Supervisor issue #4 requires a materially better, light-editorial Power BI report
that supports this page story: outcome → driver → segment → operational issue.
This doc is the **dashboard-design pass** (run before PBIR implementation) and the
authoritative **Canonical design contract** for `powerbi-report-authoring`.

## 1. Design identity

- **Tone:** light editorial / executive analytics — "strategy consulting product",
  not a default dashboard.
- **Signature:** quality-of-growth scatter (Growth% × GM%) with reference lines,
  plus sorted horizontal bars and restrained status color. Reused on Markets,
  Products, and Customer pages.
- **Current (brownfield) tone:** dark `#0B1220` canvas, `#111B2E` panels, `#26364D`
  borders, gradient blue bars, one donut, hidden headers, manual per-visual titles.
- **Target:** light surfaces, semantic color, descriptive insight titles, no
  decorative donuts, no gradient magnitude fills.

## 2. Canvas & grid (brownfield — preserved)

- Canvas **1280 × 720**, FitToPage. Page margin **24**, gutter **16**, snap **8**.
- 12-column grid, ~88 px columns (content width 1232 px).
- KPI card = 3 cols (296 px) · 4-col visual = 400 px · 6-col = 608 px · 8-col = 816 px.

## 3. Color map (implementation contract)

| Token | Hex | Use |
|---|---|---|
| Actual / primary series | `#2563EB` | Sales, primary bars/lines (tint `#DBEAFE`) |
| Prior year / comparison | `#94A3B8` | LY series, neutral refs (tint `#E2E8F0`) |
| Budget / plan | `#7C3AED` | Budget series, attainment (tint `#EDE9FE`) |
| Margin / profitability | `#0F766E` | GM measures (tint `#CCFBF1`) |
| Positive variance | `#15803D` | upside exceptions (bg `#ECFDF3`) |
| Negative variance | `#B91C1C` | downside exceptions (bg `#FEF2F2`) |
| Warning | `#B45309` | needs attention (bg `#FFFBEB`) |
| Neutral / target line | `#64748B` | reference lines, dividers (bg `#F8FAFC`) |
| Canvas / card / section | `#F6F8FB` / `#FFFFFF` / `#EEF2F7` | surfaces |
| Text primary / secondary / muted | `#172033` / `#64748B` / `#94A3B8` | type |
| Divider / border | `#E2E8F0` | 1 px, radius ≤8 on normal charts |

Rule: ~80% neutral surfaces + 15% primary + 5% status; red/green only for
performance meaning; same Actual/Prior/Budget colors on every page; target = thin
dashed neutral line, not a saturated series.

## 4. Typography (Segoe UI)

Page title 26 pt Semibold; subtitle 12 pt Regular secondary; section 15 pt
Semibold; visual title 13 pt Semibold; KPI callout 28 pt Semibold; KPI label
11 pt; table/axis 10–11 pt; nothing below 10 pt except dense metadata.
Visual titles = insight sentences, not field names.

## 5. Page-by-page plan

Page consolidation: the two duplicate pages (Inventory_suppliers, Returns_promotions
— both relabeled copies showing only Fact Sales) are **removed**; a single new
**Operations & risk** page is authored for Returns + Inventory. Final = **5 pages**.

### Page 1 — Executive performance (existing `Executive_overview`, rename display)
Q: Are we on plan, growing profitably, where is attention required?
- **KPI row (4 cards):** Sales (+YoY), Sales vs Budget (variance $/%), Gross Margin %
  (+gap to 35% target), Return Rate (+YoY delta).
- **Hero (8-col):** monthly Actual vs Budget vs Prior line combo; tooltip =
  Sales, Budget variance, GM%, Return Rate. Title states the trend conclusion.
- **Driver (4-col):** budget→actual variance by region (waterfall or sorted bar).
- **Bottom (6+6):** quality-of-growth scatter (Growth% X, GM% Y, size Sales, entity
  Region) + Executive action list (top 5–8 exceptions: entity, var %, GM gap,
  return rate, status).

### Page 2 — Markets & stores (rename `Markets_drivers`)
Q: Which markets create high-quality growth, destroy value, why?
- **KPI row:** Sales, YoY Growth %, GM %, Budget Variance %.
- **Hero scatter:** YoY% × GM%, size Sales, entity Store/Region, ref lines 0% + target.
- **Budget variance:** sorted horizontal bars (worst→best), green/red, zero ref line.
- **Channel mix:** 100% stacked horizontal bar (replaces the donut).
- **Action table:** Store/Region + Sales, YoY%, GM%, Budget Var%, Return Rate,
  contribution; conditional formatting on variance columns only.

### Page 3 — Products & brands (existing `Products_brands`)
Q: What to grow, defend, fix, rationalize?
- **KPI row:** Product Sales, YoY Growth %, GM %, Product Return Rate or Promo share.
- **Portfolio matrix (hero scatter):** YoY% × GM%, size Sales, entity Category/Brand,
  ref lines 0% + target → stars/defend/fix/rationalize.
- **Contribution / mix shift:** sorted horizontal bars (category contribution + chg vs LY).
- **Promotion economics:** promoted vs non-promo sales, promo GM%, margin dilution pp.
- **Returns leakage:** category return rate + return value.
- **Action table:** Category/Product + Sales, YoY%, GM%, GM gap, Return Rate, Budget Var%.

### Page 4 — Customers & value (rename `Stores_customers`)
Q: Who creates customer value, is the base healthier, which behaviors explain it?
- **KPI row:** Active Customers, Sales per Active Customer, Avg Order Value,
  Repeat Customer Rate.
- **Value matrix (hero scatter):** X orders per customer, Y Sales per Customer,
  size Sales, entity Customer segment.
- **Contribution/ranking + action table** (do not duplicate store sales from Page 2).

### Page 5 — Operations & risk (NEW; replaces the two duplicate pages)
Q: Where is revenue leaking via returns, where is working capital at risk?
- **KPI row:** Return Rate %, Return Value, Inventory Value, Stock risk
  (excess + low-stock SKU count).
- **Returns:** return-rate trend, return-reason contribution (sorted bar), return
  rate by category/store with exceptions.
- **Inventory:** risk scatter (demand X, weeks of cover Y, size inventory value)
  + inventory KPI assemblage (turnover, excess/low-stock).
- **Action table:** SKU/store/category exceptions with return + inventory risk.

## 6. Interaction & navigation

- Compact top filter strip (right side of header band): Reporting year (Dim Date.Year
  dropdown) page-wide; Category / Region / Store / Customer-segment slicers are
  **page-specific**.
- Slicers stay compact; slicers never dominate content; drill-through only where a
  natural follow-up exists; no gimmick interactions.

## 7. Implementation notes (for authoring)

- Replace the dark theme with a light theme from the token table (or keep the custom
  theme name but override surface/text/palette tokens). Preserve `assets/base.json`
  per-type safeguards (textbox/card padding, hidden headers).
- **Remove** donut (`channel-mix-donut` + duplicate `market-drivers`), the disabled
  decomposition tree, and the two duplicate pages.
- Audit every field label → human-readable display names; percentages formatted
  `0.0%`; visuals get insight titles and hidden headers.
- Use conditional formatting only on variance/status (semantic color), never
  categorical rainbow.

---

# Canonical design contract

```yaml
Design Brief:
  generated_by: powerbi-report-design
  contract_version: 1
  mode: brownfield
  design_identity:
    tone: light-editorial executive analytics
    signature: quality-of-growth scatter + sorted horizontal bars, restrained status color
    current_tone: dark uniformly-boxed dashboard (#0B1220 canvas, #111B2E panels)
    current_signature: gradient blue bars, donut, hidden headers, manual per-visual titles
  archetype: Executive Summary
  color_map:
    - { measure: Sales[Reporting-Year Sales], color: "#2563EB", tint: "#DBEAFE" }
    - { measure: Sales[Prior-Year Sales], color: "#94A3B8", tint: "#E2E8F0" }
    - { measure: Budget, color: "#7C3AED", tint: "#EDE9FE" }
    - { measure: Margin, color: "#0F766E", tint: "#CCFBF1" }
    - { measure: Positive-Variance, color: "#15803D", tint: "#ECFDF3" }
    - { measure: Negative-Variance, color: "#B91C1C", tint: "#FEF2F2" }
    - { measure: Warning, color: "#B45309", tint: "#FFFBEB" }
  theme:
    base: ContosoExecutive-4f18b4d2.json (re-tokenized light) + assets/base.json safeguards
    canvas: "#F6F8FB"
    surfaces: { card: "#FFFFFF", section: "#EEF2F7", divider: "#E2E8F0" }
  pages:
    - name: Executive performance
      role: landing
      archetype: Executive
      layout_variant: B
      variant_rationale: "A trend hero plus a budget-variance driver explains the headline, per issue spec."
      page_background: "#F6F8FB"
      layout_contract:
        canvas: { width: 1280, height: 720, margin: 24, gutter: 16, snap: 8 }
        grid: { columns: 12, rows: 12,
          regions: { header: [1,1,10,2], filters: [10,1,13,2], kpis: [1,2,13,3],
            hero: [1,3,9,8], driver: [9,3,13,8], bottom: [1,8,13,13] } }
        placements:
          - { id: page_title, region: header, kind: textbox, text: "Sales are above plan but momentum softened in Q4" }
          - { id: year_slicer, region: filters, kind: slicer, field_bindings: "Dim Date[Year]", slicer_type: dropdown, slot: 1, of: 1 }
          - { id: kpi_sales, region: kpis, kind: cardVisual, field_bindings: "Fact Sales[Sales]", color_strategy: measure_match, slot: 1, of: 4, insight_basis: "Sales + YoY delta" }
          - { id: kpi_budget, region: kpis, kind: cardVisual, field_bindings: "Fact Sales Budget[Budget Variance %]", color_strategy: semantic, slot: 2, of: 4, insight_basis: "Variance $/% + attainment" }
          - { id: kpi_gm, region: kpis, kind: cardVisual, field_bindings: "Fact Sales[Reporting Year GM %]", color_strategy: measure_match, slot: 3, of: 4, insight_basis: "GM% + gap to 35% target" }
          - { id: kpi_return, region: kpis, kind: cardVisual, field_bindings: "Fact Returns[Return Rate %]", color_strategy: semantic, slot: 4, of: 4, insight_basis: "Return rate + YoY delta" }
          - { id: trend, region: hero, kind: lineChartCombination, purpose: "Monthly actual vs budget vs prior, with sales/GM%/return tooltip", field_bindings: { Category: "Dim Date[Year Month]", Y: ["Fact Sales[Sales]","Fact Sales Budget[Sales Budget]","Fact Sales[Reporting Year Sales LY]"] }, color_strategy: ["#2563EB","#7C3AED","#94A3B8"] }
          - { id: variance_driver, region: driver, kind: waterfallChart, purpose: "Which region explains the budget miss/beat", field_bindings: { Category: "Dim Store[Region]", Y: "Fact Sales Budget[YTD Actual vs Budget]" }, color_strategy: semantic }
          - { id: quality_scatter, region: bottom, kind: scatterChart, purpose: "Quality of growth by region", field_bindings: { X: Yoy%, Y: GM%, Size: Sales, Entity: Region }, color_strategy: semantic, comparison_basis: "0% growth + 35% margin target" }
          - { id: action_list, region: bottom, kind: tableEx, purpose: "Top exceptions to act on", field_bindings: [Region, "Sales Var %", "GM gap", "Return Rate", Status], color_strategy: semantic }
        space_audit:
          content_cell_count: 132
          placed_cell_count: 132
          empty_cell_pct: 0
          unplaced_regions: []
          largest_region: { name: bottom, pct_of_content: 42 }
          balance_rationale: "KPI strip, hero trend, budget-driver panel, and action row fill the content area without a dead band."
      interaction_pattern: { cross_filter_rules: "All visuals cross-highlight by default" }
      accessibility:
        alt_text_strategy: headline+trend
        contrast_notes: "Light canvas, #172033 body text; semantic color only on small variance glyphs/cells."