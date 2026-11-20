"""List the audio device indices and names available to PortAudio."""

import sounddevice as sd


def main():
    print(sd.query_devices())


if __name__ == '__main__':
    main()
