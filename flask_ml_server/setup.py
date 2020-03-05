"""
Flask-ML-Server
-------------

A Flask extension for running machine learning code on a server
"""
from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='flask-ml-server',
    version='0.0.1',
    url='https://github.com/UMass-Rescue',
    license='MIT',
    author='Jagath Jai Kumar',
    author_email='jagath.jaikumar@gmail.com',
    description="A Flask extension for running machine learning code",
    long_description="A Flask extension for running machine learning code",
    py_modules=['flask_ml_server'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask'
    ],
    python_requires=">= 3.6",
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)