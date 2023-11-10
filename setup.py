from setuptools import setup

setup(
    name='HiveMind-deltachat-bridge',
    version='0.0.2',
    packages=['deltachat_bridge'],
    url='https://github.com/JarbasHiveMind/HiveMind-deltachat-bridge',
    license='Apache-2.0',
    author='jarbasAI',
    author_email='jarbasai@mailfence.com',
    description='DeltaChat bridge for HiveMind',
    install_requires=["hivemind_bus_client", "click", "deltachat"],
    entry_points={
        'console_scripts': [
            'hm-deltachat-bridge=deltachat_bridge.__main__:launch_bot'
        ]
    }
)
