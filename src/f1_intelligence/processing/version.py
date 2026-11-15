"""The version of the processed data, computed from what decides its content.

    version = "<label>-<fingerprint>"      e.g. "v1-3f9a1c2e"

The fingerprint is a short hash of the processing rules (configs/processing.yaml)
and the processing code (transforms + schema). Change either one and the version
changes by itself, so the data is rebuilt into a new folder and the old version
stays untouched. Nobody has to remember to bump anything.
"""

import hashlib
import inspect
import json
from pathlib import Path

from f1_intelligence.config import ProcessingConfig, ProcessingRules
from f1_intelligence.processing import schema, transforms

# Code whose content decides the processed output.
_CODE_THAT_SHAPES_THE_DATA = (transforms, schema)


def fingerprint(rules: ProcessingRules) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(rules.model_dump(), sort_keys=True).encode())
    for module in _CODE_THAT_SHAPES_THE_DATA:
        h.update(inspect.getsource(module).encode())
    return h.hexdigest()[:8]


def processed_version(config: ProcessingConfig) -> str:
    return f"{config.version}-{fingerprint(config.rules)}"


def output_root(config: ProcessingConfig) -> Path:
    """Folder of the current version, e.g. data/processed/v1-3f9a1c2e."""
    return config.processed_uri / processed_version(config)
