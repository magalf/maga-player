import os
import sys
import types
import queue

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

class DummyThread:
    def __init__(self, target=None, daemon=None):
        self._target = target
    def start(self):
        if self._target:
            self._target()
    def is_alive(self):
        return False
    def join(self, timeout=None):
        pass

class DummySpinner:
    def __init__(self, value):
        self._val = value
    def value(self):
        return self._val

class DummyGui:
    def __init__(self, shots):
        self.mode_episode = True
        self.loop_enabled = False
        self.resume_frame_index = 0
        self.is_playing = False
        self.should_stop = False
        self.should_pause = False
        self.current_shot = None
        self.loaded_shots = shots
        self.current_reparto = 'animazione'
        self.episode_frame_map = []
        self.total_episode_frames = 0
        self.audio_path = None
        self.video_frame = None
        self.fps_spinner = DummySpinner(25)
        self.cache_spinner = DummySpinner(150)
        self.fps_label = types.SimpleNamespace(setText=lambda *a, **k: None)
        self.frame_counter = types.SimpleNamespace(setText=lambda *a, **k: None)
        self.timeline_slider = types.SimpleNamespace(setValue=lambda *a, **k: None,
                                                     setMaximum=lambda *a, **k: None)
        self.command_q = queue.Queue()
        self.play_thread = DummyThread()


def setup_modules():
    sys.modules['cv2'] = sys.modules.get('cv2', types.ModuleType('cv2'))
    pygame_stub = types.ModuleType('pygame')
    pygame_stub.mixer = types.SimpleNamespace(get_init=lambda: False,
                                             music=types.SimpleNamespace(stop=lambda: None,
                                                                         play=lambda *a, **k: None,
                                                                         load=lambda *a, **k: None,
                                                                         pause=lambda: None,
                                                                         unpause=lambda: None))
    sys.modules['pygame'] = pygame_stub

    qtgui = types.ModuleType('PyQt5.QtGui')
    qtgui.QPixmap = object
    qtgui.QImage = object
    qtgui.QPalette = type('QPalette', (), {})
    qtgui.QColor = type('QColor', (), {})
    sys.modules['PyQt5.QtGui'] = qtgui

    qtcore = types.ModuleType('PyQt5.QtCore')
    qtcore.Qt = types.SimpleNamespace(KeepAspectRatio=0)
    qtcore.QTimer = type('QTimer', (), {'__init__': lambda self, *a, **k: None,
                                        'timeout': types.SimpleNamespace(connect=lambda *a, **k: None)})
    sys.modules['PyQt5.QtCore'] = qtcore

    qtwidgets = types.ModuleType('PyQt5.QtWidgets')
    for name in ['QApplication', 'QMainWindow', 'QWidget', 'QLabel', 'QListWidget',
                 'QVBoxLayout', 'QHBoxLayout', 'QPushButton', 'QSlider', 'QFrame',
                 'QSpinBox', 'QFileDialog']:
        setattr(qtwidgets, name, type(name, (), {'__init__': lambda self, *a, **k: None}))
    sys.modules['PyQt5.QtWidgets'] = qtwidgets

    sys.modules.setdefault('PyQt5', types.ModuleType('PyQt5'))


def test_handle_play_clears_queue(monkeypatch):
    setup_modules()
    from player_core import parse_shot_list
    from gui import PlayerGUI

    handle_play = PlayerGUI.handle_play

    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_shots.csv')
    shots, audio = parse_shot_list(csv_path)

    gui = DummyGui(shots)
    gui.audio_path = audio
    gui.command_q.put(('dummy', 1))

    monkeypatch.setattr('gui.play_with_cache', lambda *a, **k: None)
    monkeypatch.setattr('gui.threading.Thread', DummyThread)

    handle_play(gui)

    assert list(gui.command_q.queue) == [('trim_off', None)]


def test_handle_stop_clears_queue(monkeypatch):
    setup_modules()
    from player_core import parse_shot_list
    from gui import PlayerGUI

    handle_stop = PlayerGUI.handle_stop

    csv_path = os.path.join(os.path.dirname(__file__), 'data', 'sample_shots.csv')
    shots, _ = parse_shot_list(csv_path)

    gui = DummyGui(shots)
    gui.command_q.put(('seek', 5))

    handle_stop(gui)

    assert gui.command_q.empty()
