#!/usr/bin/pythonw
# -*- coding: utf-8 -*-

from appscript import app, k, its, CommandError
from AppKit import NSApplication, NSApplicationDefined, NSBeep, NSSystemDefined, NSURL, NSWorkspace
from Foundation import NSDistributedNotificationCenter, NSSearchPathForDirectoriesInDomains, NSCachesDirectory, NSUserDomainMask
from PyObjCTools import AppHelper
from Carbon.CarbonEvt import RegisterEventHotKey, GetApplicationEventTarget
from Carbon.Events import cmdKey, shiftKey, controlKey
from AudioDevice import default_output_device_is_airplay, set_default_output_device_changed_callback
import httplib2
import os
import struct
import scrape
import HotKey
import tunes # <https://github.com/abarnert/itunesterms>

GROWL_APP_NAME = 'StreamVision'
NOTIFICATION_TRACK_INFO = 'iTunes Track Info'
NOTIFICATIONS_ALL = [NOTIFICATION_TRACK_INFO]

kEventHotKeyPressedSubtype = 6
kEventHotKeyReleasedSubtype = 9

kHIDUsage_Csmr_ScanNextTrack = 0xB5
kHIDUsage_Csmr_ScanPreviousTrack = 0xB6
kHIDUsage_Csmr_PlayOrPause = 0xCD

def growlRegister():
    global growl
    growl = app(id='com.Growl.GrowlHelperApp')

    growl.register(
        as_application=GROWL_APP_NAME,
        all_notifications=NOTIFICATIONS_ALL,
        default_notifications=NOTIFICATIONS_ALL,
        icon_of_application='iTunes.app')
        # if we leave off the .app, we can get Classic iTunes's icon

def growlNotify(title, description, **kw):
    try:
        if usingStereo:
            description += '\n(AirPlay)'

        growl.notify(
            with_name=NOTIFICATION_TRACK_INFO,
            title=title,
            description=description,
            application_name=GROWL_APP_NAME,
            **kw)
    except CommandError:
        growlRegister()
        growlNotify(title, description, **kw)

def radioParadiseURL():
    session = scrape.Session()
    session.go('http://radioparadise.com/jq_playlist.php')
    url = session.region.firsttag('a')['href']
    if not url.startswith('http'):
    	url = 'http://www.radioparadise.com/rp2-' + url
	return url

