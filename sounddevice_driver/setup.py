from setuptools import find_packages, setup

package_name = 'sounddevice_driver'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools', 'numpy', 'sounddevice'],
    zip_safe=True,
    maintainer='Alexander Minor',
    maintainer_email='alexander@minor.pw',
    description='ROS 2 microphone capture driver using Python sounddevice.',
    license='Apache License 2.0',
    entry_points={
        'console_scripts': [
            'sounddevice_driver_node = sounddevice_driver.sounddevice_driver_node:main',
            'sounddevice_list_devices = sounddevice_driver.sounddevice_list_devices:main',
        ],
    },
)
