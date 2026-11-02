"""Consumer identity imports must not turn missing evidence into solver failures."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from extractor360.core.consumer_reports import (coverage, import_report, validate_report, write_report,
                                                write_template)
from extractor360.core.job import Job
from extractor360.core.project import Project, read_project, relink_source, source_identity, write_project


@pytest.fixture
def dataset(tmp_path):
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'original fixture media')
    root = tmp_path / 'dataset'
    root.mkdir()
    manifest = dict(status='completed', run_id='test-run', source_identity=source_identity(str(source)),
                    extraction={'images_written': 6})
    (root / 'manifest.json').write_text(json.dumps(manifest))
    rows = [dict(image=f'capture {f}_{d}.jpg', frame=f, camera=d,
                 mask=f'capture {f}_{d}.mask.png' if d == 'Down' else None,
                 timestamp_seconds=f / 25, timestamp_source='decoder_timestamp') for f in [0, 5, 11] for d in ['Left', 'Down']]
    (root / 'images.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    return root


def text_model(path, names):
    path.write_text(f'# Number of images: {len(names)}, mean observations per image: 0\n' + ''.join(
        f'{i+1} 1 0 0 0 0 0 0 1 {name}\n\n' for i, name in enumerate(names)))
    return path


def rs_report(path):
    path.write_text('360EXTRACTOR_REALITYSCAN_V1\nCOMPONENT\ta\tMain\n'
                    'IMAGE\ta\tC:\\data\\capture 0_Left.jpg\ttrue\ttrue\n'
                    'IMAGE\ta\tcapture 0_Down.jpg\tfalse\ttrue\n'
                    'IMAGE\ta\tcapture 5_Down.jpg\tfalse\tfalse\n'
                    'COMPONENT\tb\tAlternative\nIMAGE\tb\tcapture 0_Down.jpg\ttrue\ttrue\n')
    return path


def test_realityscan_components_keep_rejected_disabled_and_unknown_separate(dataset, tmp_path):
    report = import_report(dataset, 'realityscan', rs_report(tmp_path / 'rs.txt'))
    a, b = coverage(report, 'a'), coverage(report, 'b')
    assert a['totals'] == {'retained': 1, 'rejected': 1, 'unknown': 3, 'disabled': 1}
    assert b['totals'] == {'unknown': 5, 'retained': 1}
    assert a['captures']['0'] == {'retained': 1, 'rejected': 1}
    assert b['directions']['Down'] == {'retained': 1, 'unknown': 2}
    assert coverage(report)['totals'] == {'unknown': 6}  # No union across components.


def test_realityscan_native_csv_and_windows_paths(dataset, tmp_path):
    path = tmp_path / 'registration.csv'
    path.write_text('#name,x,y,alt,heading,pitch,roll\n"D:\\images\\capture 0_Left.jpg",0,0,0,0,0,0\n')
    report = import_report(dataset, 'realityscan', path)
    assert coverage(report, 'registration')['totals'] == {'retained': 1, 'not_retained': 5}
    assert report['log_scope'] is None


def test_realityscan_template_preserves_documented_filename_extension(dataset, tmp_path):
    template = tmp_path / 'template.txt'
    write_template(template)
    # RealityScan's documented SaveImage example concatenates name and extension
    # directly: inputImageExt includes the leading dot. Exercise the emitted row
    # through the importer, rather than using a separately hand-written filename.
    rows = [line for line in template.read_text().splitlines() if line.startswith(('COMPONENT\t', 'IMAGE\t'))]
    content = '360EXTRACTOR_REALITYSCAN_V1\n' + '\n'.join(rows)
    values = dict(componentGUID='a', componentName='Main', inputImageName='capture 0_Left',
                  inputImageExt='.jpg', inputIsAligned='true', inputAlignmentEnabled='true')
    for key, value in values.items():
        content = content.replace('$(' + key + ')', value)
    path = tmp_path / 'input-states.txt'
    path.write_text(content)
    report = import_report(dataset, 'realityscan', path)
    assert report['models'][0]['states'] == {'capture 0_Left.jpg': 'retained'}


@pytest.mark.parametrize('binary', [False, True])
def test_postshot_camera_exports_and_mask_log(dataset, tmp_path, binary):
    name = 'capture 5_Down.jpg'
    if binary:
        path = tmp_path / 'images.bin'
        path.write_bytes(struct.pack('<Q', 1)+struct.pack('<i7di', 2, 1, 0, 0, 0, 0, 0, 0, 1)+name.encode()+b'\0'+struct.pack('<Q', 0))
    else:
        path = text_model(tmp_path / 'images.txt', [name])
    log = tmp_path / 'Postshot.log'
    log.write_text("[0:00:00.001] 2026-10-31 01:00:00 UTC\n[0:01:00.000] WARNING: old warning\n"
                   "[0:00:00.001] 2026-11-01 21:23:32 UTC\n"
                   "[0:19:08.455] WARNING: no matching image found for image mask 'C:\\inputs\\capture 5_Down.mask.png'\n"
                   "[0:19:08.456] WARNING: no matching image found for image mask 'C:\\other\\foreign.mask.png'\n")
    report = import_report(dataset, 'postshot', path, log)
    assert coverage(report, 'image-set')['totals'] == {'not_retained': 5, 'retained': 1}
    assert len(report['warnings']) == 2 and report['warnings'][0]['image'] == name
    assert report['warnings'][1]['mapped'] is False
    assert report['log_scope'] == '2026-11-01 21:23:32 UTC'
    assert report['inputs'][0]['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    log_only = import_report(dataset, 'postshot', log_path=log)
    assert log_only['models'] == [] and coverage(log_only)['totals'] == {'unknown': 6}


@pytest.mark.parametrize('data', ['# Number of images: 1\n1 1 0 0 0 0 0 0 1 capture 0_Left.jpg\n',
                                  '# Number of images: 2\n1 1 0 0 0 0 0 0 1 capture 0_Left.jpg\n\n',
                                  '1 nan 0 0 0 0 0 0 1 capture 0_Left.jpg\n\n', '',
                                  '1 1 0 0 0 0 0 0 1 foreign.jpg\n\n'])
def test_postshot_rejects_truncated_nonfinite_foreign_or_unrecognized_data(dataset, tmp_path, data):
    path = tmp_path / 'images.txt';path.write_text(data)
    with pytest.raises(ValueError):
        import_report(dataset, 'postshot', path)


def test_empty_registered_set_requires_declared_zero(dataset, tmp_path):
    path = text_model(tmp_path / 'images.txt', [])
    report = import_report(dataset, 'postshot', path)
    assert coverage(report, 'image-set')['totals'] == {'not_retained': 6}


def test_log_ignores_encoding_of_older_sessions_but_not_current_scope(dataset, tmp_path):
    log = tmp_path / 'Postshot.log'
    old = b'[0:00:00.001] 2026-11-01 21:23:32 UTC\nWARNING: ancien chemin accentu\xe9\n'
    current = (b'[0:00:00.001] 2026-11-02 09:26:09 UTC\n'
               b"WARNING: no matching image found for image mask 'capture 5_Down.mask.png'\n")
    for valid in (old + current, current, b'\xef\xbb\xbf' + current):
        log.write_bytes(valid)
        report = import_report(dataset, 'postshot', log_path=log)
        assert report['log_scope'] == '2026-11-02 09:26:09 UTC'
        assert len(report['warnings']) == 1
        assert report['warnings'][0]['image'] == 'capture 5_Down.jpg'
        assert report['inputs'][0]['sha256'] == hashlib.sha256(valid).hexdigest()
        assert coverage(report)['totals'] == {'unknown': 6}
    for invalid in (old, current + b'WARNING: accentu\xe9\n', b'WARNING: accentu\xe9\n'):
        log.write_bytes(invalid)
        with pytest.raises(ValueError, match='UTF-8'):
            import_report(dataset, 'postshot', log_path=log)


def postshot_id_model(path, identifier, camera, binary):
    # Postshot 1.1.69 emits zero-based IDs and absolute Windows image names.
    name = r'C:\qualification\images\capture 0_Left.jpg'
    if binary:
        path.write_bytes(struct.pack('<QI7dI', 1, identifier, 1, 0, 0, 0, 0, 0, 0, camera)
                         + name.encode() + b'\0' + struct.pack('<Q', 0))
    else:
        path.write_text(f'# Number of images: 1, mean observations per image: 0\n'
                        f'{identifier} 1 0 0 0 0 0 0 {camera} {name}\n\n')
    return path


@pytest.mark.parametrize('binary', [False, True])
@pytest.mark.parametrize('identifier,camera', [(0, 0), (0, 1), (1, 0), (2**31, 2**32 - 2)])
def test_native_postshot_zero_and_unsigned_ids(dataset, tmp_path, binary, identifier, camera):
    path = postshot_id_model(tmp_path / ('images.bin' if binary else 'images.txt'), identifier, camera, binary)
    report = import_report(dataset, 'postshot', path)
    assert report['models'][0]['states'] == {'capture 0_Left.jpg': 'retained'}
    assert coverage(report, 'image-set')['totals'] == {'retained': 1, 'not_retained': 5}


@pytest.mark.parametrize('binary', [False, True])
@pytest.mark.parametrize('identifier,camera', [(2**32 - 1, 0), (0, 2**32 - 1)])
def test_postshot_invalid_id_sentinels_still_fail(dataset, tmp_path, binary, identifier, camera):
    path = postshot_id_model(tmp_path / ('images.bin' if binary else 'images.txt'), identifier, camera, binary)
    with pytest.raises(ValueError, match='Invalid COLMAP image ID'):
        import_report(dataset, 'postshot', path)


@pytest.mark.parametrize('identifier,camera', [(-1, 0), (0, -1), (2**32, 0), (0, 2**32)])
def test_postshot_text_out_of_range_ids_fail(dataset, tmp_path, identifier, camera):
    path = postshot_id_model(tmp_path / 'images.txt', identifier, camera, False)
    with pytest.raises(ValueError, match='Invalid COLMAP image ID'):
        import_report(dataset, 'postshot', path)


def test_duplicate_and_ambiguous_names_fail(dataset, tmp_path):
    path = text_model(tmp_path / 'images.txt', ['capture 0_Left.jpg'] * 2)
    with pytest.raises(ValueError, match='Duplicate'):
        import_report(dataset, 'postshot', path)
    rows = [dict(image=f'{d}/same.jpg', frame=0, camera=d) for d in ['Left', 'Down']]
    (dataset / 'images.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
    manifest = json.loads((dataset / 'manifest.json').read_text())
    manifest['extraction']['images_written'] = 2
    (dataset / 'manifest.json').write_text(json.dumps(manifest))
    text_model(path, ['C:/remote/same.jpg'])
    with pytest.raises(ValueError, match='Ambiguous'):
        import_report(dataset, 'postshot', path)
    text_model(path, ['Left/same.jpg'])
    assert coverage(import_report(dataset, 'postshot', path), 'image-set')['totals']['retained'] == 1


def test_unfinished_export_cancel_limits_and_invalid_saved_membership(dataset, tmp_path, monkeypatch):
    import extractor360.core.consumer_reports as module
    path = text_model(tmp_path / 'images.txt', ['capture 0_Left.jpg'])
    with pytest.raises(InterruptedError):
        import_report(dataset, 'postshot', path, cancelled=lambda: True)
    report = import_report(dataset, 'postshot', path)
    report['models'][0]['states']['foreign.jpg'] = 'retained'
    with pytest.raises(ValueError, match='Unknown image'):
        validate_report(report)
    monkeypatch.setattr(module, 'MAX_BYTES', 10)
    with pytest.raises(ValueError, match='exceeds'):
        import_report(dataset, 'postshot', path)
    monkeypatch.undo()
    manifest = json.loads((dataset / 'manifest.json').read_text());manifest['status'] = 'failed'
    (dataset / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='completed'):
        import_report(dataset, 'postshot', path)


def test_project_retains_history_after_new_results_and_clears_on_source_replacement(dataset, tmp_path):
    report = import_report(dataset, 'realityscan', rs_report(tmp_path / 'rs.txt'))
    source = tmp_path / 'source.mp4'
    job = Job(str(source), source_identity=source_identity(str(source)), consumer_reports=[report])
    job.result = {'run_id': 'another-run'}
    path = tmp_path / 'project.360proj'
    write_project(path, Project(jobs=[job]))
    restored = read_project(path)[0].jobs[0]
    assert restored.consumer_reports == [report]
    before = copy.deepcopy(restored.consumer_reports)
    moved = tmp_path / 'moved.mp4';source.rename(moved)
    relink_source(restored, str(moved));assert restored.consumer_reports == before
    moved.write_bytes(b'replacement')
    relink_source(restored, str(moved));assert restored.consumer_reports == []


def test_cli_import_headless_and_exclusive_output(dataset, tmp_path):
    path = text_model(tmp_path / 'images.txt', ['capture 0_Left.jpg'])
    output = tmp_path / 'report.json'
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1] / 'src')}
    args = [sys.executable, '-m', 'extractor360', '--import-consumer-report', 'postshot', '--dataset', str(dataset),
            '--camera-report', str(path), '--report-output', str(output)]
    result = subprocess.run(args, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    before = output.read_bytes()
    assert subprocess.run(args, env=env, capture_output=True).returncode == 1
    assert output.read_bytes() == before
    report = json.loads(before)
    with pytest.raises(FileExistsError):
        write_report(output, report)
    template = tmp_path / 'template.txt';write_template(template)
    assert '$SelectComponent' in template.read_text()


def test_truncated_index_and_failed_report_publication_leave_no_success(dataset, tmp_path, monkeypatch):
    import extractor360.core.consumer_reports as module
    path = text_model(tmp_path / 'images.txt', ['capture 0_Left.jpg'])
    report = import_report(dataset, 'postshot', path)
    output = tmp_path / 'failed.json'
    def fail_link(*args):
        raise OSError('simulated publication failure')
    monkeypatch.setattr(module.os, 'link', fail_link)
    with pytest.raises(OSError, match='publication'):
        write_report(output, report)
    assert not output.exists() and not list(tmp_path.glob('.failed.json.*'))
    index = dataset / 'images.jsonl'
    index.write_text('\n'.join(index.read_text().splitlines()[:-1]))
    with pytest.raises(ValueError, match='count disagrees'):
        import_report(dataset, 'postshot', path)
