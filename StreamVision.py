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
    # XXX better to use http://www2.radioparadise.com/playlist.xml ?
    session = scrape.Session()
    session.go('http://www2.radioparadise.com/nowplay_b.php')
    return session.region.firsttag('a')['href']

def cleanStreamTitle(title):
    if title == k.missing_value:
        return ''
    title = title.split(' [')[0] # XXX move to description
    title = title.encode('iso-8859-1').decode('utf-8') # XXX iTunes 7.1 or RP?
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

        trackClass = iTunes.current_track.class_()
        trackName = ''
        if trackClass != k.property:
            trackName = iTunes.current_track.name()

        if iTunes.player_state() != k.playing:
            growlNotify('iTunes is not playing.', trackName)
            return
        if trackClass == k.URL_track:
            growlNotify(cleanStreamTitle(iTunes.current_stream_title()),
                        cleanStreamTrackName(trackName))
            return
        if trackClass == k.property:
           growlNotify('iTunes is playing.', '')
           return
        kw = {}
        # XXX iTunes doesn't let you get artwork for shared tracks
        if trackClass != k.shared_track:
            artwork = iTunes.current_track.artworks()
            if artwork:
                kw['pictImage'] = artwork[0].data()
        growlNotify(trackName + '  ' +
                    u'★' * (iTunes.current_track.rating() / 20),
                    iTunes.current_track.album() + '\n' +
                    iTunes.current_track.artist(),
                    **kw)

    def goToSite(self):
        iTunes = iTunesApp()
        if iTunes.player_state() == k.playing:
            url = iTunes.current_stream_URL()
            if url != k.missing_value:
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
        rating = iTunes.current_track.rating()
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
        was_playing = (iTunes.player_state() == k.playing)
        iTunes.playpause()
        if not was_playing and iTunes.player_state() == k.stopped:
            # most likely, we're focused on the iPod, so playing does nothing
            iTunes.browser_windows[1].view.set(iTunes.user_playlists[its.name=='Stations'][1]())
            iTunes.play()
        if HAVE_XTENSION and useStereo:
            if iTunes.player_state() == k.playing:
                XTensionApp().turnon('Stereo')
            else:
                XTensionApp().turnoff('Stereo')

    def playPauseFront(self):
        systemEvents = app(id='com.apple.systemEvents')
        frontName = systemEvents.processes[its.frontmost][1].name()
	if frontName == 'RealPlayer':
	    realPlayer = app(id='com.RealNetworks.RealPlayer')
	    if len(realPlayer.players()) > 0:
		if realPlayer.players[1].state() == k.playing:
		    realPlayer.pause()
		else:
		    realPlayer.play()
		return
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
        # XXX detect if "enable access for assistive devices" needs to be enabled
        systemEvents = app(id='com.apple.systemEvents')
        frontName = systemEvents.processes[its.frontmost][1].name()
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
            systemEvents.processes[frontName].windows \
                [its.subrole == 'AXStandardWindow'].windows[1]. \
                buttons[its.subrole == 'AXZoomButton'].buttons[1].click()

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
            import HIDRemote
            HIDRemote.connect()
        except ImportError:
            print "failed to import HIDRemote (XXX fix - on Intel)"
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
