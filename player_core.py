
# player_core.py

import os
import cv2
import time
import queue
import threading
import pygame
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

from debug_utils import dbg, trace, log_exception


class Shot:
    def __init__(self, shot_id, reparto, frame_path, start_frame, end_frame, absolute_start=0):
        self.shot_id = shot_id
        self.reparto = reparto
        self.frame_path = frame_path
        self.start_frame = int(start_frame) if start_frame else None
        self.end_frame = int(end_frame) if end_frame else None
        self.absolute_start = absolute_start

    def __repr__(self):
        return f"<Shot {self.shot_id} ({self.reparto}) - {self.start_frame} to {self.end_frame}>"


def parse_shot_list(csv_path):
    import csv
    shots = []
    audio_path = None

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        absolute_counter = 0
        for row in reader:
            if row["shot_id"] == "audio":
                audio_path = row["frame_path"]
            else:
                sf = int(row["start_frame"])
                ef = int(row["end_frame"])
                shots.append(Shot(
                    shot_id=row["shot_id"],
                    reparto=row["reparto"],
                    frame_path=row["frame_path"],
                    start_frame=sf,
                    end_frame=ef,
                    absolute_start=absolute_counter
                ))
                absolute_counter += (ef - sf + 1)

    return shots, audio_path


class ImageCache:
    def __init__(self, frame_paths, max_cache_size=150, start_index=0):
        self.frame_paths = frame_paths[start_index:]
        self.cache = queue.Queue(maxsize=max_cache_size)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._preload_images)
        self.thread.start()

    def _preload_images(self):
        for path in self.frame_paths:
            if self.stop_event.is_set():
                break
            while self.cache.full():
                time.sleep(0.001)
            img = cv2.imread(path)
            if img is not None:
                self.cache.put(img)
            else:
                print(f"[MANCANTE] {path}")

    def get_image(self):
        try:
            return self.cache.get(timeout=1)
        except queue.Empty:
            return None

    def stop(self):
        self.stop_event.set()
        self.thread.join()


