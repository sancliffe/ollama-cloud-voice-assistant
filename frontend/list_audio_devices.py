import speech_recognition as sr


def list_devices():
    print("Available Audio Devices:\n")
    try:
        names = sr.Microphone.list_microphone_names()
        for i, name in enumerate(names):
            print(f"Device ID {i}: {name}")
    except Exception as e:
        print(f"Error querying devices: {e}")
        print("Make sure PyAudio is installed correctly.")


if __name__ == "__main__":
    list_devices()
