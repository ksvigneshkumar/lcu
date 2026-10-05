import soundcard as sc
import soundfile as sf
import numpy as np
import threading
import sys
import ctypes

def _init_com():
    if sys.platform == 'win32':
        try:
            # COINIT_MULTITHREADED = 0
            ctypes.windll.ole32.CoInitializeEx(None, 0)
        except Exception:
            pass

class AudioRecorder:
    def __init__(self):
        _init_com()
            
        self.recording = False
        self.fs = 16000
        self.speaker = sc.default_speaker()
        self.mic = sc.default_microphone()
        self.spk_frames = []
        self.mic_frames = []
        self.spk_thread = None
        self.mic_thread = None
        
    def _record_spk(self):
        _init_com()
        try:
            with self.speaker.recorder(samplerate=self.fs) as spk_rec:
                while self.recording:
                    # Small chunks, don't block forever
                    data = spk_rec.record(numframes=self.fs // 4)
                    if data.ndim == 2 and data.shape[1] > 1:
                        data = data.mean(axis=1, keepdims=True)
                    self.spk_frames.append(data)
        except Exception as e:
            print("Speaker recording error:", e)

    def _record_mic(self):
        _init_com()
        try:
            with self.mic.recorder(samplerate=self.fs) as mic_rec:
                while self.recording:
                    data = mic_rec.record(numframes=self.fs // 4)
                    if data.ndim == 2 and data.shape[1] > 1:
                        data = data.mean(axis=1, keepdims=True)
                    self.mic_frames.append(data)
        except Exception as e:
            print("Mic recording error:", e)

    def start(self):
        if self.recording:
            return
        self.recording = True
        self.spk_frames = []
        self.mic_frames = []
        self.spk_thread = threading.Thread(target=self._record_spk, daemon=True)
        self.mic_thread = threading.Thread(target=self._record_mic, daemon=True)
        self.spk_thread.start()
        self.mic_thread.start()
        
    def stop(self, filename):
        if not self.recording:
            return None
        self.recording = False
        
        if self.spk_thread:
            self.spk_thread.join(timeout=1.0)
        if self.mic_thread:
            self.mic_thread.join(timeout=1.0)
        
        spk_data = np.concatenate(self.spk_frames, axis=0) if self.spk_frames else np.zeros((0, 1))
        mic_data = np.concatenate(self.mic_frames, axis=0) if self.mic_frames else np.zeros((0, 1))
        
        # Pad to same length
        max_len = max(len(spk_data), len(mic_data))
        if max_len == 0:
            return None
            
        if len(spk_data) < max_len:
            spk_data = np.pad(spk_data, ((0, max_len - len(spk_data)), (0, 0)))
        if len(mic_data) < max_len:
            mic_data = np.pad(mic_data, ((0, max_len - len(mic_data)), (0, 0)))
            
        mixed = spk_data + mic_data
        mixed = np.clip(mixed, -1.0, 1.0)
        
        sf.write(filename, mixed, self.fs)
        return filename
