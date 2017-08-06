#!/bin/zsh -f

# https://bitbucket.org/ronaldoussoren/py2app/issues/233/auxiliary-modules-no-longer-being-included

source bin/activate
set -e

python setup.py py2app
cp build/bdist.macosx-10.12-intel/lib.macosx-10.12-intel-2.7/*.so dist/StreamVision.app/Contents/Resources/lib/python2.7/lib-dynload
cp scrape.py dist/StreamVision.app/Contents/Resources/lib/python2.7
cp -RL httplib2 dist/StreamVision.app/Contents/Resources/lib/python2.7
