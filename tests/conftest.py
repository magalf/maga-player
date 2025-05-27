import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def set_qt_offscreen():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
