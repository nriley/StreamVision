#!/usr/bin/pythonw
# -*- coding: utf-8 -*-

from appscript import app, k, its, CommandError
from AppKit import NSApplication, NSApplicationDefined, NSBeep, NSSystemDefined, NSURL, NSWorkspace
from Foundation import NSDistributedNotificationCenter
from PyObjCTools import AppHelper
from Carbon.CarbonEvt import RegisterEventHotKey, GetApplicationEventTarget
from Carbon.Events import cmdKey, shiftKey, controlKey
import struct
import scrape
import HIDRemote
import HotKey

GROWL_APP_NAME = 'StreamVision'
NOTIFICATION_TRACK_INFO = 'iTunes Track Info'
NOTIFICATIONS_ALL = [NOTIFICATION_TRACK_INFO]

kEventHotKeyPressedSubtype = 6
kEventHotKeyReleasedSubtype = 9

kHIDUsage_Csmr_ScanNextTrack = 0xB5
kHIDUsage_Csmr_ScanPreviousTrack = 0xB6
kHIDUsage_Csmr_PlayOrPause = 0xCD

growl = app('GrowlHelperApp')

growl.register(
    as_application=GROWL_APP_NAME,
    all_notifications=NOTIFICATIONS_ALL,
    default_notifications=NOTIFICATIONS_ALL,
    icon_of_application='iTunes.app')
    # if we leave off the .app, we can get Classic iTunes's icon

def growlNotify(title, description, **kw):
    growl.notify(
        with_name=NOTIFICATION_TRACK_INFO,
        title=title,
        description=description,
        application_name=GROWL_APP_NAME,
        **kw)

def radioParadiseURL():
    session = scrape.Session()
    session.go('http://www2.radioparadise.com/nowplay_b.php')
    return session.region.firsttag('a')['href']

def cleanStreamTitle(title):
    if title == k.MissingValue:
        return ''
    title = title.split(' [')[0] # XXX move to description
    title = title.replace('`', u'’')
    return title

def cleanStreamTrackName(name):
    name = name.split('. ')[0]
    name = name.split(': ')[0]
    name = name.split(' - ')
    if len(name) > 1:
        name = ' - '.join(name[:-1])
    else:
        name = name[0]
    return name

def iTunesApp(): return app(id='com.apple.iTunes')
def XTensionApp(): return app(creator='SHEx')

HAVE_XTENSION = False
try:
    XTensionApp()
    HAVE_XTENSION = True
except:
    pass