def play_with_cache(shot_list, video_label, audio_path=None, fps=25, max_cache_size=150,
                    on_frame=None, stop_flag=None, pause_flag=None,
                    start_index=0, audio_offset_frames=None,
                    command_q=None):
        # [PATCH] calcolo offset audio (globale se Episodio, locale se Scena)
    trace("CORE", "play_with_cache",
          start_index=start_index,
          offset_frames=audio_offset_frames,
          fps=fps)                     # <── traccia dettagliata

    # [PATCH-SEEK] se la coda non è stata fornita creane una vuota (no-op)
    if command_q is None:
        command_q = queue.Queue()

    audio_start_frames = audio_offset_frames if audio_offset_frames is not None else start_index
    if not shot_list:
        print("⚠ Nessuno shot da riprodurre.")
        return

    frame_duration = 1.0 / fps

    all_paths = []
    for shot in shot_list:
        for frame_num in range(shot.start_frame, shot.end_frame + 1):
            padded = str(frame_num).zfill(4)
            path = shot.frame_path.replace("####", padded)
            all_paths.append(path)

    total_frame_count = len(all_paths)
    if start_index >= total_frame_count:
        dbg("WARN", "Start index fuori range",
            start_index=start_index, max_index=total_frame_count-1)
        start_index = 0

    cache = ImageCache(all_paths, max_cache_size=max_cache_size, start_index=start_index)

    if audio_path:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.stop()
            pygame.mixer.music.load(audio_path)
            print(f"[AUDIO DEBUG] offset_frames: {audio_start_frames}, "
                  f"start_sec: {audio_start_frames / fps:.2f}")
            pygame.mixer.music.play(start=audio_start_frames / fps)
        except Exception as e:
            print(f"[Errore audio] {e}")
    else:
        print("[INFO] Audio disattivato o non presente")

    timestamps_live = []
    timestamps_all = []
    total_pause_time = 0.0
    start_time = time.time() - (start_index * frame_duration)
    pause_start_time = None

    # ------ PLAYBACK MAIN LOOP -------------------------------------------
    i = start_index
    trim_active = False          # [PATCH-TRIM] flag
    trim_start, trim_end = 0, total_frame_count - 1
    loop_on = False           # [PATCH-LOOP] stato corrente del loop
    start_time = time.time() - (i * frame_duration)

    while i < total_frame_count:
        # -------- [PATCH-SEEK/TRIM] processa eventuali comandi ------------
        try:
            cmd, arg = command_q.get_nowait()
            if cmd == "seek":
                dbg("CORE", "seek request", target=arg)
                i = max(0, min(arg, total_frame_count - 1))
                cache.stop()
                cache = ImageCache(all_paths, max_cache_size=max_cache_size, start_index=i)
                start_time = time.time() - (i * frame_duration)
                if audio_path:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.play(start=i / fps)

            elif cmd == "trim":
                trim_start, trim_end = arg
                trim_active = True
                dbg("CORE", "trim ON", start=trim_start, end=trim_end)

                # [FIX] ricrea SEMPRE la cache e riparti dal primo frame del range
                i = trim_start
                cache.stop()
                cache = ImageCache(all_paths, max_cache_size=max_cache_size, start_index=i)
                start_time = time.time() - (i * frame_duration)
                if audio_path:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.play(start=i / fps)
                continue          # forza il ridisegno immediato del nuovo frame

            elif cmd == "trim_off":
                trim_active = False
                trim_start, trim_end = 0, total_frame_count - 1
                dbg("CORE", "trim OFF")

            elif cmd == "loop":
                loop_on = bool(arg)
                dbg("CORE", "loop set", enabled=loop_on)

        except queue.Empty:
            pass
        if stop_flag and stop_flag():
            print("[STOP] Playback interrotto esternamente.")
            break

        while pause_flag and pause_flag():
            if pause_start_time is None:
                pause_start_time = time.time()
                if pygame.mixer.get_init():
                    pygame.mixer.music.pause()
            time.sleep(0.05)
            if stop_flag and stop_flag():
                break

        if pause_start_time is not None:
            # Calcola durata pausa e correggi start_time
            pause_duration = time.time() - pause_start_time
            total_pause_time += pause_duration
            start_time += pause_duration
            pause_start_time = None
            if pygame.mixer.get_init():
                pygame.mixer.music.unpause()

        target_time = start_time + (i * frame_duration)
        now = time.time()
        delay = target_time - now
        if delay > 0:
            time.sleep(delay)

        path = all_paths[i]
        frame = cache.get_image()
        if frame is not None:
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            q_img = QImage(img_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            video_label.setPixmap(pixmap.scaled(
                video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            ))

        now = time.time()
        timestamps_all.append(now)
        timestamps_live.append(now)
        if len(timestamps_live) > 10:
            timestamps_live.pop(0)

        if len(timestamps_live) >= 2:
            elapsed = timestamps_live[-1] - timestamps_live[0]
            fps_istantaneo = (len(timestamps_live) - 1) / elapsed
        else:
            fps_istantaneo = 0.0

        if on_frame:
            on_frame(i + 1, total_frame_count, fps_istantaneo)

        i += 1
        # [PATCH-ISOLATE] se siamo in trim e superiamo la fine
        if trim_active and i > trim_end:
            if loop_on:
                i = trim_start
                if audio_path:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.play(start=i / fps)
                continue
            else:
                dbg("CORE", "trim ended, stopping")
                break          # esce dal while → loop finito
        # [PATCH-TRIM] se isolati su una scena e supero la fine
        if trim_active and i > trim_end:
            i = trim_start  # loop di scena (anche se loop GUI disattivato)

    cache.stop()
    if audio_path:
        pygame.mixer.music.stop()

    actual_fps = None
    if len(timestamps_all) > 1:
        total_time = timestamps_all[-1] - timestamps_all[0] - total_pause_time
        actual_fps = (len(timestamps_all) - 1) / total_time
        print(f"\n[PERFORMANCE] FPS medio episodio: {actual_fps:.2f} (target: {fps})")
        if actual_fps < fps - 1:
            print("[⚠️ AVVISO] Il player non ha mantenuto il framerate target!")
                
    dbg("CORE", "loop ended",
        reason="stop_flag" if stop_flag and stop_flag() else "fine video",
        last_frame=i-1)
    return actual_fps
