"""Model coverage must describe one model, not a union or a quality score."""
import copy

import pytest

from extractor360.core.alignment import summarize
from extractor360.core.diagnostic import diagnostic_options, model_overview


def test_overlapping_models_keep_individual_coverage_and_tested_gaps():
    frames = {n: {'frame': n, 'images': [f'Front/{n}.jpg'], 'timestamp_seconds': n / 10,
                  'timestamp_source': 'decoder_timestamp'} for n in range(7)}
    models = {'a': {'Front/0.jpg', 'Front/2.jpg', 'Front/4.jpg'},
              'b': {'Front/2.jpg', 'Front/4.jpg', 'Front/6.jpg'}, 'c': {'Front/1.jpg'}}
    report = summarize(frames, list(frames), set(), models)
    overview = report['overview']
    assert len(report['groups'][0]['frames']) == 4
    assert overview['largest']['capture_count'] == 3 and overview['largest_ties'] == ['a', 'b']
    assert overview['largest']['time_span'] == [0, .4]
    assert overview['largest']['missing_tested_frames'] == [1, 3]
    assert overview['fragment_models'] == 1 and not overview['only_fragments']
    # Older saved reports derive the same summary without the cached field.
    del report['overview']
    assert model_overview(report) == overview
    report['captures'][2]['timestamp_source'] = 'fps_estimate'
    assert model_overview(report)['largest']['timing'] == 'FPS estimate'
    report['captures'][2].pop('timestamp_seconds')
    assert model_overview(report)['largest']['time_span'] is None


def test_registered_total_does_not_promote_two_capture_fragments():
    frames = {n: {'frame': n, 'images': [str(n)]} for n in range(6)}
    report = summarize(frames, list(frames), set(), {'0': {'0', '1'}, '1': {'2', '3'}, '2': {'4', '5'}})
    assert report['registered_captures'] == 6
    assert report['overview']['only_fragments'] and report['overview']['largest']['capture_count'] == 2
    bad = copy.deepcopy(report)
    bad['models'][0]['frames'].append(999)
    with pytest.raises(ValueError, match='membership'):
        model_overview(bad)


@pytest.mark.parametrize('value', [{'resolution': True}, {'resolution': 2048}, {'maximum': 17},
    {'mode': 'automatic'}, {'frame_range': [1, 2]}, {'frame_range': [True, 5]},
    {'frame_range': [9, 2]}, {'frame_range': [-1, 3]}, {'frame_range': [0, 2**31]}, {'unknown': 1}])
def test_invalid_diagnostic_options_are_not_silently_reset(value):
    with pytest.raises(ValueError):
        diagnostic_options(value)


def test_all_timestamps_in_one_direction_are_not_full_view_coverage():
    directions = ('Front', 'Right', 'Back', 'Left', 'Up', 'Down')
    frames = {n: {'frame': n, 'images': [f'{d}/{n}.jpg' for d in directions]} for n in range(16)}
    report = summarize(frames, list(frames), set(), {'left': {f'Left/{n}.jpg' for n in frames},
                                                   'right': {f'Right/{n}.jpg' for n in frames}})
    largest = report['overview']['largest']
    coverage = largest['view_coverage']
    assert largest['capture_count'] == 16
    assert coverage['registered'] == 16 and coverage['tested'] == 96
    assert coverage['directions']['Left'] == {'registered': 16, 'tested': 16}
    assert coverage['missing_directions'] == ['Back', 'Down', 'Front', 'Right', 'Up']
    assert len(coverage['unregistered_images']) == 80
    assert 'Right/0.jpg' in coverage['unregistered_images']
    for model in report['models']:
        del model['image_names']
    assert model_overview(report)['largest']['view_coverage'] is None


def test_saved_direction_details_are_validated_and_derived_again():
    frames = {n: {'frame': n, 'images': [f'Left/{n}.jpg']} for n in range(3)}
    report = summarize(frames, list(frames), set(), {'0': {'Left/0.jpg', 'Left/1.jpg'}})
    report['overview']['largest']['view_coverage']['registered'] = 999
    assert model_overview(report)['largest']['view_coverage']['registered'] == 2
    report['models'][0]['image_names'] = ['Left/2.jpg']
    with pytest.raises(ValueError, match='membership'):
        model_overview(report)
