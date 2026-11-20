#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray
import sounddevice as sd
import numpy as np
import threading


class SoundDeviceSubscriber(Node):
    """ROS2 node for playing audio data from sounddevice"""

    def __init__(self):
        super().__init__('sounddevice_subscriber')
        
        # Declare parameters
        self.declare_parameter('device', None)
        self.declare_parameter('samplerate', 44100)
        self.declare_parameter('channels', 1)
        self.declare_parameter('dtype', 'float32')
        
        # Get parameters
        self.device = self.get_parameter('device').value
        self.samplerate = self.get_parameter('samplerate').value
        self.channels = self.get_parameter('channels').value
        self.dtype = self.get_parameter('dtype').value
        
        # Create subscriber
        self.subscription = self.create_subscription(
            Float32MultiArray,
            'audio',
            self._audio_callback,
            10
        )
        self.subscription  # prevent unused variable warning
        
        # Audio stream and synchronization
        self.stream = None
        self.audio_queue = []
        self.lock = threading.Lock()
        self.running = True
        
        self.get_logger().info(f'Starting sounddevice subscriber on device {self.device}')
        self.get_logger().info(f'Sample rate: {self.samplerate}, Channels: {self.channels}')
        
        # Start audio playback stream in separate thread
        self.audio_thread = threading.Thread(target=self._audio_stream_thread, daemon=True)
        self.audio_thread.start()

    def _audio_callback(self, msg):
        """Callback for audio messages"""
        try:
            # Convert message data to numpy array
            audio_data = np.array(msg.data, dtype=np.float32)
            
            # Reshape based on layout information if available
            if msg.layout.dim:
                shape = tuple(dim.size for dim in msg.layout.dim)
                audio_data = audio_data.reshape(shape)
            else:
                # Default reshape to (samples, channels)
                audio_data = audio_data.reshape(-1, self.channels)
            
            with self.lock:
                self.audio_queue.append(audio_data)
                
        except Exception as e:
            self.get_logger().error(f'Error processing audio message: {e}')

    def _audio_stream_thread(self):
        """Run audio output stream in separate thread"""
        try:
            def audio_callback(outdata, frames, time, status):
                if status:
                    self.get_logger().warn(f'Audio status: {status}')
                
                with self.lock:
                    if self.audio_queue:
                        audio_data = self.audio_queue.pop(0)
                        # Ensure correct shape and size
                        if audio_data.shape[0] >= frames:
                            outdata[:] = audio_data[:frames]
                        else:
                            # Pad with zeros if not enough data
                            outdata[:audio_data.shape[0]] = audio_data
                            outdata[audio_data.shape[0]:] = 0
                    else:
                        # No data available, output silence
                        outdata.fill(0)

            self.stream = sd.OutputStream(
                device=self.device,
                samplerate=self.samplerate,
                channels=self.channels,
                dtype=self.dtype,
                callback=audio_callback
            )
            self.stream.start()
            
            while self.running:
                sd.sleep(100)
                
        except Exception as e:
            self.get_logger().error(f'Audio stream error: {e}')
        finally:
            if self.stream:
                self.stream.stop()
                self.stream.close()

    def destroy_node(self):
        """Clean up resources"""
        self.running = False
        if self.audio_thread:
            self.audio_thread.join(timeout=2.0)
        if self.stream:
            self.stream.stop()
            self.stream.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    
    try:
        node = SoundDeviceSubscriber()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()