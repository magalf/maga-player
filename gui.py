# ⚠️ IMPORT NECESSARI
import time
import threading
import queue
import pygame
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel, QListWidget,
    QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QFrame, QSpinBox, QFileDialog)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, QTimer
from player_core import parse_shot_list, play_with_cache
from debug_utils import dbg, trace, log_exception

class PlayerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.mode_episode = True
        self.loop_enabled = False
        self.resume_frame_index = 0  # [DEBUG INIT]
        self.is_playing = False
        self.should_stop = False
        self.should_pause = False
        # self.resume_frame_index = 0  # disabilitato per mantenere posizione
        self.current_shot = None

        self.total_episode_frames = 0
        self.episode_frame_map = []  # mappa globale di tutti i frame

        self.setWindowTitle("Player Episodio Maga - GUI")
        self.setMinimumSize(1280, 720)
        self.loaded_shots = []
        self.audio_path = None
        self.current_reparto = "animazione"
        self.set_dark_theme()

        # UI completa copiata e integrata (vedi file originale utente)
        # — mantenuta per compatibilità

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

        self.mode_toggle_btn = QPushButton("Episodio")
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
        self.shot_list.itemClicked.connect(self.shot_selected_in_scene_mode)
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

    def shot_selected_in_scene_mode(self):
        shots = [s for s in self.loaded_shots if s.reparto == self.current_reparto]
        row = self.shot_list.currentRow()
        if row < 0 or row >= len(shots):
            return

        selected = shots[row]
        dbg("SELECT", "click lista",
            shot=selected.shot_id,
            frame_abs=selected.absolute_start,
            playing=self.is_playing,
            mode="Ep" if self.mode_episode else "Sc")        

        # Calcola frame assoluto nel montaggio
        frame_global_index = 0
        for s in shots:
            if s.shot_id == selected.shot_id:
                break
            frame_global_index += (s.end_frame - s.start_frame + 1)

        if self.mode_episode:
            self.resume_frame_index = selected.absolute_start
            dbg("GUI", "enqueue seek", target=self.resume_frame_index)
            if hasattr(self, "command_q"):
                self.command_q.put(("seek", self.resume_frame_index))
            # niente STOP / restart in modalità Episodio
        else:
            self.current_shot = selected
            self.resume_frame_index = 0
            abs_start = selected.absolute_start
            abs_end   = abs_start + (selected.end_frame - selected.start_frame)
            dbg("GUI", "trim+seek scena", start=abs_start, end=abs_end)

            if hasattr(self, "command_q"):
                self.command_q.put(("trim", (abs_start, abs_end)))
                self.command_q.put(("seek", abs_start))
            # nessuno stop / restart
            shot_len = selected.end_frame - selected.start_frame + 1
            self.timeline_slider.setMaximum(shot_len)
            self.frame_counter.setText(f"Frame: 0000 / {shot_len:04d}")

    def handle_play(self):
        trace("GUI", "handle_play",
            mode="Episodio" if self.mode_episode else "Scena",
            resume_frame=self.resume_frame_index)
        print(f"[▶ handle_play] resume_frame_index: {self.resume_frame_index}")
        # [PATCH-SEEK] coda comandi (una sola istanza)
        if not hasattr(self, "command_q"):
            self.command_q = queue.Queue()
        if self.is_playing:
            print("[INFO] Riproduzione già in corso.")
            self.should_pause = False
            return

        if not self.loaded_shots:
            print("⚠️ Nessuno shot caricato.")
            return

        if self.mode_episode:
            # filtra gli shot in base al reparto corrente
            selected_shots = [
                s for s in self.loaded_shots if s.reparto == self.current_reparto
            ]
            # mappa completa episodio solo sugli shot filtrati
            self.episode_frame_map = []
            for s in selected_shots:
                self.episode_frame_map.extend(range(s.start_frame, s.end_frame + 1))
            self.total_episode_frames = len(self.episode_frame_map)
        else:
            if not self.current_shot:
                print("[⚠️] Nessuno shot selezionato.")
                return
            selected_shots = [self.current_shot]
            self.episode_frame_map = list(
                range(self.current_shot.start_frame, self.current_shot.end_frame + 1)
            )
            self.total_episode_frames = len(self.episode_frame_map)


        fps_value = self.fps_spinner.value()
        cache_value = self.cache_spinner.value()
        # [PATCH] calcola offset audio corretto
        if self.mode_episode:
            audio_offset_frames = self.resume_frame_index
        else:
            audio_offset_frames = (self.current_shot.absolute_start +
                                   self.resume_frame_index)
        print(f"[AUDIO] offset_frames = {audio_offset_frames}")

        audio = self.audio_path  # audio sempre attivo

        def update_gui_live(current_frame, total_frames, fps_ist):
            self.resume_frame_index = current_frame
            self.frame_counter.setText(f"Frame: {current_frame:04d} / {total_frames:04d}")
            self.fps_label.setText(f"FPS: {fps_ist:.2f}")
            self.timeline_slider.setValue(int((current_frame / total_frames) * 100))


        def playback_loop():
            try:
                dbg("THREAD", "Avvio playback loop")
                self.is_playing = True
                self.should_stop = False
                self.should_pause = False

                while self.is_playing:
                    play_with_cache(
                        selected_shots,   # <— solo shot del reparto corrente
                        self.video_frame,
                        audio,
                        fps=fps_value,
                        max_cache_size=cache_value,
                        on_frame=update_gui_live,
                        stop_flag=lambda: self.should_stop,
                        pause_flag=lambda: self.should_pause,
                        # start_index va sempre in coordinate *assolute*
                        start_index=(
                        self.resume_frame_index
                        if self.mode_episode
                        else self.current_shot.absolute_start + self.resume_frame_index
                    ),
                        audio_offset_frames=audio_offset_frames,
                        command_q=self.command_q       # <── PASSAGGIO CODA
                    )

                    if self.should_stop or not self.loop_enabled:
                        break

                    # riparte se in loop e non è stato premuto Stop
                    self.should_pause = False

                self.is_playing = False
            except Exception as e:
                log_exception("THREAD", e)

        # se un thread è già vivo → chiedi lo stop e aspetta che termini
        if getattr(self, "play_thread", None) and self.play_thread.is_alive():
            self.play_thread.join(timeout=1.0)
        self.should_stop = False

        # ——[PATCH-TRIM] imposta il range sin dall'avvio ——
        if self.mode_episode:
            self.command_q.put(("trim_off", None))
        else:
            abs_start = self.current_shot.absolute_start
            abs_end   = abs_start + (self.current_shot.end_frame - self.current_shot.start_frame)
            self.command_q.put(("trim", (abs_start, abs_end)))
            # assicura che parta dal frame locale corretto
            self.command_q.put(("seek", abs_start + self.resume_frame_index))

        dbg("THREAD", "New", start=self.resume_frame_index,
            prev_alive=self.play_thread.is_alive() if getattr(self, "play_thread", None) else False)
        self.play_thread = threading.Thread(target=playback_loop, daemon=True)
        self.play_thread.start()

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

        # [PATCH-LOOP] comunica il nuovo stato al core
        if hasattr(self, "command_q"):
            self.command_q.put(("loop", self.loop_enabled))

    def handle_stop(self):
        """
        STOP:
        • termina gentilmente il loop
        • mette l’audio in pausa
        • riporta il frame all’inizio della modalità corrente
        """
        dbg("STOP", "invocato",
            thread=threading.current_thread().name,
            mode="Ep" if self.mode_episode else "Sc",
            playing=self.is_playing)
        self.should_pause = False
        self.is_playing = False

        # join sicuro – solo se siamo nel thread GUI
        if (hasattr(self, "play_thread")
                and self.play_thread.is_alive()
                and threading.current_thread() is not self.play_thread):
            self.play_thread.join(timeout=0.5)

        # ferma audio subito
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

        # azzera l’indice e aggiorna GUI
        self.resume_frame_index = 0
        if not self.mode_episode:
            # in SCENA si resta sullo shot corrente ma a frame 0
            self.timeline_slider.setValue(0)
            self.frame_counter.setText("Frame: 0000 / "
                                        f"{self.current_shot.end_frame - self.current_shot.start_frame + 1:04d}")
        else:
            # in EPISODIO torna all’inizio assoluto
            self.timeline_slider.setValue(0)
            if self.total_episode_frames:
                self.frame_counter.setText(f"Frame: 0000 / {self.total_episode_frames:04d}")

    def handle_pause(self):
        if self.is_playing:
            self.should_pause = True
            print("[Pausa] Playback in pausa")

    def toggle_episode_mode(self):
        # non fermiamo più il thread: continuerà con trim/seek
        self.mode_episode = not self.mode_episode
        # se stiamo passando a SCENA deduci lo shot corrente dal frame globale
        if not self.mode_episode:
            for sh in self.loaded_shots:
                if sh.absolute_start <= self.resume_frame_index <= sh.absolute_start + (sh.end_frame - sh.start_frame):
                    self.current_shot = sh
                    break
        # [PATCH] sincronizza indice frame quando si cambia modalità
        if self.current_shot:
            if self.mode_episode:   # Scena → Episodio (locale → globale)
                self.resume_frame_index = (self.current_shot.absolute_start +
                                           self.resume_frame_index)
            else:                   # Episodio → Scena (globale → locale)
                # converti l'indice globale in locale e clampalo
                self.resume_frame_index = max(
                    0,
                    min(
                        self.resume_frame_index - self.current_shot.absolute_start,
                        self.current_shot.end_frame - self.current_shot.start_frame
                    )
                )
                
        dbg("MODE", "toggle",
            to="Episodio" if self.mode_episode else "Scena",
            resume_frame=self.resume_frame_index)
        
        # ——[PATCH-TRIM] comunica al core il nuovo range ——
        if hasattr(self, "command_q"):
            if self.mode_episode:
                self.command_q.put(("trim_off", None))
                if self.total_episode_frames:
                    self.timeline_slider.setMaximum(self.total_episode_frames)
                    self.frame_counter.setText(f"Frame: {self.resume_frame_index:04d} / {self.total_episode_frames:04d}")
            elif self.current_shot:
                abs_s = self.current_shot.absolute_start
                abs_e = abs_s + (self.current_shot.end_frame - self.current_shot.start_frame)
                self.command_q.put(("trim", (abs_s, abs_e)))
                self.command_q.put(("seek", abs_s + self.resume_frame_index))
                # aggiorna slider & contatore per lo shot
                shot_len = abs_e - abs_s + 1
                self.timeline_slider.setMaximum(shot_len)
                self.frame_counter.setText(f"Frame: {self.resume_frame_index:04d} / {shot_len:04d}")

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
