import os
import sys
import types

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Provide minimal stubs so player_core can be imported without optional deps
sys.modules.setdefault('cv2', types.ModuleType('cv2'))
pygame_stub = types.ModuleType('pygame')
pygame_stub.mixer = types.SimpleNamespace(get_init=lambda: False, music=types.SimpleNamespace())
sys.modules.setdefault('pygame', pygame_stub)

qtgui = types.ModuleType('PyQt5.QtGui')
qtgui.QPixmap = object
qtgui.QImage = object
qtcore = types.ModuleType('PyQt5.QtCore')
qtcore.Qt = types.SimpleNamespace(KeepAspectRatio=0)
sys.modules.setdefault('PyQt5', types.ModuleType('PyQt5'))
sys.modules.setdefault('PyQt5.QtGui', qtgui)
sys.modules.setdefault('PyQt5.QtCore', qtcore)

from player_core import parse_shot_list


def test_parse_shot_list():
    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_shots.csv')
    shots, audio = parse_shot_list(csv_path)
    assert audio == 'path/audio.wav'
    assert len(shots) == 2
    assert shots[0].shot_id == 's1'
    assert shots[0].absolute_start == 0
    assert shots[1].shot_id == 's2'
    # shot1 length is 3 frames -> shot2 starts at 3
    assert shots[1].absolute_start == 3
