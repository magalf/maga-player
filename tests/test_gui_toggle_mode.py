import os
import sys
import types
import queue
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

from player_core import parse_shot_list, Shot
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


def test_gui_toggle_mode_duplicate_departments(qtbot):
    shots = [
        Shot("s1", "animazione", "anim/shot1/frame####.png", 1, 3, absolute_start=0),
        Shot("s1", "render", "render/shot1/frame####.png", 1, 3, absolute_start=0),
        Shot("s2", "animazione", "anim/shot2/frame####.png", 1, 2, absolute_start=3),
        Shot("s2", "render", "render/shot2/frame####.png", 1, 2, absolute_start=3),
    ]

    gui = PlayerGUI()
    qtbot.addWidget(gui)

    gui.loaded_shots = shots
    gui.current_reparto = "render"
    gui.resume_frame_index = 4  # global frame within second shot
    gui.command_q = queue.Queue()

    gui.toggle_episode_mode()  # Episode -> Scene
    assert gui.mode_episode is False
    assert gui.current_shot == shots[3]
    assert gui.resume_frame_index == 1
    assert gui.command_q.get_nowait() == ("trim", (3, 4))
    assert gui.command_q.get_nowait() == ("seek", 4)
    assert gui.command_q.empty()

    gui.toggle_episode_mode()  # Scene -> Episode
    assert gui.mode_episode is True
    assert gui.resume_frame_index == 4
    assert gui.command_q.get_nowait() == ("trim_off", None)
    assert gui.command_q.empty()
