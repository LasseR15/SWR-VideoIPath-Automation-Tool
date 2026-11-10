from enum import Enum


class HydrationLevel(str, Enum):
    SKELETON = "skeleton"
    FULL = "full"
