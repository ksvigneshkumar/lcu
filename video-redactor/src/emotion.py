import cv2
import logging
import os
# Force CPU only to prevent cuDNN hard crashes on laptops without proper NVIDIA drivers
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

from fer.fer import FER
from collections import Counter

import tempfile

def analyze_video_emotion(video_path: str, sample_rate: int = 15) -> dict:
    """
    Analyzes the video file to detect facial emotions.
    Draws bounding boxes and emotions on the video and saves it.
    """
    logging.info(f"Starting emotion analysis on {video_path}")
    detector = FER(mtcnn=True)
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        logging.error("Failed to open video for emotion analysis.")
        return {"error": "Could not open video file"}
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    
    out_path = os.path.join(tempfile.gettempdir(), "emotion_processed.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
    
    frame_count = 0
    emotions_found = []
    last_result = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % sample_rate == 0:
            try:
                last_result = detector.detect_emotions(frame)
                if last_result:
                    dominant_emotion = max(last_result[0]["emotions"], key=last_result[0]["emotions"].get)
                    emotions_found.append(dominant_emotion)
            except Exception as e:
                logging.warning(f"Emotion detection failed on frame {frame_count}: {e}")
                
        # Draw bounding boxes and emotion text
        if last_result:
            for face in last_result:
                box = face["box"]
                emotions = face["emotions"]
                dom = max(emotions, key=emotions.get)
                
                # Draw Rectangle
                cv2.rectangle(frame, (box[0], box[1]), (box[0]+box[2], box[1]+box[3]), (0, 255, 0), 2)
                # Put Text
                cv2.putText(frame, dom.upper(), (box[0], box[1]-10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
        out.write(frame)
        frame_count += 1
        
    cap.release()
    out.release()
    
    # Convert to web-playable H.264 and merge original audio
    final_out = os.path.join(tempfile.gettempdir(), "emotion_final.mp4")
    # -y (overwrite), -i (video), -i (audio source), -c:v libx264 (H264 codec), -c:a aac (audio codec)
    # -map 0:v:0 (take video from first input), -map 1:a:0? (take audio from second input if it exists)
    cmd = f'ffmpeg -y -i "{out_path}" -i "{video_path}" -c:v libx264 -c:a aac -map 0:v:0 -map 1:a:0? "{final_out}" -loglevel quiet'
    os.system(cmd)
    
    if not emotions_found:
        return {"dominant": "Neutral / No Face Detected", "counts": {}, "processed_video": final_out}
        
    counts = dict(Counter(emotions_found))
    dominant = max(counts, key=counts.get)
    
    logging.info(f"Emotion analysis complete. Dominant: {dominant}")
    return {
        "dominant": dominant,
        "counts": counts,
        "processed_video": final_out
    }
