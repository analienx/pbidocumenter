"""Desktop Bridge capture must reject incorrect instances and stale evidence."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from pbip_documenter.quality_gate import source_digest
from pbip_documenter.visual_quality import desktop_bridge as bridge
from pbip_documenter.visual_quality.evidence import load

ROOT = Path(__file__).parents[2] / 'examples' / 'contoso-retail'


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, unsaved: bool = False):
    project = tmp_path / 'project'
    project.mkdir()
    shutil.copytree(ROOT / 'Contoso Retail.Report', project / 'Contoso Retail.Report')
    shutil.copytree(ROOT / 'Contoso Retail.SemanticModel', project / 'Contoso Retail.SemanticModel')
    pbip = project / 'Contoso Retail.pbip'
    pbip.write_text('{}', encoding='utf-8')
    report = project / 'Contoso Retail.Report'
    ids = load(report / 'definition/pages/pages.json')['pageOrder']
    calibration = tmp_path / 'calibration.json'
    calibration.write_text(json.dumps({'native_pixels': [1400, 900], 'rect': [0, 100, 1280, 720]}))
    cli = tmp_path / 'bridge.cmd'
    cli.write_text('stub', encoding='utf-8')
    instance = {'pid': 42, 'bridgeStatus': 'connected', 'currentFilePath': str(pbip),
                'reportDir': str(report), 'hasUnsavedChanges': unsaved,
                'pages': [{'id': i} for i in ids]}

    def fake_call(_cli: Path, command: str, *args: str, **_kwargs):
        if command == 'status':
            return {'status': 'ready', 'instances': [instance]}
        if command == 'screenshot':
            raw = Path(args[args.index('--output') + 1])
            Image.new('RGB', (1400, 900), (255, 255, 255)).save(raw)
            return {'status': 'ok', 'pageId': args[0]}
        raise AssertionError(f'Unexpected Bridge command: {command}')

    monkeypatch.setattr(bridge, '_call', fake_call)
    return report, pbip, cli, calibration, instance


def test_bridge_binds_five_canvas_images_to_exact_source(tmp_path, monkeypatch):
    report, pbip, cli, calibration, _ = _setup(tmp_path, monkeypatch)
    renders = tmp_path / 'renders'
    result = bridge.capture(report, pbip, renders, pid=42, cli=cli, crop=calibration)
    assert result['source_sha256'] == source_digest(report)
    assert len(result['files']) == 5
    assert all((renders / name).is_file() for name in result['files'])
    assert all(Image.open(renders / name).size == (1280, 720) for name in result['files'])
    assert load(renders / 'capture-manifest.json')['files'] == result['files']


def test_bridge_rejects_unsaved_or_wrong_instance(tmp_path, monkeypatch):
    report, pbip, cli, calibration, state = _setup(tmp_path, monkeypatch, unsaved=True)
    with pytest.raises(ValueError, match='unsaved'):
        bridge.capture(report, pbip, tmp_path / 'renders', pid=42, cli=cli, crop=calibration)
    state['hasUnsavedChanges'] = False
    state['currentFilePath'] = str(tmp_path / 'other.pbip')
    with pytest.raises(ValueError, match='does not match'):
        bridge.capture(report, pbip, tmp_path / 'renders', pid=42, cli=cli, crop=calibration)


def test_bridge_requires_calibration_and_current_inventory(tmp_path, monkeypatch):
    report, pbip, cli, calibration, state = _setup(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match='calibration'):
        bridge.capture(report, pbip, tmp_path / 'renders', pid=42, cli=cli)
    state['pages'] = state['pages'][:-1]
    with pytest.raises(ValueError, match='inventories differ'):
        bridge.capture(report, pbip, tmp_path / 'renders', pid=42, cli=cli, crop=calibration)
    state['pages'] = [{'id': i} for i in load(report / 'definition/pages/pages.json')['pageOrder']]
    calibration.write_text(json.dumps({'native_pixels': [1400, 900], 'rect': [0, 100, 1250, 720]}))
    with pytest.raises(ValueError, match='canvas ratio'):
        bridge.capture(report, pbip, tmp_path / 'renders', pid=42, cli=cli, crop=calibration)
    assert not (tmp_path / 'renders' / 'capture-manifest.json').exists()