def cleanStreamTitle(title):
    if title == k.missing_value:
        return ''
    title = title.split(' [')[0] # XXX move to description
    try: # incorrectly encoded?
        title = title.encode('iso-8859-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
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

def iTunesApp(): return app(id='com.apple.iTunes', terms=tunes)
def XTensionApp(): return app(creator='SHEx')
def AmuaApp(): return app('Amua.app')

HAVE_XTENSION = False
try:
    XTensionApp()
    HAVE_XTENSION = True
except:
    pass

HAVE_AMUA = False
try:
    AmuaApp()
    HAVE_AMUA = True
except:
    pass

needsStereoPowerOn = HAVE_XTENSION
usingStereo = False

def mayUseStereo():
    if not HAVE_XTENSION:
        return False
    systemEvents = app(id='com.apple.systemEvents')
    iTunesWindow = systemEvents.application_processes[u'iTunes'].windows[u'iTunes']
    # Can't get AirPlay status with iTunes Mini Player or window on other Space.
    try:
        remote_speakers = iTunesWindow.buttons[its.attributes['AXDescription'].value.beginswith(u'AirPlay')].title()
    except CommandError: # window on another Space?
        return usingStereo
    return remote_speakers and remote_speakers[0] not in (None, k.missing_value)

def turnStereoOnOrOff():
    global needsStereoPowerOn, usingStereo
    usingStereo = False
    if not default_output_device_is_airplay() and not mayUseStereo():
        if HAVE_XTENSION and XTensionApp().status('Stereo'):
            XTensionApp().turnoff('Stereo')
        return
    if not XTensionApp().status('Stereo'):
        XTensionApp().turnon('Stereo')
    usingStereo = True
    needsStereoPowerOn = False

def turnStereoOff():
    global needsStereoPowerOn, usingStereo
    usingStereo = False
    if default_output_device_is_airplay() or not mayUseStereo():
        return
    if not needsStereoPowerOn and XTensionApp().status('Stereo'):
        XTensionApp().turnoff('Stereo')
    needsStereoPowerOn = True

def amuaPlaying():
    if not HAVE_AMUA:
        return False
    return AmuaApp().is_playing()

class OneFileCache(object):
    __slots__ = ('key', 'cache')

    def __init__(self, cache):
        if not os.path.exists(cache):
            os.makedirs(cache)
        self.cache = os.path.join(cache, 'file')
        self.key = None

    def get(self, key):
        if key == self.key:
            return file(self.cache, 'r').read()

    def set(self, key, value):
        self.key = key
        file(self.cache, 'w').write(value)

    def delete(self, key):
        if key == self.key:
            self.key = None
            os.remove(cache)

class StreamVision(NSApplication):

    hotKeyActions = {}
    hotKeys = []

    def displayTrackInfo(self, playerInfo=None):
        iTunes = iTunesApp()

        try:
            trackClass = iTunes.current_track.class_()
        except CommandError:
            trackClass = k.property

        trackName = ''
        if trackClass != k.property:
            trackName = iTunes.current_track.name()

        try:
            playerState = iTunes.player_state()
        except CommandError:
            playerState = None # probably iTunes quit
        if playerState != k.playing:
            if playerState != None:
                growlNotify('iTunes is not playing.', trackName)
            turnStereoOff()
            return
        turnStereoOnOrOff()
        if trackClass == k.URL_track:
            if amuaPlaying():
                if playerInfo is None: # Amua displays it itself
                    AmuaApp().display_song_information()
                return
            url = iTunes.current_stream_URL()
            kw = {}
            if url != k.missing_value and url.endswith('.jpg'):
                try:
                    response, content = self.http.request(url)
                except Exception, e:
                    import sys
                    print >> sys.stderr, 'Request for album art failed:', e
                else:
                    if response['content-type'].startswith('image/'):
                        file(self.imagePath, 'w').write(content)
                        kw['image_from_location'] = self.imagePath
            growlNotify(cleanStreamTitle(iTunes.current_stream_title()),
                        cleanStreamTrackName(trackName), **kw)
            return
        if trackClass == k.property:
            growlNotify('iTunes is playing.', '')
            return
        kw = {}
        # XXX iTunes doesn't let you get artwork for shared tracks
        if trackClass != k.shared_track:
            artwork = iTunes.current_track.artworks()
            if artwork:
                try:
                    kw['pictImage'] = artwork[0].data_()
                except CommandError:
                    pass
        growlNotify(trackName + '  ' +
                    u'★' * (iTunes.current_track.rating() / 20),
                    iTunes.current_track.album() + '\n' +
                    iTunes.current_track.artist(),
                    **kw)

    def defaultOutputDeviceChanged(self):
        turnStereoOnOrOff()
        self.displayTrackInfo()

    def goToSite(self):
        iTunes = iTunesApp()
        if iTunes.player_state() == k.playing:
            if amuaPlaying():
                AmuaApp().display_album_details()
                return
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
        if amuaPlaying():
            if increment < 0:
                AmuaApp().ban_song()
                growlNotify('Banned song.', '', icon_of_application='Amua.app')
            else:
                AmuaApp().love_song()
                growlNotify('Loved song.', '', icon_of_application='Amua.app')
            return
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
        global needsStereoPowerOn

        iTunes = iTunesApp()
        was_playing = (iTunes.player_state() == k.playing)
        if not useStereo:
            needsStereoPowerOn = False
        if was_playing and amuaPlaying():
            AmuaApp().stop()
        else:
            iTunes.playpause()
        if not was_playing and iTunes.player_state() == k.stopped:
            # most likely, we're focused on the iPod, so playing does nothing
            iTunes.browser_windows[1].view.set(iTunes.user_playlists[its.name=='Stations'][1]())
            iTunes.play()
        if not useStereo:
            return
        if iTunes.player_state() == k.playing:
            turnStereoOnOrOff()
        else:
            turnStereoOff()

    def playPauseFront(self):
        systemEvents = app(id='com.apple.systemEvents')
        frontName = systemEvents.processes[its.frontmost == True][1].name()
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

    def nextTrack(self):
        if amuaPlaying():
            AmuaApp().skip_song()
            return
        iTunesApp().next_track()

    def registerZoomWindowHotKey(self):
        self.zoomWindowHotKey = self.registerHotKey(self.zoomWindow, 42, cmdKey | controlKey) # cmd-ctrl-\

    def unregisterZoomWindowHotKey(self):
        self.unregisterHotKey(self.zoomWindowHotKey)
        self.zoomWindowHotKey = None

    def zoomWindow(self):
        # XXX detect if "enable access for assistive devices" needs to be enabled
        systemEvents = app(id='com.apple.systemEvents')
        frontName = systemEvents.processes[its.frontmost == True][1].name()
        if frontName == 'iTunes':
            systemEvents.processes['iTunes'].menu_bars[1]. \
                menu_bar_items['Window'].menus.menu_items['Zoom'].click()
            return
        elif frontName in ('X11', 'XQuartz', 'Emacs'): # preserve C-M-\
            self.unregisterZoomWindowHotKey()
            systemEvents.key_code(42, using=[k.command_down, k.control_down])
            self.registerZoomWindowHotKey()
            return
        frontPID = systemEvents.processes[its.frontmost == True][1].unix_id()
        try:
            zoomed = app(pid=frontPID).windows[1].zoomed
            zoomed.set(not zoomed())
        except (CommandError, RuntimeError):
            systemEvents.processes[frontName].windows \
                [its.subrole == 'AXStandardWindow'].windows[1]. \
                buttons[its.subrole == 'AXZoomButton'].buttons[1].click()

    def finishLaunching(self):
        super(StreamVision, self).finishLaunching()

        caches = NSSearchPathForDirectoriesInDomains(NSCachesDirectory,
                                                     NSUserDomainMask, True)[0]
        cache = os.path.join(caches, 'StreamVision')
        self.http = httplib2.Http(OneFileCache(cache), 5)
        self.imagePath = os.path.join(cache, 'image')

        self.registerHotKey(self.displayTrackInfo, 100) # F8
        self.registerHotKey(self.goToSite, 100, cmdKey) # cmd-F8
        self.registerHotKey(self.playPause, 101) # F9
        self.registerHotKey(lambda: iTunesApp().previous_track(), 109) # F10
        self.registerHotKey(self.nextTrack, 103) # F11
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

        set_default_output_device_changed_callback(
            self.defaultOutputDeviceChanged)
        turnStereoOnOrOff()

    def sendEvent_(self, theEvent):
        eventType = theEvent.type()
        if eventType == NSSystemDefined and \
               theEvent.subtype() == kEventHotKeyPressedSubtype:
            self.hotKeyActions[theEvent.data1()]()
        elif eventType == NSApplicationDefined:
            key = theEvent.data1()
            if key == kHIDUsage_Csmr_ScanNextTrack:
                self.nextTrack()
            elif key == kHIDUsage_Csmr_ScanPreviousTrack:
                iTunesApp().previous_track()
            elif key == kHIDUsage_Csmr_PlayOrPause:
                self.playPauseFront()
        super(StreamVision, self).sendEvent_(theEvent)

if __name__ == "__main__":
    growlRegister()
    AppHelper.runEventLoop()
    try:
        HIDRemote.disconnect()
    except:
        pass
