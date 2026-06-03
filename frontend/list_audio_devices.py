import sounddevice as sd

def list_devices():
    print("Available Audio Devices:\n")
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            device_type = []
            if dev['max_input_channels'] > 0:
                device_type.append("Input (Microphone)")
            if dev['max_output_channels'] > 0:
                device_type.append("Output (Speaker)")
            
            if not device_type:
                continue
                
            type_str = " / ".join(device_type)
            print(f"Device ID {i}: {dev['name']} [{type_str}]")
    except Exception as e:
        print(f"Error querying devices: {e}")

if __name__ == "__main__":
    list_devices()
