"""
Platform Detection, Capability Matrix, and Provider Contracts
"""

from app.models.state import PlatformInfo
from app.platform.detect import get_platform_info, detect_platform
from app.platform.capabilities import get_capability_matrix, CapabilityStatus

__all__ = [
    "PlatformInfo",
    "get_platform_info",
    "detect_platform",
    "get_capability_matrix",
    "CapabilityStatus",
]
