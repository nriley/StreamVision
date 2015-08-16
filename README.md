StreamVision
============

I use and maintain this, but it's unlikely to be useful as is to
others.

What is it?
-----------
Displays what you're playing in your audio player and lets you control the audio player from the keyboard.  It includes special support for the Radio Paradise stream.  There's also some code in there that turns my stereo on and off with AirPlay, but that should only try to do anything if you have XTension installed.

If nothing else, I've had to update it countless times for changes to iTunes and its scripting interface.

Commands
--------
 - F8: display track info
 - ⌘F8: go to currently playing Internet radio stream’s URL (or Radio Paradise song page)
 - F9: play/pause
 - F11: previous track
 - F12: next track
 - ⇧F11: decrement star rating
 - ⇧F12: increment star rating
 - ⌘F11: decrease iTunes volume
 - ⌘F12: increase iTunes volume

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

Once you run it once and it displays a notification, you can configure it in the Growl app.  I have the Display Style set to “Music Video”, 40% opacity, normal size, duration 2 seconds.

Running it in development
-------------------------
```shell
% python setup.py py2app -A
% arch -i386 dist/StreamVision.app/Contents/MacOS/StreamVision
```
Unfortunately `^C` doesn't work to kill it; you either have to use `^\` (and deal with the crash report) or kill it from elsewhere.

`py2app -A` uses aliases, so you can modify StreamVision.py and only have to rerun it without rebuilding.
