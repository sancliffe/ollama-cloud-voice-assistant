import configparser
import json
import logging
import os
import requests
import pyttsx3
import speech_recognition as sr
from faster_whisper import WhisperModel

# Load config
config = configparser.ConfigParser()
config.read('config.ini')

# Setup logging
logging.basicConfig(level=getattr(logging, config['Logging']['log_level'], 'INFO'), 
                    filename=config.get('Logging', 'log_file', fallback='assistant.log'),
                    format='%(asctime)s - %(levelname)s - %(message)s')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def init_tts():
    engine = pyttsx3.init()
    return engine

def init_stt():
    model_size = config.get('Models', 'stt_model', fallback='base')
    logging.info(f"Loading faster-whisper model: {model_size}")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    return model

def chat_with_ollama(prompt):
    url = f"{config.get('Models', 'ollama_host', fallback='http://localhost:11434')}/api/generate"
    model = config.get('Models', 'ollama_model', fallback='llama3')
    timeout = int(config.get('Models', 'ollama_timeout', fallback='240'))
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        logging.info(f"Sending request to {url} (timeout: {timeout}s)...")
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json().get('response', '')
    except requests.exceptions.Timeout:
        logging.error("Timeout connecting to Ollama. The GKE cluster might be cold starting. Please wait a few minutes and try again.")
        return "Sorry, the cloud backend timed out while starting up."
    except Exception as e:
        logging.error(f"Error communicating with Ollama: {e}")
        return "I'm having trouble connecting to my brain in the cloud."

def main():
    logging.info("Starting Assistant...")
    
    try:
        tts_engine = init_tts()
        stt_model = init_stt()
        recognizer = sr.Recognizer()
        
        # Configure audio device
        input_device = int(config.get('Audio', 'input_device', fallback='0'))
        
        logging.info(f"Using input device index: {input_device}")
        
        with sr.Microphone(device_index=input_device) as source:
            logging.info("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=2)
            
            while True:
                try:
                    logging.info("\nListening...")
                    audio = recognizer.listen(source, timeout=int(config.get('Timeouts', 'speech_recognition_timeout', fallback='30')))
                    
                    # Convert audio to wav format in memory for faster-whisper
                    wav_data = audio.get_wav_data()
                    
                    # write to temp file since faster-whisper prefers file or numpy array
                    temp_file = "temp_audio.wav"
                    with open(temp_file, "wb") as f:
                        f.write(wav_data)
                        
                    logging.info("Transcribing...")
                    segments, info = stt_model.transcribe(temp_file, beam_size=5)
                    
                    transcript = "".join([segment.text for segment in segments]).strip()
                    
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    
                    if not transcript:
                        continue
                        
                    logging.info(f"You: {transcript}")
                    
                    # Check for exit commands
                    clean_transcript = transcript.lower().strip()
                    if any(word in clean_transcript for word in ["exit", "quit", "stop", "goodbye"]):
                        logging.info("Exiting...")
                        tts_engine.say("Goodbye!")
                        tts_engine.runAndWait()
                        break
                        
                    # Get response from LLM
                    response_text = chat_with_ollama(transcript)
                    logging.info(f"Assistant: {response_text}")
                    
                    # Speak response
                    tts_engine.say(response_text)
                    tts_engine.runAndWait()
                    
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logging.error(f"Error in main loop: {e}")
    except Exception as e:
        logging.error(f"Failed to initialize: {e}")

if __name__ == "__main__":
    main()
