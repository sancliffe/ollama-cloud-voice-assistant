import configparser
import logging
import requests
import pyttsx3
import speech_recognition as sr

# Load config
config = configparser.ConfigParser()
config.read('config.ini')

# Setup logging
logging.basicConfig(level=getattr(logging, config.get('Logging', 'log_level', fallback='INFO')),
                    filename=config.get(
                        'Logging', 'log_file', fallback='assistant.log'),
                    format='%(asctime)s - %(levelname)s - %(message)s')

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)


def init_tts():
    engine = pyttsx3.init()
    return engine


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
        logging.error(
            "Timeout connecting to Ollama. The GKE cluster might be cold starting. Please wait a few minutes and try again.")
        return "Sorry, the cloud backend timed out while starting up."
    except Exception as e:
        logging.error(f"Error communicating with Ollama: {e}")
        return "I'm having trouble connecting to my brain in the cloud."


def main():
    logging.info("Starting Assistant...")

    try:
        tts_engine = init_tts()
        recognizer = sr.Recognizer()

        # Configure audio device
        input_device_str = config.get('Audio', 'input_device', fallback='0')
        input_device = int(
            input_device_str) if input_device_str.isdigit() else None

        logging.info(f"Using input device index: {input_device}")

        with sr.Microphone(device_index=input_device) as source:
            logging.info("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=2)

            while True:
                try:
                    logging.info("\nListening...")
                    audio = recognizer.listen(source, timeout=int(config.get(
                        'Timeouts', 'speech_recognition_timeout', fallback='30')))

                    logging.info("Transcribing...")
                    # Using recognize_google as a lightweight fallback for STT
                    transcript = recognizer.recognize_google(audio)

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

                except sr.UnknownValueError:
                    logging.info("Could not understand audio.")
                except sr.RequestError as e:
                    logging.error(
                        f"Could not request results from STT service; {e}")
                except sr.WaitTimeoutError:
                    continue
                except Exception as e:
                    logging.error(f"Error in main loop: {e}")
    except Exception as e:
        logging.error(f"Failed to initialize: {e}")


if __name__ == "__main__":
    main()
