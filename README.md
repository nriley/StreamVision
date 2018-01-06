StreamVision
============

Short version: I use and maintain this, but it's unlikely to be useful as is to others.

What does it do?
----------------
StreamVision displays what’s playing in your audio player and lets you control the audio player from the keyboard.  It works with iTunes, the [Spotify desktop app](http://spotify.com/us/download/mac/) and the [Hermes](http://hermesapp.org/) Pandora client.  It includes special support for the [Radio Paradise](http://www.radioparadise.com/) stream.

There's also some code in there that turns my stereo on and off with AirPlay, but that should only try to do anything if you have [XTension](http://www.machomeautomation.com/) installed.

If nothing else, it provides a reference for obtaining album artwork and track information from iTunes.

Keyboard shortcuts
------------------
 - F8: display track info
 - ⌘F8: go to currently playing Internet radio stream’s URL (or Radio Paradise song page), show current song in iTunes, or bring Hermes/Spotify to the front if they’re playing
 - ⇧F8: look up currently playing Internet radio song on Apple Music (this has a lot of dependencies; see below)
 - F9: play/pause
 - F11: previous track
 - F12: next track (or skip track in Hermes)
 - ⇧F11: decrement star rating
 - ⇧F12: increment star rating
 - ⌘F11: decrease audio player volume
 - ⌘F12: increase audio player volume

Requirements
------------
 - macOS (currently tested on 10.10.5 and 10.11.5 with py2app, and on 10.12.6 and 10.13.2 with PyInstaller)
 - Growl (macOS’s notification system is insufficiently flexible for what I’m doing)
 - iTunes, Hermes and/or Spotify

Building it
-----------
StreamVision is written in Python 2 with a couple of small C extensions.  I use it with macOS's built-in Python, and have not tested it with other Python installations (which may not contain all the packages upon which StreamVision relies).

I'd recommend you create a [virtualenv](https://virtualenv.pypa.io/) to isolate StreamVision's build from your Python installation.

```shell
% cd StreamVision
% virtualenv . --system-site-packages
% source bin/activate
```

You will also need to install [`py-appscript`](http://appscript.sourceforge.net/py-appscript/install.html):

```shell
(StreamVision) % pip install appscript
```

Ideally I should either include [httplib2](https://github.com/jcgregorio/httplib2) as a submodule or a dependency (patches welcome), but for the moment...

```shell
% git clone https://github.com/jcgregorio/httplib2 httplib2-src
% ln -s httplib2-src/python2/httplib2
```

Building with PyInstaller (10.12+)
----------------------------------
Clone PyInstaller from Git, build an i386 (32-bit) bootloader and install PyInstaller:

```shell
(StreamVision) % mkdir src
(StreamVision) % cd src
(StreamVision) % git clone https://github.com/pyinstaller/pyinstaller
(StreamVision) % cd pyinstaller/bootloader
(StreamVision) % arch -i386 python ./waf distclean all --target-arch=32bit
(StreamVision) % cd ..
(StreamVision) % arch -i386 pip install -e .
```

Then build the extension modules and StreamVision itself:
```shell
(StreamVision) % python setup.py build
(StreamVision) % arch -i386 pyinstaller StreamVision.spec
```
The application should build as `dist/StreamVision.app`, though without Apple Music support.

After you run StreamVision once, you can configure its display style in the Growl app.  I have mine set to “Music Video”, 85% opacity, normal size, duration 2 seconds.

If you really want Apple Music support
--------------------------------------
Install a current OpenSSL *including 32-bit support* (I use MacPorts — `sudo port install openssl +universal`).

Install `cryptography` from Git linking against your built OpenSSL — with MacPorts, like this:
```shell
(StreamVision) % CPPFLAGS='-I/opt/local/include' LDFLAGS='-L/opt/local/lib' \
                pip install git+https://github.com/pyca/cryptography#egg=cryptography
```

Get [a MusicKit private key](https://developer.apple.com/library/content/documentation/NetworkingInternetWeb/Conceptual/AppleMusicWebServicesReference/SetUpWebServices.html), put it in a file and update the filename in and `kid`/`iss` in `StreamVision.spec` and `applemusic.py`.

To test that your MusicKit private key is set up properly, use `applemusic.py` — its command line arguments form a search term:
```shell
(StreamVision) % python applemusic.py lera lynn the only thing worth fighting for
{u'Lera Lynn - The Only Thing Worth Fighting For (From the HBO Series "True Detective") - Single - 1 The Only Thing Worth Fighting For (From the HBO Series "True Detective") (2015-07-07)': u'https://itunes.apple.com/us/album/only-thing-worth-fighting-for-from-hbo-series-true/id1015686735?i=1015686740',
 u'Lera Lynn - True Detective (Music from the HBO Series) - 2 The Only Thing Worth Fighting For (2015-07-07)': u'https://itunes.apple.com/us/album/the-only-thing-worth-fighting-for/id1005912517?i=1005913310'}
```

Assuming everything works, rebuild with `pyinstaller` as above and you should have an Apple Music-enabled version of StreamVision.

Building with py2app (10.10 or 10.11)
-------------------------------------
StreamVision uses [py2app](https://pythonhosted.org/py2app/); unfortunately py2app has not kept pace with OS development.  In OS X 10.11, the bundled version of py2app does not work because of a conflict with [System Integrity Protection](https://developer.apple.com/library/mac/documentation/Security/Conceptual/System_Integrity_Protection_Guide/Introduction/Introduction.html) (SIP, also known as "rootless").  You can disable SIP while building StreamVision, or install your own version of py2app which will not have this restriction.  Instructions for both options are in [this Stack Overflow question](http://stackoverflow.com/questions/33197412/py2app-operation-not-permitted).

Then you're ready to build:

```shell
% source bin/activate
(StreamVision) % python setup.py py2app
```

The application will be built in the `dist` folder.  After you run StreamVision once, you can configure its display style in the Growl app.  I have it set to “Music Video”, 85% opacity, normal size, duration 2 seconds.

If you run into errors with the above (likely on 10.11 if you've installed your own py2app), you likely have encountered a twisty mess of py2app code rot as its dependencies have been updated and it hasn't kept pace.  Building with `-A` (as below) is a workaround that won't let you distribute StreamVision, but at least you can run it for yourself.

Running it in development
-------------------------
```shell
(StreamVision) % python setup.py py2app -A
(StreamVision) % arch -i386 dist/StreamVision.app/Contents/MacOS/StreamVision
```
Unfortunately `^C` doesn't work to stop it; you either have to use `^\` (and deal with the crash report) or kill it from elsewhere.

`py2app -A` uses aliases, so you can modify `StreamVision.py` and test your changes without rebuilding.
