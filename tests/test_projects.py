"""Document integrity, portability, source identity and runtime boundaries."""
import copy
import json
from pathlib import Path

import pytest

from extractor360.core.job import Job
from extractor360.core import project
from extractor360.core.project import Project, read_project, write_project, source_identity, source_problem, relink_source
from extractor360.core.settings_manager import SettingsManager


@pytest.fixture
def document(tmp_path):
    media = tmp_path / 'médiás' / 'image.png'
    media.parent.mkdir()
    media.write_bytes(b'source fixture')
    job = Job(str(media), settings=dict(SettingsManager.DEFAULT_SETTINGS, layout_mode='cube', active_cameras=[0, 5],
                                        mask_profile='postshot', quality=83, pitch_offset=13.12345),
              source_identity=source_identity(str(media)))
    return Project(jobs=[job], default_settings=copy.deepcopy(SettingsManager.DEFAULT_SETTINGS), selected_job_ids=[job.job_id])


def test_roundtrip_preserves_project_jobs_settings_and_last_result(tmp_path, document):
    job = document.jobs[0]
    job.settings['custom_output_dir'] = str(tmp_path / 'exports')
    job.status = 'Done'
    job.result = {'status': 'completed', 'output_dir': str(tmp_path / 'exports' / 'image_processed'),
                  'run_id': 'previous-run', 'extraction': {'images_written': 2}}
    target = tmp_path / 'test.360proj'
    digest = write_project(target, document)
    loaded, actual = read_project(target)
    assert actual == digest and loaded.project_id == document.project_id
    restored = loaded.jobs[0]
    assert restored.job_id == job.job_id and loaded.selected_job_ids == [job.job_id]
    for key in ('custom_output_dir', 'active_cameras', 'quality', 'pitch_offset', 'mask_profile'):
        assert restored.settings[key] == job.settings[key]
    assert restored.result == job.result
    assert restored.status == 'Pending' and restored.source_check_required
    assert source_problem(restored) is None
    assert job.status == 'Done'  # Saving does not reset a live job.


def test_move_project_folder_and_save_as_rebase_paths(tmp_path, document):
    folder = tmp_path / 'original'
    folder.mkdir()
    media = folder / 'pano.jpg'
    media.write_bytes(b'media')
    job = document.jobs[0]
    relink_source(job, str(media))
    job.settings.update(ai_model=str(folder / 'custom.pt'), trust_custom_model=True,
                        custom_output_dir=str(folder / 'exports'))
    job.result = {'output_dir': str(folder / 'exports' / 'run')}
    write_project(folder / 'capture.360proj', document)
    moved = tmp_path / 'moved'
    folder.rename(moved)
    loaded, _ = read_project(moved / 'capture.360proj')
    assert loaded.jobs[0].file_path == str(moved / 'pano.jpg')
    assert loaded.jobs[0].settings['ai_model'] == str(moved / 'custom.pt')
    assert loaded.jobs[0].settings['custom_output_dir'] == str(moved / 'exports')
    assert loaded.jobs[0].result['output_dir'] == str(moved / 'exports' / 'run')
    assert source_problem(loaded.jobs[0]) is None
    write_project(tmp_path / 'copy.360proj', loaded)
    again, _ = read_project(tmp_path / 'copy.360proj')
    assert again.jobs[0].file_path == loaded.jobs[0].file_path


def test_missing_changed_and_relinked_source_preserve_settings(tmp_path, document):
    job = document.jobs[0]
    original_id = job.job_id
    original_settings = copy.deepcopy(job.settings)
    job.result = {'status': 'completed', 'output_dir': '/previous/export'}
    source = Path(job.file_path)
    moved = tmp_path / 'relocated.png'
    source.rename(moved)
    assert 'missing' in source_problem(job)
    relink_source(job, str(moved))
    assert source_problem(job) is None and job.result['status'] == 'completed'
    moved.write_bytes(b'new and different source')
    assert 'changed' in source_problem(job)
    target = tmp_path / 'missing.360proj'
    write_project(target, document)
    loaded, _ = read_project(target)
    assert 'changed' in source_problem(loaded.jobs[0])  # Save must not bless changed content.
    relink_source(job, str(moved))
    assert job.result == {} and job.job_id == original_id and job.settings == original_settings


