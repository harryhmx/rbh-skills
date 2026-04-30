# Speech generation is now in image.py (shared file for all media generation).
# This file is kept for backward compatibility with the dynamic import in story.py.

from image import generate_speech  # noqa: F401, F811
