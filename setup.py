"""
Usage:
    python setup.py py2app
"""
from distutils.core import setup
from setuptools.extension import Extension
import py2app

plist = dict(
    CFBundleIdentifier='net.sabi.StreamVision',
    CFBundleName='StreamVision',
    NSPrincipalClass='StreamVision',
    LSUIElement=1,
)

setup(
    app=["StreamVision.py"],
    ext_modules=[Extension('AudioDevice',
                           sources=['AudioDevicemodule.c'],
                           extra_link_args=['-framework', 'AudioToolbox'])],
    data_files=["English.lproj"],
    options=dict(py2app=dict(
        plist=plist,
        site_packages=True,
        resources=['AuthKey_8937YX2XGP.p8'])),
)
