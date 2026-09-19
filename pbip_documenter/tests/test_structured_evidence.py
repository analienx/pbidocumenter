"""Structured PBIR evidence must not be confused with rendered-image evidence."""
from __future__ import annotations

from pathlib import Path

from pbip_documenter.quality_gate import source_digest
from pbip_documenter.visual_quality.structured_evidence import report_context

REPORT = Path(__file__).parents[2] / 'examples/contoso-retail/Contoso Retail.Report'


def test_context_contains_exact_page_and_visual_inventory():
    result = report_context(REPORT)
    assert result['source_sha256'] == source_digest(REPORT)
    assert len(result['pages']) == 5
    assert sum(len(page['visuals']) for page in result['pages']) == 54
    assert 'not visual or data approval' in result['kind']


def test_context_preserves_repaired_bar_roles_and_explicit_formats():
    page = next(p for p in report_context(REPORT)['pages'] if p['id'] == 'Products_brands')
    chart = next(v for v in page['visuals'] if v['visual_id'] == 'product-quality-growth')
    assert chart['visual_type'] == 'clusteredBarChart'
    assert chart['field_bindings']['Category'][0]['query_ref'] == 'Dim Product.Brand'
    assert chart['field_bindings']['Y'][0]['query_ref'] == 'Fact Sales.Reporting Year GM %'
    assert {x['path'] for x in chart['configured_visual_properties']} == {
        'visual.objects.categoryAxis[0].properties.showAxisTitle.expr.Literal.Value',
        'visual.objects.valueAxis[0].properties.showAxisTitle.expr.Literal.Value'}
    assert chart['evidence_limits']['pixel_readability'] == 'requires fresh rendered image'
    assert chart['evidence_limits']['data_values'] == 'requires a live semantic-model query'


def test_iteration_refreshes_visual_crops_after_each_report_render(tmp_path, monkeypatch):
    from pbip_documenter.visual_quality import runner, visual_evidence

    events = []
    monkeypatch.setattr(runner, '_adapter', lambda _spec, name, _ctx: events.append(name))
    monkeypatch.setattr(visual_evidence, 'crop_report_visuals',
                        lambda *_args: events.append('crop'))
    monkeypatch.setattr(runner, 'request',
                        lambda *_args: events.append('request') or {'schema': 1})
    monkeypatch.setattr(runner, 'audit', lambda *_args: {
        'source_sha256': 'fresh', 'findings': [], 'passed': True})
    result = runner.iterate({'surface': 'report', 'source': str(tmp_path / 'report.Report'),
                             'renders': str(tmp_path / 'renders'),
                             'workspace': str(tmp_path / 'work'),
                             'max_rounds': 1, 'fixer_id': 'repair-executor',
                             'crop_visuals': True})
    assert result['outcome'] == 'passed'
    assert events == ['renderer', 'crop', 'request', 'reviewer']
