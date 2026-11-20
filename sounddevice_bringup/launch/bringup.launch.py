from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def launch_setup(context):
    config = context.launch_configurations
    print('\nStarting sounddevice driver with parameters:')
    for name in ('log_level', 'ns', 'device', 'samplerate', 'blocksize', 'channels',
                 'audio_topic'):
        value = config[name]
        if name == 'ns':
            value = '/' + value.strip('/')
        elif name == 'device' and not value:
            value = '(system default)'
        print(f' {name}: {value}')
    print('')

    return [
        Node(
            package='sounddevice_driver',
            executable='sounddevice_driver_node',
            namespace=config['ns'],
            parameters=[{
                'device': ParameterValue(config['device'], value_type=str),
                'samplerate': int(config['samplerate']),
                'blocksize': int(config['blocksize']),
                'channels': int(config['channels']),
                'audio_topic': ParameterValue(config['audio_topic'], value_type=str),
            }],
            arguments=['--ros-args', '--log-level', config['log_level']],
            output='screen',
        ),
    ]


def generate_launch_description():
    declared_arguments = [
        DeclareLaunchArgument(
            'log_level', default_value='error',
            description='Logging level for the driver',
            choices=['info', 'debug', 'error', 'warn'],
        ),
        DeclareLaunchArgument(
            'ns', default_value='', description='Namespace for the node and topics',
        ),
        DeclareLaunchArgument(
            'device', default_value='',
            description='Input device index or name substring; empty uses the system default',
        ),
        DeclareLaunchArgument(
            'samplerate', default_value='44100', description='Capture sample rate in Hz',
        ),
        DeclareLaunchArgument(
            'blocksize', default_value='4096', description='Samples per channel per captured block',
        ),
        DeclareLaunchArgument(
            'channels', default_value='4', description='Number of input channels',
        ),
        DeclareLaunchArgument(
            'audio_topic', default_value='audio/raw', description='RawAudio output topic name',
        ),
    ]
    return LaunchDescription(declared_arguments + [OpaqueFunction(function=launch_setup)])
