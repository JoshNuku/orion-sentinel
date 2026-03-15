"""AI package: audio and vision modules for ORION.

This package contains the audio and vision inference units. Import
from `orion.modules.ai` in the codebase (compatibility wrapper
`ai_engine.py` will continue to expose the same symbols as before).
"""

from .audio import AudioIntelligenceUnit
from .vision import IntelligenceUnit

__all__ = ['AudioIntelligenceUnit', 'IntelligenceUnit']
