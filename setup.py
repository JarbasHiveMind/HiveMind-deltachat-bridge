from setuptools import setup

setup(
    name='HiveMind-deltachat-bridge',
    version='0.0.1',
    packages=['deltachat_bridge'],
    url='https://github.com/JarbasHiveMind/HiveMind-deltachat-bridge',
    license='Apache-2.0',
    author='jarbasAI',
    author_email='jarbasai@mailfence.com',
    description='Mycroft DeltaChat bridge for the HiveMind',
    install_requires=["jarbas_hive_mind>=0.10.7", "deltachat"],
    entry_points={
        'console_scripts': [
            'HiveMind-deltachat-bridge=deltachat_bridge.__main__:main'
        ]
    }
)
