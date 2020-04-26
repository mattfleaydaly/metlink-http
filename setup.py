from pathlib import Path

import setuptools

setuptools.setup(
    name='metlinkpid-http',
    version='1.0.0',
    description='Modified HTTP server for Metlink PID',
    url='https://github.com/mattfleaydaly/metlink-http',
    author='Alex Peters',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    py_modules=['metlinkpid_http'],
    python_requires='~=3.6',
    install_requires=[
        'metlinkpid~=1.0.1',
        'flask~=1.0.2',
        'envopt~=0.2.0',
        'waitress~=1.3.0',
        'python-dateutil~=2.8.1',
        'requests~=2.22.0',
        'git-python~=1.0.3',
        'simpleaudio~=1.0.4'
    ],
    entry_points={
        'console_scripts': [
            'metlinkpid-http=metlinkpid_http:main',
        ],
    },
)
