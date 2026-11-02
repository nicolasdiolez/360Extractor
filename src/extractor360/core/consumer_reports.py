"""Read-only, bounded consumer evidence. No Qt, media decoding or external tools.

Membership is relative to one exported component/image set. Absence from a
registered-camera export does not prove that a solver rejected a submitted view.
"""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import struct
import tempfile
from typing import Any

MAX_BYTES = 16 * 1024**2
MAX_VIEWS = 20000
MAX_MEMBERSHIPS = 100000
MAX_REPORTS = 10
# COLMAP image_t/camera_t are uint32; only UINT32_MAX is the invalid sentinel.
# Native Postshot exports start both identifiers at zero.
INVALID_COLMAP_ID = 2**32 - 1
STATES = ('retained', 'rejected', 'not_retained', 'disabled', 'unknown')
FORMAT = '360-extractor-consumer-report'
RS_TEMPLATE = '''360EXTRACTOR_REALITYSCAN_V1
$IterateComponents(
COMPONENT\t$(componentGUID)\t$(componentName)
$SelectComponent("$(componentGUID)")
$IterateImages(
IMAGE\t$(componentGUID)\t$(inputImageName)$(inputImageExt)\t$(inputIsAligned)\t$(inputAlignmentEnabled)
)
)
'''


def _check(cancelled):
    if cancelled():
        raise InterruptedError('Report import cancelled')


def _read(path, cancelled=lambda: False):
    _check(cancelled)
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'Choose a regular report file: {path.name}')
    with path.open('rb') as handle:
        content = handle.read(MAX_BYTES + 1)
    _check(cancelled)
    if len(content) > MAX_BYTES:
        raise ValueError(f'{path.name} exceeds the 16 MiB import limit')
    return content


def _text(content):
    try:
        return content.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('Reports must be UTF-8 text (or COLMAP images.bin)') from exc


def _json(content):
    def invalid(value):
        raise ValueError(f'Nonfinite JSON value: {value}')
    try:
        return json.loads(_text(content), parse_constant=invalid)
    except RecursionError as exc:
        raise ValueError('Report structure is too deeply nested') from exc


def _string(value, label, maximum=4096):
    if not isinstance(value, str) or not value or len(value) > maximum or any(c in value for c in '\x00\r\n\t'):
        raise ValueError(f'Invalid {label}')
    return value


def _relative(value):
    _string(value, 'indexed image/mask name')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or ':' in value or path.as_posix() != value:
        raise ValueError('Indexed names must be normalized relative paths')
    return value


