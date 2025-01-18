"""Configure test environment."""
import os
import sys
from pathlib import Path

# Add the root directory to Python path
ROOT_DIR = Path(__file__).parent
sys.path.append(str(ROOT_DIR))

# Add custom_components to Python path
CUSTOM_COMPONENTS = ROOT_DIR / "custom_components"
sys.path.append(str(CUSTOM_COMPONENTS)) 