import os
import sys
import types
import time
import pytest

# Ensure project root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

pytest.importorskip("PyQt5")

# Stub pygame if missing
if 'pygame' not in sys.modules:
    pygame_stub = types.ModuleType('pygame')
    pygame_stub.mixer = types.SimpleNamespace(
        get_init=lambda: True,
        music=types.SimpleNamespace(
            stop=lambda: None,
            play=lambda *a, **k: None,
            load=lambda *a, **k: None,
            pause=lambda: None,
            unpause=lambda: None,
        ),
    )
    sys.modules['pygame'] = pygame_stub

# Stub cv2 if missing
if 'cv2' not in sys.modules:
    cv2_stub = types.ModuleType('cv2')
    cv2_stub.imread = lambda *a, **k: None
    sys.modules['cv2'] = cv2_stub

from gui import PlayerGUI, pygame
from player_core import parse_shot_list


def test_handle_play_then_stop(qtbot, monkeypatch):
    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_shots.csv')
    shots, audio = parse_shot_list(csv_path)

    gui = PlayerGUI()
    qtbot.addWidget(gui)

    gui.loaded_shots = shots
    gui.audio_path = audio

    stop_calls = []

    monkeypatch.setattr(pygame.mixer.music, 'stop', lambda: stop_calls.append(True), raising=False)
    monkeypatch.setattr(pygame.mixer, 'get_init', lambda: True, raising=False)

    def fake_play_with_cache(*args, **kwargs):
        stop_flag = kwargs.get('stop_flag')
        on_frame = kwargs.get('on_frame')
        for i in range(3):
            if stop_flag and stop_flag():
                break
            if on_frame:
                on_frame(i, 3, 25)
            time.sleep(0.01)
        return 25

    monkeypatch.setattr(sys.modules['gui'], 'play_with_cache', fake_play_with_cache)

    gui.handle_play()
    assert gui.is_playing is True

    qtbot.wait(50)
    gui.handle_stop()

    gui.play_thread.join(timeout=1.0)
    assert not gui.play_thread.is_alive()
    assert gui.is_playing is False
    assert gui.resume_frame_index == 0
    assert stop_calls
