from typing import Mapping, Optional


def features() -> Mapping[str, Optional[str]]:
    if not hasattr(features, 'features'):
        setattr(features, 'features', {
            'nosrlrace': 'Disable !srlrace',
            })
    return getattr(features, 'features')
