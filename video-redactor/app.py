import os
# Force CPU only globally to prevent any CUDA crashes
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import streamlit as st
import tempfile
import json

# --- Monkey patch for PyAV >= 12.0.0 with faster-whisper ---
import av
original_av_open = av.open
def patched_av_open(*args, **kwargs):
    kwargs.pop('metadata_errors', None)
    return original_av_open(*args, **kwargs)
av.open = patched_av_open
# -----------------------------------------------------------

from src.ingest import extract_audio
from src.transcribe import transcribe_audio
from src.rules import load_rules
from src.redact import Redactor
from src.output import write_outputs, format_timestamp
from src.gmeet_bot import GMeetBot

st.set_page_config(page_title="Video Redactor AI", page_icon="🕵️", layout="wide")

st.markdown("""
<style>
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1f6fb2, #2ec4b6) !important;
    color: white !important;
    font-weight: bold !important;
    border: 1px solid transparent !important;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
}
div.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2ec4b6, #1f6fb2) !important;
    border: 1px solid transparent !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Real-Time Video Intelligence for Detection, Transcription & Privacy Protection")
st.markdown("Upload a video or provide a live stream URL. The AI will convert speech to text and redact sensitive patient information based on your rules.")

# State for outputs
if "original_text" not in st.session_state:
    st.session_state.original_text = ""
if "redacted_text" not in st.session_state:
    st.session_state.redacted_text = ""
if "report_json" not in st.session_state:
    st.session_state.report_json = ""

col1, col2 = st.columns([1, 1])

with col1:
    st.header("1. Input Video")
    input_type = st.radio("Select Input Type:", ["Upload Video/Audio File", "Live Stream URL", "Live GMeet Link (Auto-Record Audio)", "Live Mic Recording (Any Meeting)"])
    
    video_path = None
    stream_url = ""
    duration = 60
    
    if input_type == "Upload Video/Audio File":
        uploaded_file = st.file_uploader("Upload Media (mp4, mov, mkv, webm, mp3, wav, m4a)", type=['mp4', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flac'])
        if uploaded_file is not None:
            # Save uploaded file to temp
            file_ext = "." + uploaded_file.name.split('.')[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tfile:
                tfile.write(uploaded_file.read())
                video_path = tfile.name
    elif input_type == "Live Stream URL":
        stream_url = st.text_input("Enter Live Stream / Video URL (rtsp://, http://):")
        duration = st.number_input("How many seconds to record from live stream?", min_value=10, max_value=600, value=60)
        if stream_url:
            video_path = stream_url
    elif input_type in ["Live GMeet Link (Auto-Record Audio)", "Live Mic Recording (Any Meeting)"]:
        if input_type == "Live GMeet Link (Auto-Record Audio)":
            stream_url = st.text_input("Enter Google Meet Link (https://meet.google.com/...):")
            st.info("🎙️ We will automatically open the link in your browser and silently record the audio!")
        else:
            stream_url = ""
            st.info("🎙️ Record audio directly from your computer. You CAN wear headphones! The app will record both your mic and the meeting audio automatically.")
        
        if "recorder" not in st.session_state:
            from src.audio_recorder import AudioRecorder
            st.session_state.recorder = AudioRecorder()
            
        col_rec1, col_rec2 = st.columns(2)
        with col_rec1:
            if st.button("🔴 Start Live Record"):
                if stream_url:
                    import webbrowser
                    webbrowser.open(stream_url)
                st.session_state.recorder.start()
                
        with col_rec2:
            if st.button("⏹️ Stop Recording"):
                import uuid
                import os
                temp_wav = os.path.abspath(f"mic_rec_{uuid.uuid4().hex}.wav")
                saved_path = st.session_state.recorder.stop(temp_wav)
                if saved_path:
                    st.session_state.mic_audio_path = saved_path
                    
        if st.session_state.recorder.recording:
            st.warning("Recording is currently active! You can have your meeting now.")
            
        if "mic_audio_path" in st.session_state and os.path.exists(st.session_state.mic_audio_path):
            video_path = st.session_state.mic_audio_path
            st.success("Audio recorded successfully. Click the Redaction button below to process.")
            st.audio(video_path, format='audio/wav')

with col2:
    st.header("2. Redaction Rules")
    st.markdown("Specify the words, names, or types to redact.")
    
    rule_tab1, rule_tab2 = st.tabs(["✍️ Type Rules", "📄 Upload Rules File"])
    
    default_rules = """# Built-in Types
type:PERSON
type:PHONE_NUMBER
type:EMAIL_ADDRESS
type:LOCATION

# Exact words (Type hospital or patient names here)
Apollo Hospital
Room 204

# Custom Regex (e.g. PT-12345 or PT12345)
regex:PT-?\\d{5}
"""
    
    with rule_tab1:
        rules_text = st.text_area("Type rules (one per line):", value=default_rules, height=200)
        
    with rule_tab2:
        st.markdown("Upload a `.txt` or `.csv` file containing one redaction rule per line.")
        uploaded_rule_file = st.file_uploader("Choose a file", type=['txt', 'csv'])
        if uploaded_rule_file is not None:
            uploaded_rules_content = uploaded_rule_file.read().decode("utf-8")
            rules_text += "\n" + uploaded_rules_content
            st.success(f"Loaded {len(uploaded_rules_content.splitlines())} lines from file. These will be combined with typed rules.")

if st.button("Start AI Redaction Process", type="primary", use_container_width=True):
    if not video_path:
        st.error("Please upload a video or provide a URL first!")
    else:
        with st.spinner("Processing... This might take a minute."):
            try:
                # 1. Save rules to a temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='w', encoding='utf-8') as rule_file:
                    rule_file.write(rules_text)
                    rule_path = rule_file.name
                
                rules_dict = load_rules(rule_path)
                
                if video_path == "GMEET_BOT_MODE":
                    st.info("Starting Browser Bot... Please 'Admit' the bot if you are the host.")
                    st.warning("⚠️ Turn ON 'Captions (CC)' inside the Google Meet for the bot to read the text!")
                    st.write("Click 'Stop' in the top right corner of Streamlit to end the session.")
                    
                    bot = GMeetBot(rules_dict)
                    bot.start(stream_url)
                    
                    st.markdown("### Live Redacted Captions")
                    output_placeholder = st.empty()
                    
                    all_original = []
                    all_redacted = []
                    try:
                        st.info("Listening for captions... Please speak in the meeting.")
                        for original_text, redacted_text in bot.read_captions_generator():
                            if isinstance(original_text, str) and original_text.startswith("ERROR:"):
                                st.error(original_text)
                            else:
                                all_original.append(original_text)
                                all_redacted.append(redacted_text)
                                output_placeholder.text_area("Captions", value="\n\n".join(all_redacted), height=400)
                    except Exception as e:
                        st.error(f"Captions Loop Error: {e}")
                    finally:
                        bot.close()
                        st.session_state.redacted_text = "\n\n".join(all_redacted)
                        st.session_state.original_text = "\n\n".join(all_original)
                        st.session_state.report_json = "{}"
                        st.success(f"GMeet session ended. Extracted {len(all_redacted)} caption blocks.")
                else:
                    with st.status("🚀 Running AI Processing Pipeline...", expanded=True) as status:
                        # Optional: Emotion Analysis for Videos
                        if video_path.lower().endswith(('.mp4', '.mov', '.mkv', '.webm')):
                            st.write("⏳ Analyzing video for facial emotions...")
                            from src.emotion import analyze_video_emotion
                            emo_res = analyze_video_emotion(video_path)
                            st.session_state.emotion_result = emo_res
                            if "dominant" in emo_res:
                                st.write(f"✅ Emotion Analysis Complete! (Dominant: {emo_res['dominant'].upper()})")
                                
                        # 2. Ingest
                        st.write("⏳ Preparing audio...")
                        audio_path = extract_audio(video_path, duration=duration)
                        st.audio(audio_path, format='audio/wav')
                        st.write("✅ Audio preparation complete!")
                        
                        # 3. Transcribe
                        st.write("⏳ Transcribing speech to text...")
                        segments = transcribe_audio(audio_path)
                        
                        # Generate original text before redaction
                        original_lines = []
                        for seg in segments:
                            start_str = format_timestamp(seg['start'])
                            end_str = format_timestamp(seg['end'])
                            original_lines.append(f"[{start_str} - {end_str}] {seg['text']}")
                        st.session_state.original_text = "\n".join(original_lines)
                        st.write("✅ Transcription complete!")
                        
                        # 4. Redact
                        st.write("⏳ Redacting sensitive information...")
                        redactor = Redactor(rules_dict)
                        redacted_segments = []
                        for seg in segments:
                            redacted_text_chunk, redactions = redactor.redact_segment(seg['text'])
                            redacted_segments.append({
                                "start": seg['start'],
                                "end": seg['end'],
                                "text": redacted_text_chunk,
                                "redactions": redactions
                            })
                            
                        # 5. Output
                        out_dir = "output"
                        os.makedirs(out_dir, exist_ok=True)
                        out_txt = os.path.join(out_dir, "redacted_transcript.txt")
                        out_json = os.path.join(out_dir, "redaction_report.json")
                        out_original_txt = os.path.join(out_dir, "original_transcript.txt")
                        
                        # Write original transcript to file
                        with open(out_original_txt, "w", encoding="utf-8") as f:
                            f.write(st.session_state.original_text)
                            
                        write_outputs(redacted_segments, rules_dict, out_txt, out_json)
                        
                        with open(out_txt, "r", encoding="utf-8") as f:
                            st.session_state.redacted_text = f.read()
                            
                        with open(out_json, "r", encoding="utf-8") as f:
                            st.session_state.report_json = f.read()
                            
                        st.write("✅ Redaction complete!")
                        status.update(label="🎉 All Processing Completed Successfully!", state="complete", expanded=False)
                
            except Exception as e:
                st.error(f"Error during processing: {e}")

if st.session_state.redacted_text:
    st.divider()
    st.header("3. Results Dashboard")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Original Transcript", "🛡️ Safe Redacted File", "📊 Redaction Report", "🎭 Emotion Analysis"])
    
    with tab1:
        st.markdown("### The Original Text from Video")
        st.info("This contains the raw, sensitive information directly from the video.")
        st.text_area("Original Transcript:", value=st.session_state.original_text, height=300)
        st.download_button("Download Original Transcript (.txt)", data=st.session_state.original_text, file_name="original_transcript.txt", mime="text/plain")
        
    with tab2:
        st.markdown("### The Redacted Text (Safe for LLM/RAG)")
        st.success("Sensitive data has been safely replaced with AI tags.")
        st.text_area("Safe Transcript:", value=st.session_state.redacted_text, height=300)
        st.download_button("Download Safe Transcript (.txt)", data=st.session_state.redacted_text, file_name="redacted_transcript.txt", mime="text/plain")
        
    with tab3:
        st.markdown("### Redaction Details & Metrics")
        st.warning("Details of what was redacted and when.")
        try:
            report_dict = json.loads(st.session_state.report_json)
            st.json(report_dict)
        except:
            st.text_area("Report JSON:", value=st.session_state.report_json, height=300)
            
        st.download_button("Download Report (.json)", data=st.session_state.report_json, file_name="redaction_report.json", mime="application/json")

    with tab4:
        st.markdown("### Facial Emotion Analysis")
        if "emotion_result" in st.session_state and st.session_state.emotion_result:
            emo = st.session_state.emotion_result
            if "error" in emo:
                st.error(emo["error"])
            else:
                st.success(f"Dominant Emotion: **{emo.get('dominant', 'Unknown').upper()}**")
                if "processed_video" in emo and os.path.exists(emo["processed_video"]):
                    st.video(emo["processed_video"])
                st.write("Emotion Breakdown throughout video:")
                
                emotion_emojis = {
                    "happy": "😊", "sad": "😢", "angry": "😠", 
                    "surprise": "😲", "fear": "😨", "disgust": "🤢", "neutral": "😐"
                }
                for em_name, count in emo.get("counts", {}).items():
                    em_icon = emotion_emojis.get(em_name.lower(), "🔹")
                    st.markdown(f"**{em_icon} {em_name.capitalize()}**: {count} frames")
        else:
            st.info("No emotion data available. Upload a video file to analyze emotions.")
