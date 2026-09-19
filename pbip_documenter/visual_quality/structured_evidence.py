"""Source-grounded PBIR context for vision review and separate repair planning.

PBIR describes intended configuration, NOT what rendered. DAX values and axis
pixel legibility must be checked through a live model query and page image.
"""
from __future__ import annotations

from pathlib import Path

from pbip_documenter.quality_gate import source_digest

from .evidence import load


def _property_literals(node: object, path: str = '', limit: int = 50) -> list[dict]:
    """Extract actual configured literals, without hallucinating absent styles."""
    found: list[dict] = []
    def walk(value: object, key: str, depth: int) -> None:
        if len(found) >= limit or depth > 16:
            return
        if isinstance(value, dict):
            literal = value.get('Literal')
            if isinstance(literal, dict) and 'Value' in literal:
                text = str(literal['Value'])
                if len(text) <= 180:
                    found.append({'path': key + '.Literal.Value', 'value': text})
                return
            for name, child in value.items():
                walk(child, f'{key}.{name}' if key else name, depth + 1)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f'{key}[{index}]', depth + 1)
    walk(node, path, 0)
    return found


def visual_context(visual: dict) -> dict:
    """Report only facts explicitly present in a PBIR visual definition."""
    view = visual.get('visual', {})
    bindings = {}
    for role, spec in view.get('query', {}).get('queryState', {}).items():
        bindings[role] = [
            {'query_ref': projection.get('queryRef', ''),
             'field': projection.get('field', {}),
             'active': projection.get('active', True)}
            for projection in spec.get('projections', [])
        ]
    return {'visual_id': visual['name'], 'visual_type': view.get('visualType', ''),
            'position': visual['position'], 'field_bindings': bindings,
            'sort_definition': view.get('query', {}).get('sortDefinition'),
            'configured_visual_properties': _property_literals(view.get('objects', {}), 'visual.objects'),
            'configured_container_properties': _property_literals(
                view.get('visualContainerObjects', {}), 'visual.visualContainerObjects'),
            'evidence_limits': {'pixel_readability': 'requires fresh rendered image',
                                'data_values': 'requires a live semantic-model query',
                                'missing_property': 'may be inherited from theme or defaults'}}


def report_context(report: Path) -> dict:
    """Pure read-only inventory; no Desktop instance or credentials required."""
    pages_root = report / 'definition' / 'pages'
    pages = []
    for page_id in load(pages_root / 'pages.json')['pageOrder']:
        page_dir = pages_root / page_id
        page = load(page_dir / 'page.json')
        visuals = [visual_context(load(path)) for path in sorted(
            (page_dir / 'visuals').glob('*/visual.json'))]
        pages.append({'id': page_id, 'display_name': page['displayName'],
                      'canvas': [page['width'], page['height']], 'visuals': visuals})
    return {'schema': 1, 'kind': 'PBIR source metadata, not visual or data approval',
            'source_sha256': source_digest(report), 'pages': pages}
