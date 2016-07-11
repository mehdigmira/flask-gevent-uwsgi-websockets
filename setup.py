"""
Flask-Gevent-uWSGI-Websockets
-------------

This is the description for that library
"""
from setuptools import setup


setup(
    name='Flask-Gevent-uWSGI-Websockets',
    version='0.1.1',
    url='',
    license='MIT',
    author='Mehdi GMIRA',
    author_email='mehdigmira@gmail.com',
    description='This library enables using high performance websockets on top of: flask, gevent, uwsgi. '
                'The library is designed so that only one websocket connection is opened per browser session.',
    long_description=__doc__,
    py_modules=['flask_gevent_uwsgi_websockets'],
    # if you would be using a package instead use packages instead
    # of py_modules:
    # packages=['flask_sqlite3'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'Flask',
        'gevent',
        'uwsgi'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    keywords='uwsgi flask gevent websockets'
)
