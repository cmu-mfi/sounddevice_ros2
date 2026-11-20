#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from foxglove_msgs.msg import RawAudio
import sounddevice as sd
import numpy as np
import threading
import argparse

class SoundDevicePublisher(Node):
    """ROS2 node for publishing audio data from sounddevice"""

    def __init__(self, namespace=""):
        super().__init__('sounddevice_publisher')
        
        print(f"Device: {sd.query_devices()}")
        
        # Declare parameters
        self.declare_parameter('device', None)
        self.declare_parameter('samplerate', 44100)
        self.declare_parameter('blocksize', 4096)
        self.declare_parameter('channels', 4)
        # Force dtype to int16 for PCM-S16
        self.declare_parameter('dtype', 'int16')
        self.declare_parameter('publish_rate', 20)
        
        # Get parameters
        self.device = self.get_parameter('device').value
        self.samplerate = self.get_parameter('samplerate').value
        self.blocksize = self.get_parameter('blocksize').value
        self.channels = self.get_parameter('channels').value
        self.dtype = self.get_parameter('dtype').value
        
        # Create publisher
        # Publish to 'audio/raw' topic with RawAudio
        self.publisher = self.create_publisher(RawAudio, namespace.strip('/')+'/audio/raw', 10)
        
        # Audio stream and thread
        self.stream = None
        self.audio_data = None
        self.lock = threading.Lock()
        self.running = True
        
        self.get_logger().info(f'Starting sounddevice publisher on device {self.device}')
        self.get_logger().info(f'Sample rate: {self.samplerate}, Block size: {self.blocksize}, Channels: {self.channels}, Format: pcm-s16')
        
        # Start audio stream in separate thread
        self.audio_thread = threading.Thread(target=self._audio_stream_thread, daemon=True)
        self.audio_thread.start()
        
        # Create timer for publishing
        publish_rate = self.get_parameter('publish_rate').value
        if publish_rate is None or publish_rate == 0:
            publish_rate = 10.0
        self.timer = self.create_timer(1.0 / float(publish_rate), self._publish_audio)

    def _audio_stream_thread(self):
        """Run audio stream in separate thread"""
        try:
            def audio_callback(indata, frames, time, status):
                if status:
                    self.get_logger().warn(f'Audio status: {status}')
                with self.lock:
                    # Ensure int16 for PCM-S16
                    self.audio_data = indata.copy().astype(np.int16)

            with sd.InputStream(
                device=self.device,
                samplerate=self.samplerate,
                blocksize=self.blocksize,
                channels=self.channels,
                dtype='int16',
                callback=audio_callback
            ):
                while self.running:
                    sd.sleep(100)
        except Exception as e:
            self.get_logger().error(f'Audio stream error: {e}')

    def _publish_audio(self):
        """Publish audio data as foxglove_msgs/RawAudio (PCM-S16)"""
        from builtin_interfaces.msg import Time
        import rclpy.clock
        with self.lock:
            if self.audio_data is not None:
                msg = RawAudio()
                # Flatten and convert to bytes (little-endian int16)
                msg.data = self.audio_data.flatten().tobytes()
                msg.format = 'pcm-s16'
                msg.sample_rate = self.samplerate
                msg.number_of_channels = self.channels
                # Set timestamp to now
                now = self.get_clock().now().to_msg()
                msg.timestamp = now
                self.publisher.publish(msg)

    def destroy_node(self):
        """Clean up resources"""
        self.running = False
        if self.audio_thread:
            self.audio_thread.join(timeout=2.0)
        if self.stream:
            self.stream.stop()
        super().destroy_node()


def main(args=None):
    parser = argparse.ArgumentParser(
        description="Publish microphone audio as foxglove_msgs/RawAudio"
    )
    parser.add_argument(
        "--namespace",
        default="",
        help="Namespace prefix for the audio topic "
             "(e.g. robot1 -> /robot1/audio/raw)",
    )

    cli_args, ros_args = parser.parse_known_args(args)    
    
    rclpy.init(args=args)
    
    try:
        node = SoundDevicePublisher(namespace=cli_args.namespace)
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
