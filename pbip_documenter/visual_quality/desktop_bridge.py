"""Fail-closed Power BI Desktop Bridge capture, independent of reviewer/model.

Bridge screenshots may include editing chrome; a calibrated canvas crop is
required unless the PNG already matches the PBIR canvas aspect ratio.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pbip_documenter.quality_gate import source_digest

from .evidence import digest, load, png_size


def _call(cli: Path, *args: str, timeout: int = 100) -> dict:
    result = subprocess.run([str(cli), *args], capture_output=True, text=True,
                            shell=False, timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError(f"Desktop Bridge {args[0]} failed: {result.stderr[-400:]}")
    data = json.loads(result.stdout.lstrip('\ufeff'))
    if data.get('status') not in ('ready', 'ok'):
        raise RuntimeError(f"Desktop Bridge {args[0]} returned non-ready status")
    return data


def capture(report: Path, pbip: Path, renders: Path, *, pid: int,
            cli: Path, scale: int = 2, crop: Path | None = None) -> dict:
    """Capture all declared pages with explicit PID, disk state and crop checks."""
    if pid <= 0 or scale not in (1, 2, 3) or not cli.is_file():
        raise ValueError('Explicit Desktop PID, scale 1..3 and installed CLI required')
    report, pbip, renders = report.resolve(), pbip.resolve(), renders.resolve()
    if not pbip.is_file() or report.parent != pbip.parent:
        raise ValueError('Report and PBIP must be the same local project')
    baseline = source_digest(report)
    status = _call(cli, 'status', '--pid', str(pid))
    instances = status.get('instances', [])
    if len(instances) != 1 or instances[0].get('pid') != pid:
        raise ValueError('Explicit PID did not resolve to one Desktop instance')
    instance = instances[0]
    if (instance.get('bridgeStatus') != 'connected' or
        os.path.normcase(os.path.normpath(instance.get('currentFilePath', ''))) !=
        os.path.normcase(os.path.normpath(str(pbip))) or
        os.path.normcase(os.path.normpath(instance.get('reportDir', ''))) !=
        os.path.normcase(os.path.normpath(str(report)))):
        raise ValueError('Desktop instance does not match the requested PBIP')
    if instance.get('hasUnsavedChanges') is not False:
        raise ValueError('Desktop has unsaved changes; in-memory pixels cannot certify disk source')
    ids = load(report / 'definition' / 'pages' / 'pages.json')['pageOrder']
    if [p['id'] for p in instance.get('pages', [])] != ids:
        raise ValueError('Desktop and PBIR page inventories differ')
    if crop is None:
        raise ValueError('Bridge includes Desktop chrome; explicit canvas calibration required')
    calibration = load(crop)
    box = calibration.get('rect')
    native = calibration.get('native_pixels')
    if (not isinstance(native, list) or len(native) != 2 or
        not isinstance(box, list) or len(box) != 4 or
        not all(type(x) is int and x > 0 for x in native) or
        not all(type(x) is int and x >= 0 for x in box)):
        raise ValueError('Invalid native screenshot dimensions or crop rectangle')
    reference = calibration.get('scale_one_canvas_pixels')
    if (not isinstance(reference, list) or len(reference) != 2 or
        not all(type(value) is int and value > 0 for value in reference)):
        raise ValueError('Canvas calibration requires independently measured scale_one_canvas_pixels')
    x, y, width, height = box
    if (abs(width - reference[0] * scale) > 2 or
        abs(height - reference[1] * scale) > 2):
        raise ValueError('Canvas crop dimensions disagree with independent scale-one calibration')
    if (not width or not height or x + width > native[0] or y + height > native[1]):
        raise ValueError('Canvas crop lies outside the calibrated screenshot')
    import re

    from PIL import Image
    renders.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pbip-bridge-') as folder:
        staging = Path(folder)
        results: dict[str, str] = {}
        for ordinal, item in enumerate(instance['pages'], start=1):
            page = load(report / 'definition' / 'pages' / item['id'] / 'page.json')
            expected_ratio = page['width'] / page['height']
            if abs(width / height / expected_ratio - 1) > 0.01:
                raise ValueError('Calibrated crop does not match the PBIR canvas ratio')
            slug = re.sub('[^a-z0-9]+', '-', page['displayName'].lower()).strip('-')
            name = f'{ordinal:02d}-{slug}.png'
            raw = staging / ('raw-' + name)
            response = _call(cli, 'screenshot', item['id'], '--pid', str(pid),
                             '--scale', str(scale), '--output', str(raw),
                             '--wait-seconds', '60', timeout=95)
            if response.get('pageId') != item['id'] or not raw.is_file():
                raise ValueError('Bridge returned a different page or no screenshot')
            if png_size(raw) != tuple(native):
                raise ValueError('Native screenshot resolution changed; recalibrate the crop')
            with Image.open(raw) as picture:
                picture.load()
                clipped = picture.crop((x, y, x + width, y + height))
                out = staging / name
                clipped.save(out, format='PNG')
            if png_size(out) != (width, height):
                raise ValueError('Canvas extraction did not produce the expected dimensions')
            results[name] = digest(out)
        if source_digest(report) != baseline:
            raise RuntimeError('PBIR or semantic model changed during capture')
        after = _call(cli, 'status', '--pid', str(pid))
        current = after.get('instances', [])
        if (len(current) != 1 or current[0].get('hasUnsavedChanges') is not False or
            os.path.normcase(os.path.normpath(current[0].get('currentFilePath', ''))) !=
            os.path.normcase(os.path.normpath(str(pbip)))):
            raise RuntimeError('Desktop session changed or acquired unsaved edits during capture')
        for name in results:
            os.replace(staging / name, renders / name)
    manifest = {'schema': 1, 'source_sha256': baseline,
                'captured_at_utc': datetime.now(timezone.utc).isoformat(),
                'capture': 'Desktop Bridge 0.1.2 with explicit PID, calibrated canvas crop',
                'desktop_pid': pid, 'desktop_pbip': str(pbip),
                'native_pixels': native, 'canvas_crop': box,
                'canvas_pixels': [width, height], 'files': results,
                'readiness': 'Rendered evidence only; no visual, model or data acceptance.'}
    target = renders / 'capture-manifest.json'
    with tempfile.NamedTemporaryFile(dir=renders, suffix='.json-tmp', mode='w',
                                     encoding='utf-8', delete=False) as handle:
        json.dump(manifest, handle, indent=2)
        temporary = Path(handle.name)
    os.replace(temporary, target)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Calibrated Desktop Bridge capture')
    parser.add_argument('--source', type=Path, required=True, help='PBIR *.Report directory')
    parser.add_argument('--pbip', type=Path, required=True, help='The exact open PBIP path')
    parser.add_argument('--renders', type=Path, required=True)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--cli', type=Path, required=True, help='Installed powerbi-desktop CLI')
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--scale', type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args(argv)
    result = capture(args.source, args.pbip, args.renders, pid=args.pid,
                     cli=args.cli, scale=args.scale, crop=args.calibration)
    print(json.dumps({'pages': len(result['files']), 'source_sha256': result['source_sha256'],
                      'render_mode': result['capture']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
