
# player_core.py

import os
import cv2
import time
import queue
import threading
import pygame
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


class Shot:
    def __init__(self, shot_id, reparto, frame_path, start_frame, end_frame):
        self.shot_id = shot_id
        self.reparto = reparto
        self.frame_path = frame_path
        self.start_frame = int(start_frame) if start_frame else None
        self.end_frame = int(end_frame) if end_frame else None

    def __repr__(self):
        return f"<Shot {self.shot_id} ({self.reparto}) - {self.start_frame} to {self.end_frame}>"


def parse_shot_list(csv_path):
    import csv
    shots = []
    audio_path = None

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['shot_id'].lower() == 'audio':
                audio_path = row['frame_path']
            else:
                shot = Shot(
                    shot_id=row['shot_id'],
                    reparto=row['reparto'],
                    frame_path=row['frame_path'],
                    start_frame=row['start_frame'],
                    end_frame=row['end_frame']
                )
                shots.append(shot)

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
                    on_frame=None, stop_flag=None, pause_flag=None, start_index=0):
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
        print("[Start Index] Fuori range, playback interrotto.")
        return

    cache = ImageCache(all_paths, max_cache_size=max_cache_size, start_index=start_index)

    if audio_path:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.stop()
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play(start=start_index / fps)
        except Exception as e:
            print(f"[Errore audio] {e}")
    else:
        print("[INFO] Audio disattivato o non presente")

    timestamps_live = []
    timestamps_all = []
    total_pause_time = 0.0
    start_time = time.time() - (start_index * frame_duration)
    pause_start_time = None

    i = start_index
    while i < len(all_paths):
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

    return actual_fps