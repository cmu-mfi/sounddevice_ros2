#!/usr/bin/env python3
"""Lossless microphone -> foxglove_msgs/RawAudio publisher.

Fixes relative to sounddevice_ros_publisher_node.py:
  1. Every captured block is published exactly once (queue between the PortAudio callback and ROS),
     instead of a timer re-sending whichever block happened to be latest (old node: ~1/3 coverage,
     65% duplicate messages at 20 Hz).
  2. msg.timestamp = time the first sample of the block hit the ADC (PortAudio input latency
     subtracted), not the publish time (old node: stamps ~100 ms late).
  3. No logging inside the audio callback (a slow callback causes input overflow); overflows are
     counted and reported once a second from the ROS thread.
Same CLI and parameters as before; `publish_rate` is kept for compatibility but no longer matters.
"""
import argparse, queue, threading, time as pytime
import numpy as np
import rclpy
from rclpy.node import Node
from foxglove_msgs.msg import RawAudio
import sounddevice as sd


class SoundDevicePublisher(Node):
    def __init__(self, namespace=""):
        super().__init__('sounddevice_publisher')
        self.declare_parameter('device', None)
        self.declare_parameter('samplerate', 44100)
        self.declare_parameter('blocksize', 4096)
        self.declare_parameter('channels', 4)
        self.declare_parameter('dtype', 'int16')
        self.declare_parameter('publish_rate', 20)          # ignored: one message per captured block
        self.device = self.get_parameter('device').value
        self.samplerate = int(self.get_parameter('samplerate').value)
        self.blocksize = int(self.get_parameter('blocksize').value)
        self.channels = int(self.get_parameter('channels').value)
        self.publisher = self.create_publisher(RawAudio, namespace.strip('/') + '/audio/raw', 50)
        self.q = queue.SimpleQueue()                        # (ros_stamp_ns, int16 block)
        self.n_captured = self.n_published = self.n_overflow = 0
        self.last_report = pytime.monotonic()
        self.running = True
        self.get_logger().info(f'device={self.device} samplerate={self.samplerate} blocksize={self.blocksize} '
                               f'channels={self.channels} -> {self.samplerate / self.blocksize:.1f} msgs/s expected, pcm-s16')
        self.audio_thread = threading.Thread(target=self._audio_stream_thread, daemon=True)
        self.audio_thread.start()
        # drain the queue well above the block rate; every queued block is published, none skipped
        self.timer = self.create_timer(0.5 * self.blocksize / self.samplerate, self._drain)

    def _audio_stream_thread(self):
        def audio_callback(indata, frames, t, status):
            # keep this tiny: no logging, no ROS calls
            if status:
                self.n_overflow += 1
            ros_now = self.get_clock().now().nanoseconds
            # time.currentTime - time.inputBufferAdcTime = how long ago the first sample of this block was captured
            lat = (t.currentTime - t.inputBufferAdcTime) if (t.currentTime and t.inputBufferAdcTime) else frames / self.samplerate
            self.q.put((ros_now - int(lat * 1e9), np.ascontiguousarray(indata, dtype=np.int16).copy()))
            self.n_captured += 1
        try:
            with sd.InputStream(device=self.device, samplerate=self.samplerate, blocksize=self.blocksize,
                                channels=self.channels, dtype='int16', callback=audio_callback):
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
            self.get_logger().info(f'{self.n_captured / dt:.1f} blocks/s captured, {self.n_published / dt:.1f} published, '
                                   f'{self.n_overflow} overflow events, queue {self.q.qsize()}')
            if self.n_overflow:
                self.get_logger().warn('input overflow: the sound card dropped samples; lower the load or raise blocksize')
            self.n_captured = self.n_published = self.n_overflow = 0
            self.last_report = now

    def destroy_node(self):
        self.running = False
        self.audio_thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    parser = argparse.ArgumentParser(description="Publish microphone audio as foxglove_msgs/RawAudio (lossless)")
    parser.add_argument("--namespace", default="", help="e.g. bed_side_audio -> /bed_side_audio/audio/raw")
    cli_args, _ = parser.parse_known_args(args)
    rclpy.init(args=args)
    node = SoundDevicePublisher(namespace=cli_args.namespace)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
