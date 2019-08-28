import atexit
import tempfile

from postix.settings import *  # noqa

tmpdir = tempfile.TemporaryDirectory()
MEDIA_ROOT = os.path.join(tmpdir.name, "media")
atexit.register(tmpdir.cleanup)

LANGUAGE_CODE = "en-us"