def test_project_never_grants_custom_model_trust(tmp_path, document):
    job = document.jobs[0]
    job.settings.update(ai_model=str(tmp_path / 'custom.pt'), ai_mode='Generate Mask', trust_custom_model=True)
    target = tmp_path / 'custom.360proj'
    write_project(target, document)
    data = json.loads(target.read_text())
    assert data['jobs'][0]['settings']['trust_custom_model'] is False
    data['jobs'][0]['settings']['trust_custom_model'] = True  # Untrusted file claims consent.
    target.write_text(json.dumps(data))
    loaded, _ = read_project(target)
    assert loaded.jobs[0].settings['trust_custom_model'] is False
    assert loaded.jobs[0].settings['ai_model'] == str(tmp_path / 'custom.pt')
    assert job.settings['trust_custom_model'] is True
    from extractor360.core.validation import validate_settings
    with pytest.raises(ValueError, match='Custom .pt'):
        validate_settings(loaded.jobs[0].settings)


@pytest.mark.parametrize('mutation', ['version', 'duplicate', 'selection', 'settings', 'identity', 'traversal'])
def test_invalid_document_rejected(tmp_path, document, mutation):
    target = tmp_path / 'bad.360proj'
    write_project(target, document)
    data = json.loads(target.read_text())
    if mutation == 'version': data['schema_version'] = 2
    if mutation == 'duplicate': data['jobs'].append(data['jobs'][0])
    if mutation == 'selection': data['selected_job_ids'] = ['unknown']
    if mutation == 'settings': data['jobs'][0]['settings']['resolution'] = 'bad'
    if mutation == 'identity': data['jobs'][0]['source_identity']['size_bytes'] = True
    if mutation == 'traversal': data['jobs'][0]['source'] = {'kind': 'relative', 'path': '../escape.png'}
    target.write_text(json.dumps(data))
    with pytest.raises(ValueError): read_project(target)


def test_failed_atomic_replacement_preserves_previous_project(tmp_path, document, monkeypatch):
    target = tmp_path / 'work.360proj'
    digest = write_project(target, document)
    original = target.read_bytes()
    document.jobs[0].settings['quality'] = 50
    def fail(*args): raise OSError('disk full')
    monkeypatch.setattr(project.os, 'replace', fail)
    with pytest.raises(OSError, match='disk full'): write_project(target, document, digest)
    assert target.read_bytes() == original
    assert not list(tmp_path.glob('.*.tmp'))


def test_conflict_and_new_target_collision_preserve_external_edit(tmp_path, document):
    target = tmp_path / 'work.360proj'
    digest = write_project(target, document)
    with pytest.raises(FileExistsError): write_project(target, document)
    target.write_text('external edit')
    with pytest.raises(ValueError, match='changed on disk'): write_project(target, document, digest)
    assert target.read_text() == 'external edit'


def test_invalid_save_never_creates_target(tmp_path, document):
    document.jobs[0].settings['resolution'] = -1
    target = tmp_path / 'invalid.360proj'
    with pytest.raises(ValueError): write_project(target, document)
    assert not target.exists() and not list(tmp_path.glob('.*.tmp'))


def test_changed_source_rejected_by_worker_before_outputs(tmp_path, document):
    from extractor360.core.processor import ProcessingWorker
    job = document.jobs[0]
    job.settings['custom_output_dir'] = str(tmp_path / 'not-created')
    Path(job.file_path).write_bytes(b'changed media')
    worker = ProcessingWorker([job])
    worker.run()
    assert worker.error_count == 1 and 'Source size/date changed' in job.result['error']
    assert not (tmp_path / 'not-created').exists()


def test_first_save_on_filesystem_without_hardlinks(tmp_path, document, monkeypatch):
    import errno
    def unsupported(*args): raise OSError(errno.EOPNOTSUPP, 'no hardlinks')
    monkeypatch.setattr(project.os, 'link', unsupported)
    target = tmp_path / 'portable.360proj'
    digest = write_project(target, document)
    loaded, actual = read_project(target)
    assert digest == actual and loaded.project_id == document.project_id
    document.jobs[0].settings['quality'] = 50
    write_project(target, document, digest)
    assert read_project(target)[0].jobs[0].settings['quality'] == 50
