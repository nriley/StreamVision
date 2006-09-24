"""
Script for building the example.

Usage:
    python setup.py py2app
"""
from distutils.core import setup, Extension
import py2app

plist = dict(
    CFBundleIdentifier='net.sabi.StreamVision',
    CFBundleName='StreamVision',
    NSPrincipalClass='StreamVision',
    LSUIElement=1,
)

setup(
    app=["StreamVision.py"],
    ext_modules=[Extension('HotKey',
                           sources=['HotKeymodule.c'],
                           extra_link_args=['-framework', 'Carbon']),
                 Extension('HIDRemote',
                           sources=['HIDRemotemodule.m'],
                           extra_link_args=['-framework', 'Cocoa',
                                            '-framework', 'IOKit',
                                            'libHIDUtilities.a'])],
    data_files=["English.lproj"],
    options=dict(py2app=dict(plist=plist)),
)
