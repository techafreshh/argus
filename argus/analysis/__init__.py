"""Pure-stdlib vegetation/water analysis: NDVI, NDWI, bi-temporal change."""

from argus.analysis.change import detect_change
from argus.analysis.ndvi import compute_ndvi, fetch_ndvi, z_score
from argus.analysis.ndwi import compute_ndwi, fetch_ndwi

__all__ = [
    "compute_ndvi",
    "compute_ndwi",
    "detect_change",
    "fetch_ndvi",
    "fetch_ndwi",
    "z_score",
]
