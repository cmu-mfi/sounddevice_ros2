# sounddevice_ros2

ROS 2 Jazzy microphone capture using Python `sounddevice` and PortAudio.

- **sounddevice_driver**: Publishes each captured block once as
  `foxglove_msgs/msg/RawAudio`, with interleaved PCM-S16 audio and the first sample’s
  ADC-adjusted timestamp. Includes an audio-device listing executable.
- **sounddevice_bringup**: Provides `bringup.launch.py` with namespace and capture settings.

## Build

Run inside the ROS 2 Jazzy environment (the `ros2_jazzy` Distrobox for this workspace):

```zsh
source /opt/ros/jazzy/setup.zsh
cd ~/ros2_ws
rosdep install --from-paths src/sounddevice_ros2 --ignore-src --rosdistro jazzy -y
colcon build --symlink-install --packages-up-to sounddevice_bringup
source install/setup.zsh
```

Runtime dependencies include `rclpy`, `rcl_interfaces`, `foxglove_msgs`, NumPy,
`sounddevice` (rosdep key `python3-sounddevice-pip`), and PortAudio (rosdep key
`portaudio19-dev`, which includes the `libportaudio2` runtime). The runtime
must have access to the input audio device. If pip reports an externally managed
Python environment, install `sounddevice` in a container-side virtual environment
with `--system-site-packages` and use that environment’s Python for both the build
and runtime.

## Usage

```zsh
ros2 run sounddevice_driver sounddevice_list_devices
ros2 launch sounddevice_bringup bringup.launch.py
ros2 launch sounddevice_bringup bringup.launch.py ns:=microphone device:=2 channels:=1
```

The namespaced example publishes `/microphone/audio/raw` from
`/microphone/sounddevice_driver`. Device names can also be matched, for example
`device:='USB Audio'`. Select a channel count and sample rate supported by your input.

| Launch argument | Default | Description |
| --- | --- | --- |
| `ns` | `""` | Namespace for the node and relative topic |
| `log_level` | `error` | `debug`, `info`, `warn`, or `error` |
| `device` | `""` | Input device index or name substring; empty uses the system default |
| `samplerate` | `44100` | Samples per second |
| `blocksize` | `4096` | Samples per channel per block; must be positive |
| `channels` | `4` | Input channel count |
| `audio_topic` | `audio/raw` | RawAudio topic; relative names follow `ns` |

Capture settings are startup parameters. Publishing follows capture blocks rather
than a separate publish rate; audio is always PCM-S16. Normal ROS remapping also
works when running the node directly:

```zsh
ros2 run sounddevice_driver sounddevice_driver_node --ros-args \
  -r __ns:=/microphone -r audio/raw:=audio/capture -p channels:=1
```

This replaces the old `sounddevice_ros` package and its custom `--namespace` option.
Playback and the legacy message definitions are no longer included.
