import sys
import os

# Add your project directory to the sys.path
path = '/home/yourusername/atomquest'
if path not in sys.path:
    sys.path.insert(0, path)

os.chdir(path)

from app import app as application
