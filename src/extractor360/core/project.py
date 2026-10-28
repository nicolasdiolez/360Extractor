"""Versioned Studio documents. Media stay in place; loading never resumes work.

Only small project documents are hashed. Source identity uses size/mtime and
does not claim cryptographic media verification. This module imports no Qt/AI.
"""
from __future__ import annotations

import copy
import errno
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
from typing import Any
import uuid

from extractor360.core.ai_classes import AI_MODEL_VARIANTS, resolve_ai_model_name
from extractor360.core.job import Job
from extractor360.core.diagnostic import diagnostic_options
from extractor360.core.output_plan import MEDIA_EXTENSIONS
from extractor360.core.validation import validate_settings
from extractor360.core.version import VERSION

FORMAT = '360-extractor-project'
MAX_BYTES = 16 * 1024 * 1024


@dataclass
class Project:
    jobs: list[Job] = field(default_factory=list)
    default_settings: dict[str, Any] = field(default_factory=dict)
    selected_job_ids: list[str] = field(default_factory=list)
    project_id: str = field(default_factory=lambda: uuid.uuid4().hex)


def source_identity(path: str) -> dict[str, int]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f'Source is missing or unavailable: {path}')
    stat = source.stat()
    return {'size_bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}


def source_problem(job: Job) -> str | None:
    try:
        current = source_identity(job.file_path)
    except OSError:
        return 'Source missing or unavailable — use Project > Locate Selected Source'
    if job.source_identity is None:
        return 'Source identity unavailable — use Project > Locate Selected Source'
    if current != job.source_identity:
        return 'Source size/date changed — use Project > Locate Selected Source to confirm it'
    return None


def relink_source(job: Job, path: str) -> None:
    source = Path(path).expanduser().resolve(strict=True)
    if source.suffix.lower() not in MEDIA_EXTENSIONS:
        raise ValueError('Select a supported media file')
    identity = source_identity(str(source))
    if job.source_identity != identity:
        # Existing results describe the old source; never relabel them as new.
        job.result = {}
        job.settings['excluded_frames'] = []
        if job.diagnostic_settings:
            job.diagnostic_settings['frame_range'] = None
    job.file_path = str(source)
    job.source_identity = identity
    job.source_check_required = True
    job.status = 'Pending'


def _object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    return value


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or len(value) != 32:
        raise ValueError('Project/job identifiers must be UUID hex strings')
    try:
        if uuid.UUID(hex=value).hex != value:
            raise ValueError('Noncanonical UUID')
    except (ValueError, AttributeError) as exc:
        raise ValueError('Invalid project/job identifier') from exc
    return value


def _identity(value: Any) -> dict[str, int] | None:
    if value is None:
        return None
    value = _object(value, 'Source identity')
    if set(value) != {'size_bytes', 'mtime_ns'} or any(type(v) is not int or v < 0 for v in value.values()):
        raise ValueError('Invalid source size/mtime identity')
    return dict(value)


def _encode_path(value: str, parent: Path) -> dict[str, str]:
    # Preserve foreign absolute paths until the user explicitly locates them.
    if PureWindowsPath(value).is_absolute() and not Path(value).is_absolute():
        return {'kind': 'absolute', 'path': value}
    path = Path(value).expanduser().absolute()
    if path.is_relative_to(parent):
        return {'kind': 'relative', 'path': path.relative_to(parent).as_posix()}
    return {'kind': 'absolute', 'path': str(path)}


def _decode_path(value: Any, parent: Path) -> str:
    ref = _object(value, 'Path reference')
    path = ref.get('path')
    if not isinstance(path, str) or not path or '\x00' in path:
        raise ValueError('Invalid path reference')
    if ref.get('kind') == 'relative':
        if Path(path).is_absolute() or PureWindowsPath(path).drive or '\\' in path or '..' in Path(path).parts:
            raise ValueError('Relative project paths must stay inside the project folder')
        return str(parent / path)
    if ref.get('kind') == 'absolute' and (Path(path).is_absolute() or PureWindowsPath(path).is_absolute()):
        return path
    raise ValueError('Invalid path kind or absolute path')


def _settings(value: Any) -> dict[str, Any]:
    settings = copy.deepcopy(_object(value, 'Settings'))
    # Validate the configuration without treating a file's trust bit as consent.
    # This call only validates data; no model is imported or loaded.
    settings['trust_custom_model'] = True
    settings = validate_settings(settings)
    settings['trust_custom_model'] = False
    return settings


def _encode_settings(value: dict[str, Any], parent: Path) -> dict[str, Any]:
    settings = _settings(value)
    if settings['custom_output_dir']:
        settings['custom_output_dir'] = _encode_path(settings['custom_output_dir'], parent)
    model = resolve_ai_model_name(settings['ai_model'])
    settings['ai_model'] = model if model in AI_MODEL_VARIANTS.values() else _encode_path(model, parent)
    return settings


def _decode_settings(value: Any, parent: Path) -> dict[str, Any]:
    settings = copy.deepcopy(_object(value, 'Settings'))
    if settings.get('custom_output_dir'):
        settings['custom_output_dir'] = _decode_path(settings['custom_output_dir'], parent)
    if isinstance(settings.get('ai_model'), dict):
        settings['ai_model'] = _decode_path(settings['ai_model'], parent)
    elif resolve_ai_model_name(settings.get('ai_model')) not in AI_MODEL_VARIANTS.values():
        raise ValueError('Custom models require a path reference')
    return _settings(settings)


def _document(project: Project, parent: Path) -> dict[str, Any]:
    jobs = []
    for job in project.jobs:
        _object(job.diagnostic_settings, 'Diagnostic settings')
        result = copy.deepcopy(job.result)
        if result.get('output_dir'):
            result['output_dir'] = _encode_path(result['output_dir'], parent)
        jobs.append({'id': job.job_id, 'source': _encode_path(job.file_path, parent),
                     'source_identity': job.source_identity, 'settings': _encode_settings(job.settings, parent),
                     'last_result': result,
                     'diagnostic_settings': diagnostic_options(job.diagnostic_settings) if job.diagnostic_settings else {}})
    return {'format': FORMAT, 'schema_version': 1, 'application_version': VERSION,
            'id': project.project_id, 'defaults': _encode_settings(project.default_settings, parent),
            'selected_job_ids': project.selected_job_ids, 'jobs': jobs}


def _parse(data: Any, parent: Path) -> Project:
    data = _object(data, 'Project')
    if data.get('format') != FORMAT or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('Unsupported project format/version (expected 360 Extractor project version 1)')
    entries = data.get('jobs')
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ValueError('Project jobs must be a list of at most 10000 entries')
    project = Project(project_id=_identifier(data.get('id')), default_settings=_decode_settings(data.get('defaults'), parent))
    ids, sources = set(), set()
    for entry in entries:
        entry = _object(entry, 'Job')
        job_id = _identifier(entry.get('id'))
        source = _decode_path(entry.get('source'), parent)
        if Path(source).suffix.lower() not in MEDIA_EXTENSIONS:
            raise ValueError('Unsupported project source extension')
        key = os.path.normcase(os.path.realpath(source))
        if job_id in ids or key in sources:
            raise ValueError('Duplicate project job or source')
        ids.add(job_id)
        sources.add(key)
        result = copy.deepcopy(_object(entry.get('last_result', {}), 'Last result'))
        if result.get('output_dir'):
            result['output_dir'] = _decode_path(result['output_dir'], parent)
        diagnostic = _object(entry.get('diagnostic_settings', {}), 'Diagnostic settings')
        diagnostic_options(diagnostic)  # Validate optional settings in old and new documents.
        project.jobs.append(Job(source, settings=_decode_settings(entry.get('settings'), parent), result=result,
                                job_id=job_id, source_identity=_identity(entry.get('source_identity')), source_check_required=True,
                                diagnostic_settings=diagnostic_options(diagnostic) if diagnostic else {}))
    selected = data.get('selected_job_ids', [])
    if not isinstance(selected, list) or any(not isinstance(i, str) or i not in ids for i in selected):
        raise ValueError('Selection contains an unknown job')
    if len(set(selected)) != len(selected):
        raise ValueError('Duplicate selected job')
    project.selected_job_ids = list(selected)
    return project


def read_project(path: Path) -> tuple[Project, str]:
    path = Path(path).absolute()
    with path.open('rb') as file:
        content = file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ValueError('Project exceeds 16 MiB')
    try:
        data = json.loads(content.decode('utf-8-sig'), parse_constant=lambda v: _invalid_constant(v))
        project = _parse(data, path.parent)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Invalid project encoding or structure') from exc
    return project, hashlib.sha256(content).hexdigest()


def _invalid_constant(value: str) -> None:
    raise ValueError(f'Invalid JSON constant: {value}')


def write_project(path: Path, project: Project, expected_digest: str | None = None) -> str:
    path = Path(path).absolute()
    if path.suffix.lower() != '.360proj':
        raise ValueError('Project filenames must end with .360proj')
    if path.is_symlink():
        raise ValueError('Choose a regular project file, not a symbolic link')
    data = _document(project, path.parent)
    _parse(data, path.parent)  # Validate the complete document before any write.
    content = (json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
    if len(content) > MAX_BYTES:
        raise ValueError('Project exceeds 16 MiB')

    def check_target():
        if expected_digest is None:
            if path.exists():
                raise FileExistsError('Project already exists; use Save As or explicitly confirm replacement')
        elif not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_digest:
            raise ValueError('Project changed on disk; use Save As to preserve both versions')

    check_target()
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        check_target()
        if expected_digest is None:
            try:
                os.link(temporary, path)  # Exclusive publication; never truncate a raced target.
            except OSError as exc:
                if exc.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP):
                    raise
                # exFAT has no hardlinks. The first save uses exclusive creation;
                # subsequent saves still replace a fully staged file atomically.
                file = path.open('xb')
                identity = os.fstat(file.fileno())
                try:
                    with file:
                        file.write(content)
                        file.flush()
                        os.fsync(file.fileno())
                except OSError:
                    try:
                        current = path.stat()
                        if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                            path.unlink()
                    except OSError:
                        pass
                    raise
        else:
            os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return hashlib.sha256(content).hexdigest()
