"""Destination-specific mask contracts, independent of Qt and model libraries.

Custom preserves existing settings. Named profiles own polarity and naming;
they describe a file contract, not a qualified reconstruction in that product.
"""
from typing import Any


MASK_PROFILES = {
    'custom': 'Custom / legacy',
    'realityscan': 'RealityScan',
    'colmap': 'COLMAP',
    'postshot': 'Postshot — Remove Occluders',
}


def profile_settings(profile: str) -> dict[str, Any]:
    if profile not in MASK_PROFILES:
        raise ValueError(f'Unknown mask profile: {profile}')
    if profile == 'custom':
        return {}
    return {'naming_mode': profile, 'ai_invert_mask': profile != 'postshot'}


def mask_contract(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        'profile': settings.get('mask_profile', 'custom'),
        'ignored_value': 0 if settings['ai_invert_mask'] else 255,
        'kept_value': 255 if settings['ai_invert_mask'] else 0,
        'meaning': 'ignore_observation',
        'edge_smoothing': settings['feather_mask'],
        'naming_mode': settings['naming_mode'],
    }
