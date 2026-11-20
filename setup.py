from setuptools import setup, find_packages

package_name = 'sounddevice_ros'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='your_email@example.com',
    description='ROS2 sounddevice package',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'sounddevice_subscriber = sounddevice_ros.sounddevice_ros_subscriber_node:main',
            'sounddevice_publisher = sounddevice_ros.sounddevice_ros_publisher_node:main',
        ],
    },
)