def _views(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_VIEWS:
        raise ValueError(f'Expected 1–{MAX_VIEWS} confirmed views')
    result, names, positions, masks = [], set(), set(), set()
    timing: dict[int, tuple[Any, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Invalid confirmed view')
        name = _relative(row.get('image'))
        frame, direction = row.get('frame'), row.get('camera')
        if type(frame) is not int or not 0 <= frame <= 2147483647:
            raise ValueError('Invalid confirmed source frame')
        _string(direction, 'camera direction', 128)
        if name in names or (frame, direction) in positions:
            raise ValueError('Duplicate image or capture/direction in confirmed index')
        names.add(name)
        positions.add((frame, direction))
        mask = row.get('mask')
        if mask is not None:
            _relative(mask)
            if mask in masks:
                raise ValueError('Duplicate mask in confirmed index')
            masks.add(mask)
        seconds, origin = row.get('timestamp_seconds'), row.get('timestamp_source', 'unavailable')
        if seconds is not None and (type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Invalid capture timestamp')
        _string(origin, 'timestamp source', 128)
        if frame in timing and timing[frame] != (seconds, origin):
            raise ValueError('Views of a capture disagree on their timestamp')
        timing[frame] = (seconds, origin)
        result.append(dict(image=name, mask=mask, frame=frame, camera=direction,
                           timestamp_seconds=seconds, timestamp_source=origin))
    return result


class _Names:
    def __init__(self, names):
        self.exact = set(names)
        self.basenames: dict[str, list[str]] = {}
        for name in self.exact:
            self.basenames.setdefault(PurePosixPath(name).name, []).append(name)

    def match(self, name):
        _string(name, 'reported filename')
        normalized = name.replace('\\', '/')
        if normalized in self.exact:
            return normalized
        matches = self.basenames.get(PurePosixPath(normalized).name, [])
        if len(matches) > 1:
            raise ValueError(f'Ambiguous reported basename: {name}')
        return matches[0] if matches else None


def _member(names, value, result, state='retained'):
    name = names.match(value)
    if name is None:
        raise ValueError(f'Report image is not in the selected confirmed index: {value}')
    if name in result:
        raise ValueError(f'Duplicate reported image: {value}')
    result[name] = state
    if len(result) > MAX_VIEWS:
        raise ValueError('Too many reported views')


def _boolean(value):
    if value.lower() not in ('true', 'false', '1', '0'):
        raise ValueError('RealityScan alignment flags must be true/false or 1/0')
    return value.lower() in ('true', '1')


def _realityscan(content, names, cancelled):
    text = _text(content)
    if text.lstrip().startswith('360EXTRACTOR_REALITYSCAN_V1'):
        models: dict[str, dict[str, Any]] = {}
        memberships = 0
        for line in text.strip().splitlines()[1:]:
            _check(cancelled)
            if not line.strip():
                continue
            fields = line.strip().split('\t')
            if fields[0] == 'COMPONENT' and len(fields) == 3:
                key, label = fields[1:]
                _string(key, 'component ID', 256)
                _string(label, 'component label', 256)
                if key in models or len(models) >= 128:
                    raise ValueError('Duplicate or excessive RealityScan components')
                models[key] = dict(id=key, label=label, absent_state='unknown', states={})
            elif fields[0] == 'IMAGE' and len(fields) == 5 and fields[1] in models:
                aligned, enabled = _boolean(fields[3]), _boolean(fields[4])
                state = 'retained' if aligned else 'rejected' if enabled else 'disabled'
                _member(names, fields[2], models[fields[1]]['states'], state)
                memberships += 1
                if memberships > MAX_MEMBERSHIPS:
                    raise ValueError('Too many component memberships')
            else:
                raise ValueError('Invalid RealityScan report row; export with the supplied template')
        if not models or any(not m['states'] for m in models.values()):
            raise ValueError('RealityScan report has no input identities for a component')
        return list(models.values())
    # Native ALIGNMENT > Export > Registration > Internal/External camera parameters.
    rows = csv.reader(io.StringIO(text), strict=True)
    try:
        header = next(rows)
        columns = [v.strip().lower().lstrip('#').strip() for v in header]
        if 'name' not in columns or len(set(columns)) != len(columns):
            raise ValueError('Expected RealityScan registration CSV with a #name column')
        index = columns.index('name')
        states: dict[str, str] = {}
        for row in rows:
            _check(cancelled)
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError('Truncated RealityScan registration CSV')
            _member(names, row[index], states)
    except (StopIteration, csv.Error) as exc:
        raise ValueError('Invalid RealityScan registration CSV') from exc
    if not states:
        raise ValueError('Registration CSV has no camera identities; use the full input-state report for failures')
    return [dict(id='registration', label='Exported registration', absent_state='not_retained', states=states)]


def _postshot_text(content, names, cancelled):
    states: dict[str, str] = {}
    lines = _text(content).splitlines()
    declared = None
    image_line = True
    ids = set()
    for line in lines:
        _check(cancelled)
        if line.startswith('#'):
            match = re.search(r'Number of images:\s*(\d+)', line)
            if match:
                declared = int(match[1])
            continue
        if image_line:
            fields = line.split(maxsplit=9)
            if len(fields) != 10:
                raise ValueError('Invalid COLMAP image row; choose images.txt, not cameras.txt')
            identifier, camera = int(fields[0]), int(fields[8])
            if (not 0 <= identifier < INVALID_COLMAP_ID or identifier in ids
                    or not 0 <= camera < INVALID_COLMAP_ID
                    or not all(math.isfinite(float(v)) for v in fields[1:8])):
                raise ValueError('Invalid COLMAP image ID or pose')
            ids.add(identifier)
            _member(names, fields[9], states)
        else:
            observations = line.split()
            if len(observations) % 3:
                raise ValueError('Truncated COLMAP observation row')
            for i in range(0, len(observations), 3):
                if not all(math.isfinite(float(v)) for v in observations[i:i+2]):
                    raise ValueError('Nonfinite COLMAP observation')
                int(observations[i+2])
        image_line = not image_line
    if not image_line or (declared is not None and declared != len(states)) or (not states and declared != 0):
        raise ValueError('Truncated or empty COLMAP images.txt')
    return states


def _postshot_binary(content, names, cancelled):
    stream = io.BytesIO(content)

    def unpack(fmt):
        size = struct.calcsize('<' + fmt)
        data = stream.read(size)
        if len(data) != size:
            raise ValueError('Truncated COLMAP images.bin')
        return struct.unpack('<' + fmt, data)

    count, = unpack('Q')
    if count > MAX_VIEWS:
        raise ValueError('Too many COLMAP images')
    states: dict[str, str] = {}
    ids = set()
    for _ in range(count):
        _check(cancelled)
        row = unpack('I7dI')
        if (row[0] == INVALID_COLMAP_ID or row[0] in ids or row[-1] == INVALID_COLMAP_ID
                or not all(math.isfinite(v) for v in row[1:8])):
            raise ValueError('Invalid COLMAP image ID or pose')
        ids.add(row[0])
        name = bytearray()
        while True:
            char = stream.read(1)
            if not char or len(name) > 4096:
                raise ValueError('Invalid COLMAP image name')
            if char == b'\0':
                break
            name.extend(char)
        _member(names, _text(bytes(name)), states)
        points, = unpack('Q')
        offset = stream.tell() + points * 24
        if offset > len(content):
            raise ValueError('Truncated COLMAP observations')
        stream.seek(offset)
    if stream.tell() != len(content):
        raise ValueError('Unexpected trailing COLMAP binary data')
    return states


def _log(content, views, cancelled):
    # Postshot appends sessions to one file. Older sessions may use a different
    # encoding; only the selected session must satisfy the UTF-8 contract.
    content = content.removeprefix(b'\xef\xbb\xbf')
    headers = list(re.finditer(rb'^\[0:00:00\.\d+\] (\d{4}-\d{2}-\d{2} [\d:]+ UTC)', content, re.M))
    scope = headers[-1].group(1).decode('ascii') if headers else 'entire supplied file (no UTC session header)'
    if headers:
        content = content[headers[-1].start():]
    text = _text(content)
    masks = _Names(v['mask'] for v in views if v['mask'])
    mask_views = {v['mask']: v['image'] for v in views if v['mask']}
    warnings = []
    for line in text.splitlines():
        _check(cancelled)
        if not re.search(r'\b(?:WARNING|ERROR)\b', line, re.I):
            continue
        is_mask = bool(re.search(r'\bmask\b', line, re.I))
        match = re.search(r"image mask\s+['\"](.+?)['\"]", line, re.I) if is_mask else None
        name = masks.match(match[1]) if match else None
        warnings.append(dict(kind='mask' if is_mask else 'consumer', message=line.replace('\t', ' ')[:4096],
                             image=mask_views.get(name), mapped=name is not None))
        if len(warnings) > 1000:
            raise ValueError('More than 1000 warnings; provide a narrower log')
    return scope, warnings


def import_report(dataset, consumer, report_path=None, log_path=None, cancelled=lambda: False):
    """Bind imported identities to a chosen confirmed export, not filename guesses.

    Names prove correspondence only, not pixel identity or solver-input provenance.
    The export's source identity and run/index digests remain in the saved receipt.
    """
    if consumer not in ('realityscan', 'postshot'):
        raise ValueError('Choose RealityScan or Postshot')
    if not report_path and not log_path:
        raise ValueError('Choose a camera/input report or a consumer log')
    root = Path(dataset)
    raw_manifest = _read(root / 'manifest.json', cancelled)
    manifest = _json(raw_manifest)
    if not isinstance(manifest, dict) or manifest.get('status') != 'completed':
        raise ValueError('Choose a completed 360 Extractor export')
    raw_index = _read(root / 'images.jsonl', cancelled)
    views = _views([_json(line.encode()) for line in _text(raw_index).splitlines() if line.strip()])
    extraction = manifest.get('extraction')
    if (not isinstance(extraction, dict) or type(extraction.get('images_written')) is not int
            or extraction['images_written'] != len(views)):
        raise ValueError('Confirmed index count disagrees with the completed manifest')
    names = _Names(v['image'] for v in views)
    models, inputs = [], []
    if report_path:
        content = _read(report_path, cancelled)
        if consumer == 'realityscan':
            models = _realityscan(content, names, cancelled)
        else:
            states = (_postshot_binary(content, names, cancelled) if Path(report_path).suffix.lower() == '.bin'
                      else _postshot_text(content, names, cancelled))
            models = [dict(id='image-set', label='Exported Image Set', absent_state='not_retained', states=states)]
        inputs.append(dict(name=Path(report_path).name, sha256=hashlib.sha256(content).hexdigest(), role='cameras'))
    scope, warnings = None, []
    if log_path:
        content = _read(log_path, cancelled)
        scope, warnings = _log(content, views, cancelled)
        inputs.append(dict(name=Path(log_path).name, sha256=hashlib.sha256(content).hexdigest(), role='log'))
    report = dict(format=FORMAT, schema_version=1, consumer=consumer,
                  dataset=dict(run_id=manifest.get('run_id'), source_identity=manifest.get('source_identity'),
                               manifest_sha256=hashlib.sha256(raw_manifest).hexdigest(),
                               index_sha256=hashlib.sha256(raw_index).hexdigest()),
                  inputs=inputs, views=views, models=models, warnings=warnings, log_scope=scope)
    return validate_report(report)


def validate_report(value):
    """Validate persisted facts without opening any path or trusting saved totals."""
    if not isinstance(value, dict) or value.get('format') != FORMAT or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported consumer report format/version')
    if value.get('consumer') not in ('postshot', 'realityscan'):
        raise ValueError('Invalid consumer')
    views = _views(value.get('views'))
    names = {v['image'] for v in views}
    dataset = value.get('dataset')
    if not isinstance(dataset, dict):
        raise ValueError('Invalid dataset receipt')
    _string(dataset.get('run_id'), 'export run ID', 256)
    identity = dataset.get('source_identity')
    if not isinstance(identity, dict) or any(type(identity.get(k)) is not int or identity[k] < 0 for k in ('size_bytes', 'mtime_ns')):
        raise ValueError('Invalid export source identity')
    for key in ('index_sha256', 'manifest_sha256'):
        if not isinstance(dataset.get(key), str) or not re.fullmatch('[0-9a-f]{64}', dataset[key]):
            raise ValueError('Invalid dataset digest')
    inputs = value.get('inputs')
    if not isinstance(inputs, list) or not 1 <= len(inputs) <= 2:
        raise ValueError('Invalid import receipt')
    for entry in inputs:
        if not isinstance(entry, dict) or entry.get('role') not in ('cameras', 'log'):
            raise ValueError('Invalid import receipt')
        _string(entry.get('name'), 'report filename')
        if not isinstance(entry.get('sha256'), str) or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
            raise ValueError('Invalid report digest')
    models = value.get('models')
    if not isinstance(models, list) or len(models) > 128:
        raise ValueError('Invalid consumer models')
    ids, memberships = set(), 0
    for model in models:
        if not isinstance(model, dict):
            raise ValueError('Invalid consumer model')
        key = _string(model.get('id'), 'model ID', 256)
        _string(model.get('label'), 'model label', 256)
        states = model.get('states')
        if key in ids or model.get('absent_state') not in ('unknown', 'not_retained') or not isinstance(states, dict):
            raise ValueError('Invalid or duplicate consumer model')
        ids.add(key)
        if any(name not in names or state not in STATES for name, state in states.items()):
            raise ValueError('Unknown image or state in consumer model')
        memberships += len(states)
    if memberships > MAX_MEMBERSHIPS:
        raise ValueError('Too many component memberships')
    warnings = value.get('warnings')
    if not isinstance(warnings, list) or len(warnings) > 1000:
        raise ValueError('Invalid consumer warnings')
    for warning in warnings:
        if not isinstance(warning, dict) or warning.get('kind') not in ('mask', 'consumer'):
            raise ValueError('Invalid consumer warning')
        _string(warning.get('message'), 'warning message')
        if warning.get('image') is not None and warning['image'] not in names:
            raise ValueError('Warning references an unknown image')
        if type(warning.get('mapped')) is not bool or warning['mapped'] != (warning.get('image') is not None):
            raise ValueError('Invalid warning association')
    if value.get('log_scope') is not None:
        _string(value['log_scope'], 'log scope', 256)
    return {**value, 'views': views}


def validate_reports(value):
    if not isinstance(value, list) or len(value) > MAX_REPORTS:
        raise ValueError(f'A source can retain at most {MAX_REPORTS} consumer reports')
    return [validate_report(report) for report in value]


def coverage(report, model_id=None):
    report = validate_report(report)
    model = next((m for m in report['models'] if m['id'] == model_id), None)
    if model_id is not None and model is None:
        raise ValueError('Unknown consumer model')
    states = model['states'] if model else {}
    absent = model['absent_state'] if model else 'unknown'
    rows = []
    captures: dict[int, Counter] = {}
    directions: dict[str, Counter] = {}
    for view in report['views']:
        state = states.get(view['image'], absent)
        rows.append({**view, 'state': state})
        captures.setdefault(view['frame'], Counter())[state] += 1
        directions.setdefault(view['camera'], Counter())[state] += 1
    return dict(views=rows, totals=dict(Counter(v['state'] for v in rows)),
                capture_totals=dict(exported=len(captures), any_retained=sum(v['retained'] > 0 for v in captures.values()),
                                    all_retained=sum(v['retained'] == sum(v.values()) for v in captures.values())),
                captures={str(k): dict(v) for k, v in sorted(captures.items())},
                directions={k: dict(v) for k, v in sorted(directions.items())})


def write_report(path, report):
    content = (json.dumps(validate_report(report), indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
    if len(content) > MAX_BYTES:
        raise ValueError('Saved report exceeds 16 MiB')
    _publish(path, content)


def write_template(path):
    _publish(path, RS_TEMPLATE.encode('utf-8'))


def _publish(path, content):
    """Stage first and publish exclusively; never replace an existing result."""
    import errno
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise FileExistsError(f'Choose a new filename: {target}')
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except OSError as exc:
            if exc.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP):
                raise
            handle = target.open('xb')
            identity = os.fstat(handle.fileno())
            try:
                with handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
            except OSError:
                try:
                    current = target.stat()
                    if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                        target.unlink()
                except OSError:
                    pass
                raise
    finally:
        Path(temporary).unlink(missing_ok=True)
