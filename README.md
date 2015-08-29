StreamVision
============

Short version: I use and maintain this, but it's unlikely to be useful as is to others.

What does it do?
----------------
StreamVision displays what’s playing in your audio player and lets you control the audio player from the keyboard.  It works with iTunes, the Rdio desktop app and the Hermes Pandora client.  It includes special support for the Radio Paradise stream.

There's also some code in there that turns my stereo on and off with AirPlay, but that should only try to do anything if you have XTension installed.

If nothing else, it can provide a reference on how to get album artwork and track information out of iTunes.

Keyboard shortcuts
------------------
 - F8: display track info
 - ⌘F8: go to currently playing Internet radio stream’s URL (or Radio Paradise song page), show current song in iTunes, or bring Rdio/Hermes to the front if they’re playing
 - F9: play/pause
 - F11: previous track
 - F12: next track (or skip track in Hermes)
 - ⇧F11: decrement star rating
 - ⇧F12: increment star rating
 - ⌘F11: decrease audio player volume
 - ⌘F12: increase audio player volume

Requirements
------------
 - OS X (currently tested on 10.10.5)
 - Growl (OS X’s notification system is insufficiently flexible for what I’m doing)
 - iTunes, Hermes or Rdio

Building it
-----------
Ideally I should either include httplib2 as a submodule or a dependency (patches welcome), but for the moment...
```shell
% cd StreamVision
% git clone https://github.com/jcgregorio/httplib2 httplib2-src
% ln -s httplib2-src/python2/httplib2
% python setup.py py2app
```

Once you run it once, you can configure the display style in the Growl app.  I have it set to “Music Video”, 40% opacity, normal size, duration 2 seconds.

Running it in development
-------------------------
```shell
% python setup.py py2app -A
% arch -i386 dist/StreamVision.app/Contents/MacOS/StreamVision
```
Unfortunately `^C` doesn't work to stop it; you either have to use `^\` (and deal with the crash report) or kill it from elsewhere.

`py2app -A` uses aliases, so you can modify StreamVision.py and only have to rerun it without rebuilding.
