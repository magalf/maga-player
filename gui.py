from player_core import parse_shot_list

import sys
import random
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QListWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QFrame, QSpinBox, QFileDialog
)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, QTimer
import threading
from player_core import play_with_cache


class PlayerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode_episode = True  # True = episodio intero, False = singolo shot
        self.loop_enabled = False
        self.is_playing = False
        self.should_stop = False
        self.should_pause = False
        self.resume_frame_index = 0  # 👈 Nuovo: dove ripartire dopo una pausa

        self.setWindowTitle("Player Episodio Maga - GUI")
        self.setMinimumSize(1280, 720)
        self.loaded_shots = []
        self.audio_path = None
        self.current_reparto = "animazione"
        self.set_dark_theme()

        # Layout principale
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # --------------------------
        # COLONNA SINISTRA (PLAYER)
        # --------------------------
        left_side = QVBoxLayout()
        main_layout.addLayout(left_side, stretch=4)

        # Area video
        self.video_frame = QLabel("Area Riproduzione (16:9)")
        self.video_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        self.video_frame.setAlignment(Qt.AlignCenter)
        self.video_frame.setStyleSheet("background-color: #1e1e1e; color: #aaaaaa;")
        self.video_frame.setMinimumHeight(400)
        left_side.addWidget(self.video_frame, stretch=8)

        # CONTROLLI (bottoni + cache)
        controls_layout = QHBoxLayout()

        button_style = """
            QPushButton {
                background-color: #333333;
                color: white;
                padding: 6px 12px;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """

        self.load_csv_btn = QPushButton("📂 Carica CSV")
        self.play_btn = QPushButton("▶ Play")
        self.pause_btn = QPushButton("⏸ Pausa")
        self.stop_btn = QPushButton("⏹ Stop")
        self.loop_btn = QPushButton("🔁 Loop")
        self.loop_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: white;
                padding: 6px 12px;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
        """)

        self.mode_toggle_btn = QPushButton("🎯 Episodio intero")
        self.mode_toggle_btn.clicked.connect(self.toggle_episode_mode)
        self.mute_btn = QPushButton("🔇 Audio")
        self.render_toggle_btn = QPushButton("🎬 Animazione/Render")

        for btn in [
            self.load_csv_btn, self.play_btn, self.pause_btn, self.stop_btn,
            self.loop_btn, self.mode_toggle_btn, self.mute_btn, self.render_toggle_btn
        ]:
            btn.setStyleSheet(button_style)
            controls_layout.addWidget(btn)

        # Cache spinner
        config_layout = QHBoxLayout()

        self.cache_label = QLabel("Cache:")
        self.cache_label.setStyleSheet("color: #dddddd;")
        self.cache_spinner = QSpinBox()
        self.cache_spinner.setRange(10, 1000)
        self.cache_spinner.setValue(150)
        self.cache_spinner.setStyleSheet("background-color: #2a2a2a; color: #ffffff;")

        self.fps_label_gui = QLabel("FPS:")
        self.fps_label_gui.setStyleSheet("color: #dddddd;")
        self.fps_spinner = QSpinBox()
        self.fps_spinner.setRange(1, 60)
        self.fps_spinner.setValue(25)
        self.fps_spinner.setStyleSheet("background-color: #2a2a2a; color: #ffffff;")

        config_layout.addWidget(self.cache_label)
        config_layout.addWidget(self.cache_spinner)
        config_layout.addWidget(self.fps_label_gui)
        config_layout.addWidget(self.fps_spinner)

        controls_layout.addLayout(config_layout)
        
        left_side.addLayout(controls_layout, stretch=1)

        # TIMELINE + FPS + Frame counter
        timeline_layout = QHBoxLayout()
        self.timeline_slider = QSlider(Qt.Horizontal)
        self.timeline_slider.setMinimum(0)
        self.timeline_slider.setMaximum(100)
        self.timeline_slider.setStyleSheet("background-color: #3a3a3a;")

        self.fps_label = QLabel("FPS: --")
        self.fps_label.setStyleSheet("color: #bbbbbb;")

        self.frame_counter = QLabel("Frame: 0000 / 0000")
        self.frame_counter.setStyleSheet("color: #bbbbbb; padding-left: 20px;")

        timeline_layout.addWidget(self.timeline_slider)
        timeline_layout.addWidget(self.frame_counter)
        timeline_layout.addWidget(self.fps_label)

        left_side.addLayout(timeline_layout)

        # --------------------------
        # COLONNA DESTRA (SHOT LIST)
        # --------------------------
        self.shot_list = QListWidget()
        # La lista rimane vuota finché non viene caricato un CSV
        self.shot_list.setMaximumWidth(280)
        self.shot_list.setStyleSheet("background-color: #2a2a2a; color: #dddddd;")
        main_layout.addWidget(self.shot_list)

        # Dummy frame simulation (disattivato per ora)
        self.total_frames = 785
        self.current_frame = 0
        self.frame_update_timer = QTimer()
        self.frame_update_timer.timeout.connect(self.update_frame_counter)
        # self.frame_update_timer.start(40)  # DISABILITATO il play automatico

        # Pulsanti
        self.render_toggle_btn.clicked.connect(self.toggle_reparto)
        self.load_csv_btn.clicked.connect(self.open_csv_dialog)
        self.play_btn.clicked.connect(self.handle_play)
        self.stop_btn.clicked.connect(self.handle_stop)
        self.pause_btn.clicked.connect(self.handle_pause)
        self.loop_btn.clicked.connect(self.handle_loop_toggle)

    def update_frame_counter(self):
        self.current_frame += 1
        if self.current_frame > self.total_frames:
            self.current_frame = 0
        self.frame_counter.setText(f"Frame: {self.current_frame:04d} / {self.total_frames:04d}")
        self.timeline_slider.setValue(int((self.current_frame / self.total_frames) * 100))

    def toggle_mode(self):
        current_text = self.mode_toggle_btn.text()
        if "Episodio" in current_text:
            self.mode_toggle_btn.setText("🎯 Solo shot")
            print("[Modalità] Riproduzione isolata dello shot selezionato")
        else:
            self.mode_toggle_btn.setText("🎯 Episodio intero")
            print("[Modalità] Riproduzione dell'intero episodio")

    def open_csv_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file shot list", "", "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            print(f"[📂] CSV selezionato: {path}")
            self.loaded_shots, self.audio_path = parse_shot_list(path)
            self.populate_shot_list()

    def populate_shot_list(self):
        self.shot_list.clear()
        for shot in self.loaded_shots:
            if shot.reparto == self.current_reparto:
                label = f"{shot.shot_id} ({shot.start_frame}–{shot.end_frame})"
                self.shot_list.addItem(label)

    def toggle_reparto(self):
        if self.current_reparto == "animazione":
            self.current_reparto = "render"
            self.render_toggle_btn.setText("🎬 Render")
            print("[Switch] Mostro shot da render")
        else:
            self.current_reparto = "animazione"
            self.render_toggle_btn.setText("🎬 Animazione")
            print("[Switch] Mostro shot da animazione")

        self.populate_shot_list()

    def handle_play(self):
        if self.is_playing:
            print("[INFO] Riproduzione già in corso.")
            self.should_pause = False
            return

        if not self.loaded_shots:
            print("⚠️ Nessuno shot caricato.")
            return

        if not self.mode_episode:
            selected_row = self.shot_list.currentRow()
            if selected_row < 0:
                print("⚠️ Nessuno shot selezionato.")
                return
            shots_to_play = [shot for shot in self.loaded_shots if shot.reparto == self.current_reparto]
            selected_shot = shots_to_play[selected_row:selected_row + 1]
        else:
            selected_shot = [shot for shot in self.loaded_shots if shot.reparto == self.current_reparto]

        fps_value = self.fps_spinner.value()
        cache_value = self.cache_spinner.value()

        def update_gui_live(current_frame, total_frames, fps_ist):
            self.resume_frame_index = current_frame
            self.frame_counter.setText(f"Frame: {current_frame:04d} / {total_frames:04d}")
            self.fps_label.setText(f"FPS: {fps_ist:.2f}")
            self.timeline_slider.setValue(int((current_frame / total_frames) * 100))

        def playback_loop():
            self.is_playing = True
            self.should_stop = False
            self.should_pause = False

            while self.is_playing:
                fps_medio = play_with_cache(
                    selected_shot,
                    self.video_frame,
                    self.audio_path,
                    fps=fps_value,
                    max_cache_size=cache_value,
                    on_frame=update_gui_live,
                    stop_flag=lambda: self.should_stop,
                    pause_flag=lambda: self.should_pause,
                    start_index=self.resume_frame_index
                )

                self.resume_frame_index = 0

                if self.should_stop or not self.loop_enabled:
                    break

                self.should_pause = False

            self.is_playing = False

        self.play_thread = threading.Thread(target=playback_loop)
        self.play_thread.start()

    # Funzione: Toggle loop
    def handle_loop_toggle(self):
        self.loop_enabled = not self.loop_enabled
        if self.loop_enabled:
            # Attivo → blu scuro leggero
            self.loop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #223366;
                    color: white;
                    padding: 6px 12px;
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #2a3b66;
                }
                QPushButton:pressed {
                    background-color: #1b2d4d;
                }
            """)
            print("[Loop] Attivo")
        else:
            # Torna grigio default
            self.loop_btn.setStyleSheet("""
                QPushButton {
                    background-color: #333333;
                    color: white;
                    padding: 6px 12px;
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #444444;
                }
                QPushButton:pressed {
                    background-color: #222222;
                }
            """)
            print("[Loop] Disattivato")

    # Funzione: Stop
    def handle_stop(self):
        print("[Stop] Playback interrotto")
        self.should_stop = True
        self.is_playing = False
        self.should_pause = False
        # Resetta il frame a 0
        self.frame_counter.setText("Frame: 0000 / 0000")
        self.fps_label.setText("FPS: --")
        self.timeline_slider.setValue(0)
        self.video_frame.clear()

    # Funzione: Pausa
    def handle_pause(self):
        if self.is_playing:
            self.should_pause = True
            print("[Pausa] Playback in pausa")

    def toggle_episode_mode(self):
        # Se stiamo riproducendo, interrompi e rilancia in nuova modalità
        was_playing = self.is_playing

        self.should_stop = True  # Ferma thread attuale
        self.mode_episode = not self.mode_episode

        if self.mode_episode:
            self.mode_toggle_btn.setText("Episodio")
            self.mode_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3e2c66;
                    color: white;
                    padding: 6px 12px;
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #4f3c77;
                }
                QPushButton:pressed {
                    background-color: #2d1d55;
                }
            """)
            print("[Modalità] Riproduzione dell'intero episodio")
        else:
            self.mode_toggle_btn.setText("Scena")
            self.mode_toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2c6633;
                    color: white;
                    padding: 6px 12px;
                    border: 1px solid #555555;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #338c3f;
                }
                QPushButton:pressed {
                    background-color: #246428;
                }
            """)
            print("[Modalità] Riproduzione isolata dello shot")

        # Se stavamo riproducendo, rilancia con nuova logica
        if was_playing:
            def restart_play():
                while self.is_playing:
                    time.sleep(0.05)
                self.handle_play()

            import threading
            threading.Thread(target=restart_play).start()

    def set_dark_theme(self):
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(70, 70, 150))
        dark_palette.setColor(QPalette.HighlightedText, Qt.white)
        self.setPalette(dark_palette)