class StreamVision(NSApplication):

    hotKeyActions = {}
    hotKeys = []

    def displayTrackInfo(self):
        iTunes = iTunesApp()

        trackClass = iTunes.current_track.class_.get()
        trackName = ''
        if trackClass != k.Property:
            trackName = iTunes.current_track.name.get()

        if iTunes.player_state.get() != k.playing:
            growlNotify('iTunes is not playing.', trackName)
            return
        if trackClass == k.URL_track:
            growlNotify(cleanStreamTitle(iTunes.current_stream_title.get()),
                        cleanStreamTrackName(trackName))
            return
        if trackClass == k.Property:
           growlNotify('iTunes is playing.', '')
           return
        kw = {}
        # XXX iTunes doesn't let you get artwork for shared tracks
        if trackClass != k.shared_track:
            artwork = iTunes.current_track.artworks.get()
            if artwork:
                kw['pictImage'] = artwork[0].data.get()
        growlNotify(trackName + '  ' +
                    '★' * (iTunes.current_track.rating.get() / 20),
                    iTunes.current_track.album.get() + "\n" +
                    iTunes.current_track.artist.get(),
                    **kw)

    def goToSite(self):
        iTunes = iTunesApp()
        if iTunes.player_state.get() == k.playing:
            url = iTunes.current_stream_URL.get()
            if url:
                if 'radioparadise.com' in url and 'review' not in url:
                    url = radioParadiseURL()
                NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))
                return
        NSBeep()

    def registerHotKey(self, func, keyCode, mods=0):
        hotKeyRef = RegisterEventHotKey(keyCode, mods, (0, 0),
                                        GetApplicationEventTarget(), 0)
        self.hotKeys.append(hotKeyRef)
        self.hotKeyActions[HotKey.HotKeyAddress(hotKeyRef)] = func
        return hotKeyRef

    def unregisterHotKey(self, hotKeyRef):
        self.hotKeys.remove(hotKeyRef)
        del self.hotKeyActions[HotKey.HotKeyAddress(hotKeyRef)]
        hotKeyRef.UnregisterEventHotKey()

    def incrementRatingBy(self, increment):
        iTunes = iTunesApp()
        rating = iTunes.current_track.rating.get()
        rating += increment
        if rating < 0:
            rating = 0
            NSBeep()
        elif rating > 100:
            rating = 100
            NSBeep()
        iTunes.current_track.rating.set(rating)

    def playPause(self, useStereo=True):
        iTunes = iTunesApp()
        was_playing = (iTunes.player_state.get() == k.playing)
        iTunes.playpause()
        if not was_playing and iTunes.player_state.get() == k.stopped:
            # most likely, we're focused on the iPod, so playing does nothing
            iTunes.browser_windows[1].view.set(iTunes.user_playlists.filter(its.name=='Stations')[1].get())
            iTunes.play()
        if HAVE_XTENSION and useStereo:
            if iTunes.player_state.get() == k.playing:
                XTensionApp().turnon('Stereo')
            else:
                XTensionApp().turnoff('Stereo')

    def playPauseFront(self):
        systemEvents = app(id='com.apple.systemEvents')
        frontName = systemEvents.processes.filter(its.frontmost)[1].name()
	if frontName == 'RealPlayer':
	    realPlayer = app(id='com.RealNetworks.RealPlayer')
	    if realPlayer.players[0].state.get() == k.playing:
		realPlayer.pause()
	    else:
		realPlayer.play()
	elif frontName == 'VLC':
	    app(id='org.videolan.vlc').play() # equivalent to playpause
	else:
	    self.playPause(useStereo=False)	

    def registerZoomWindowHotKey(self):
        self.zoomWindowHotKey = self.registerHotKey(self.zoomWindow, 42, cmdKey | controlKey) # cmd-ctrl-\

    def unregisterZoomWindowHotKey(self):
        self.unregisterHotKey(self.zoomWindowHotKey)
        self.zoomWindowHotKey = None

    def zoomWindow(self):
        systemEvents = app(id='com.apple.systemEvents')
        frontName = systemEvents.processes.filter(its.frontmost)[1].name()
        if frontName == 'iTunes':
            systemEvents.processes['iTunes'].menu_bars[1]. \
                menu_bar_items['Window'].menus.menu_items['Zoom'].click()
            return
        elif frontName in ('X11', 'Emacs'): # preserve C-M-\
            self.unregisterZoomWindowHotKey()
            systemEvents.key_code(42, using=[k.command_down, k.control_down])
            self.registerZoomWindowHotKey()
            return
        try:
            zoomed = app(frontName).windows[1].zoomed
            zoomed.set(not zoomed())
        except (CommandError, RuntimeError):
            systemEvents.processes[frontName].windows. \
                filter(its.subrole == 'AXStandardWindow').windows[1]. \
                buttons.filter(its.subrole == 'AXZoomButton').buttons[1].click()

    def finishLaunching(self):
        super(StreamVision, self).finishLaunching()
        self.registerHotKey(self.displayTrackInfo, 100) # F8
        self.registerHotKey(self.goToSite, 100, cmdKey) # cmd-F8
        self.registerHotKey(self.playPause, 101) # F9
        self.registerHotKey(lambda: iTunesApp().previous_track(), 109) # F10
        self.registerHotKey(lambda: iTunesApp().next_track(), 103) # F11
        self.registerHotKey(lambda: self.incrementRatingBy(-20), 109, shiftKey) # shift-F10
        self.registerHotKey(lambda: self.incrementRatingBy(20), 103, shiftKey) # shift-F11
        self.registerZoomWindowHotKey()
        NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(self, self.displayTrackInfo, 'com.apple.iTunes.playerInfo', None)
        try:
            HIDRemote.connect()
        except OSError, e:
            print "failed to connect to remote: ", e

    def sendEvent_(self, theEvent):
        eventType = theEvent.type()
        if eventType == NSSystemDefined and \
               theEvent.subtype() == kEventHotKeyPressedSubtype:
            self.hotKeyActions[theEvent.data1()]()
        elif eventType == NSApplicationDefined:
            key = theEvent.data1()
            if key == kHIDUsage_Csmr_ScanNextTrack:
                iTunesApp().next_track()
            elif key == kHIDUsage_Csmr_ScanPreviousTrack:
                iTunesApp().previous_track()
            elif key == kHIDUsage_Csmr_PlayOrPause:
                self.playPauseFront()
        super(StreamVision, self).sendEvent_(theEvent)

if __name__ == "__main__":
    AppHelper.runEventLoop()
    HIDRemote.disconnect() # XXX do we get here?
