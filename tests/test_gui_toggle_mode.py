import os
import sys
import types
import pytest

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

pytest.importorskip("PyQt5")

# Stub pygame if missing
if 'pygame' not in sys.modules:
    pygame_stub = types.ModuleType('pygame')
    pygame_stub.mixer = types.SimpleNamespace(get_init=lambda: False, music=types.SimpleNamespace())
    sys.modules['pygame'] = pygame_stub

from player_core import parse_shot_list
from gui import PlayerGUI


def test_gui_toggle_mode(qtbot):
    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_shots.csv')
    shots, _ = parse_shot_list(csv_path)

    gui = PlayerGUI()
    qtbot.addWidget(gui)

    gui.loaded_shots = shots
    gui.resume_frame_index = 4  # global frame within second shot

    gui.toggle_episode_mode()  # Episode -> Scene
    assert gui.mode_episode is False
    assert gui.current_shot == shots[1]
    assert gui.resume_frame_index == 1

    gui.toggle_episode_mode()  # Scene -> Episode
    assert gui.mode_episode is True
    assert gui.resume_frame_index == 4
