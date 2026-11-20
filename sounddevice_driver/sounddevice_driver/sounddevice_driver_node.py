#!/usr/bin/env python3
"""Publish every captured audio block with its ADC-adjusted timestamp."""

import queue
import threading
import time as pytime

from foxglove_msgs.msg import RawAudio
import numpy as np
import rclpy
from rcl_interfaces.msg import ParameterDescriptor
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
import sounddevice as sd


class SoundDeviceDriver(Node):
    def __init__(self):
        super().__init__('sounddevice_driver')
        self.declare_parameter(
            'device', '', ParameterDescriptor(dynamic_typing=True, read_only=True),
        )
        for name, default in (
            ('samplerate', 44100), ('blocksize', 4096), ('channels', 4),
            ('audio_topic', 'audio/raw'),
        ):
            self.declare_parameter(name, default, ParameterDescriptor(read_only=True))

        device = self.get_parameter('device').value
        if not isinstance(device, (str, int)) or isinstance(device, bool):
            raise ValueError('device must be an input device index or name substring')
        if isinstance(device, str):
            device = device.strip()
            if device:
                try:
                    device = int(device)
                except ValueError:
                    pass
            else:
                device = None
        self.device = device
        self.samplerate = self.get_parameter('samplerate').value
        self.blocksize = self.get_parameter('blocksize').value
        self.channels = self.get_parameter('channels').value
        for name in ('samplerate', 'blocksize', 'channels'):
            if getattr(self, name) <= 0:
                raise ValueError(f'{name} must be positive')

        audio_topic = self.get_parameter('audio_topic').value
        self.publisher = self.create_publisher(RawAudio, audio_topic, 50)
        self.q = queue.SimpleQueue()  # (ros_stamp_ns, int16 block)
        self.n_captured = self.n_published = self.n_overflow = 0
        self.last_report = pytime.monotonic()
        self.running = True
        self.get_logger().info(
            f'device={self.device} samplerate={self.samplerate} blocksize={self.blocksize} '
            f'channels={self.channels} -> {self.samplerate / self.blocksize:.1f} msgs/s, '
            f'pcm-s16 on {self.publisher.topic_name}'
        )
        # Drain above the block rate; each queued block is published once.
        self.timer = self.create_timer(0.5 * self.blocksize / self.samplerate, self._drain)
        self.audio_thread = threading.Thread(target=self._audio_stream_thread, daemon=True)
        self.audio_thread.start()

    def _audio_stream_thread(self):
        def audio_callback(indata, frames, t, status):
            # Keep this tiny; report stream status from the ROS thread instead.
            if status:
                self.n_overflow += 1
            ros_now = self.get_clock().now().nanoseconds
            # PortAudio gives the age of the first sample in this block.
            lat = (
                t.currentTime - t.inputBufferAdcTime
                if t.currentTime and t.inputBufferAdcTime else frames / self.samplerate
            )
            self.q.put((
                ros_now - int(lat * 1e9),
                np.ascontiguousarray(indata, dtype='<i2').copy(),
            ))
            self.n_captured += 1
        try:
            with sd.InputStream(
                device=self.device, samplerate=self.samplerate, blocksize=self.blocksize,
                channels=self.channels, dtype='int16', callback=audio_callback,
            ):
                while self.running:
                    sd.sleep(200)
        except Exception as e:
            self.get_logger().error(f'Audio stream error: {e}')

    def _drain(self):
        while True:
            try:
                stamp_ns, block = self.q.get_nowait()
            except queue.Empty:
                break
            msg = RawAudio()
            msg.data = block.tobytes()
            msg.format = 'pcm-s16'
            msg.sample_rate = self.samplerate
            msg.number_of_channels = self.channels
            msg.timestamp.sec = stamp_ns // 1_000_000_000
            msg.timestamp.nanosec = stamp_ns % 1_000_000_000
            self.publisher.publish(msg)
            self.n_published += 1
        now = pytime.monotonic()
        if now - self.last_report >= 5.0:
            dt = now - self.last_report
            self.get_logger().info(
                f'{self.n_captured / dt:.1f} blocks/s captured, '
                f'{self.n_published / dt:.1f} published, '
                f'{self.n_overflow} overflow events, queue {self.q.qsize()}'
            )
            if self.n_overflow:
                self.get_logger().warn(
                    'input overflow: the sound card dropped samples; '
                    'lower the load or raise blocksize'
                )
            self.n_captured = self.n_published = self.n_overflow = 0
            self.last_report = now

    def destroy_node(self):
        self.running = False
        self.audio_thread.join(timeout=2.0)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = SoundDeviceDriver()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
