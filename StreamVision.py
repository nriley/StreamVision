#!/usr/bin/pythonw
# -*- coding: utf-8 -*-

from aem.ae import newdesc
from aem.findapp import ApplicationNotFoundError
from appscript import app, k, its, CommandError
from AppKit import (NSApplication, NSApplicationDefined, NSBeep, NSImage,
                    NSSystemDefined, NSURL, NSWorkspace,
                    NSWorkspaceApplicationKey,
                    NSWorkspaceDidActivateApplicationNotification)
from Foundation import (NSDistributedNotificationCenter,
                        NSSearchPathForDirectoriesInDomains,
                        NSCachesDirectory, NSUserDomainMask)
from PyObjCTools import AppHelper
from Carbon.CarbonEvt import RegisterEventHotKey, GetApplicationEventTarget
from Carbon.Events import cmdKey, shiftKey
from AudioDevice import (default_output_device_is_airplay,
                         set_default_output_device_changed_callback)
import httplib2
import json
import os
import scrape
import sys
import urllib
import urlparse
import HotKey

GROWL_APP_NAME = 'StreamVision'
NOTIFICATION_TRACK_INFO = 'iTunes Track Info'
NOTIFICATIONS_ALL = [NOTIFICATION_TRACK_INFO]

kEventHotKeyPressedSubtype = 6
kEventHotKeyReleasedSubtype = 9

def growlRegister():
    global growl
    growl = app(id='com.Growl.GrowlHelperApp')

    growl.register(
        as_application=GROWL_APP_NAME,
        all_notifications=NOTIFICATIONS_ALL,
        default_notifications=NOTIFICATIONS_ALL,
        icon_of_application='iTunes.app')
        # if we leave off the .app, we can get Classic iTunes's icon

def growlNotify(title, description='', **kw):
    try:
        if usingStereo:
            description += '\n(AirPlay)'

        if 'image' in kw:
            image = (NSImage.alloc().initWithData_(buffer(kw['image']))
                     .TIFFRepresentation())
            kw['image'] = newdesc('TIFF', image)

        growl.notify(
            with_name=NOTIFICATION_TRACK_INFO,
            title=title,
            description=description,
            identifier='StreamVision notification',
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

class UninstalledApp(object):
    __slots__ = ('kw',)
    def __init__(self, **kw): self.kw = kw
    def isrunning(self): return False
    def __repr__(self): return '<UninstalledApp: ' + ', '.join('%s=%r' % (k, v) for k, v in self.kw.iteritems())

def appIfInstalled(**kw):
    try:
        return app(**kw)
    except ApplicationNotFoundError:
        return UninstalledApp(**kw)
        
def HermesApp(): return appIfInstalled(id='com.alexcrichton.Hermes')
def iTunesApp(): return app(id='com.apple.iTunes')
def SpotifyApp(): return appIfInstalled(id='com.spotify.client')
def XTensionApp(): return app(creator='SHEx')

HAVE_XTENSION = False
try:
    XTensionApp()
    HAVE_XTENSION = True
except:
    pass

needsStereoPowerOn = HAVE_XTENSION
usingStereo = False

def hermesPlaying():
    Hermes = HermesApp()
    if Hermes.isrunning() and Hermes.playback_state() == k.playing:
        return Hermes

def spotifyPlaying():
    Spotify = SpotifyApp()
    if Spotify.isrunning() and Spotify.player_state() == k.playing:
        return Spotify

def mayUseStereo():
    if not HAVE_XTENSION:
        return False
    if hermesPlaying() or spotifyPlaying():
        return False
    try:
        # A bit better in iTunes 11.0.3, but can't do this via an Apple
        # Event descriptor; have to send multiple events
        return any(d.kind() != k.computer
                   for d in iTunesApp().current_AirPlay_devices())
    except AttributeError:
        pass

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
    if HAVE_XTENSION and not XTensionApp().status('Stereo'):
        XTensionApp().turnon('Stereo')
    usingStereo = True
    needsStereoPowerOn = False

def turnStereoOff():
    global needsStereoPowerOn, usingStereo
    usingStereo = False
    if default_output_device_is_airplay() or not mayUseStereo():
        return
    if not needsStereoPowerOn and HAVE_XTENSION and XTensionApp().status('Stereo'):
        XTensionApp().turnoff('Stereo')
    needsStereoPowerOn = True

def imageAtURL(url, force=False):
    # Spotify image URLs look like http://images.spotify.com/image/<hex>
    if url and (force or url.endswith('.jpg')):
        try:
            response, content = http.request(url)
        except Exception, e:
            print >> sys.stderr, 'Request for album art from', url, 'failed:', e
        else:
            if response['content-type'].startswith('image/'):
                return content

def itmsAlbumArtwork(itmsURL):
    try:
        itmsURL = urlparse.urlparse(itmsURL)
        query = urlparse.parse_qs(itmsURL.query)
        if itmsURL.path == '/album': # Apple Music
            action = 'lookup'
            query = dict(id=query['i'][0])
        elif itmsURL.path == '/link': # usually iTunes Store
            if not 'pn' in query: # may be n= station name or "Contacting Store"
                return
            action = 'search'
            query = dict(media='music', entity='album', limit='1',
                         term='%s %s' % (query['an'][0], query['pn'][0]))
            # XXX search through albums instead?
    except Exception, e:
        print >> sys.stderr, 'Parsing itms URL', itmsURL, 'failed:', e
        return

    url = 'http://itunes.apple.com/%s?%s' % (action, urllib.urlencode(query))
    try:
        response, content = http.request(url)
        if not response['content-type'].startswith('text/javascript'):
            print >> sys.stderr, 'Request for iTunes JSON from', url, 'failed:',
            print >> sys.stderr, response
            return
    except Exception, e:
        print >> sys.stderr, 'Request for iTunes JSON from', url, 'failed:', e
        return

    try:
        artworkURL = json.loads(content)['results'][0]['artworkUrl100']
        artworkURL = artworkURL.replace('100x100', '400x400')
    except Exception, e:
        print >> sys.stderr, 'Parsing JSON from', url, 'failed:', e
        return

    return imageAtURL(artworkURL)

def notifyTrackInfo(name, album=None, artist=None, rating=0, artwork=False,
                    streamTitle=None, streamURL=None, playing=True):
    if not playing:
        growlNotify('iTunes is not playing.', name)
        return
    turnStereoOnOrOff()

    if streamURL:
        kw = {}
        image = imageAtURL(streamURL)
        if image:
            kw['image'] = image
        growlNotify(cleanStreamTitle(streamTitle),
                    cleanStreamTrackName(name), **kw)
        return

    if not name:
        growlNotify('iTunes is playing.')
        return

    kw = {}
    if artwork is True:
        try:
            kw['image'] = iTunesApp().current_track.artworks[1].data_().data
        except CommandError:
            pass
    elif artwork:
        kw['image'] = artwork

    growlNotify(name + '  ' + u'★' * (rating / 20),
                (album or '') + '\n' + (artist or ''),
                **kw)

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
            os.remove(self.cache)

class StreamVision(NSApplication):

    hotKeyActions = {}
    hotKeysActive = {}
    hotKeysSuspended = []

    # iTunes exposes Apple Music information through notifications only
    iTunesLastTrackInfo = [None]

    def playerInfoChanged(self, playerInfo):
        infoDict = dict(playerInfo.userInfo())
        trackName = infoDict.get('Name', '')
        playerState = infoDict.get('Player State')
        if playerState != 'Playing':
            notifyTrackInfo(trackName, playing=False)
            return
        url = infoDict.get('Stream URL')
        if url:
            notifyTrackInfo(trackName, streamTitle=infoDict.get('Stream Title'),
                            streamURL=url)
            return
        artworkCount = int(infoDict.get('Artwork Count', 0))
        if artworkCount == 0:
            itms_URL = infoDict.get('Store URL')
            artwork = itmsAlbumArtwork(itms_URL)
        else:
            artwork = True
        self.iTunesLastTrackInfo = [trackName, infoDict.get('Album'),
                                    infoDict.get('Artist'),
                                    infoDict.get('Rating', 0), artwork]
        notifyTrackInfo(*self.iTunesLastTrackInfo)

    def spotifyPlaybackStateChanged(self):
        Spotify = spotifyPlaying()
        if Spotify:
            self.displayTrackInfo()
        else:
            growlNotify('Spotify is not playing.',
                        icon_of_application=SpotifyApp().AS_appdata.identifier)

    def requestedDisplayTrackInfo(self):
        growlNotify('Requesting track information...')
        self.displayTrackInfo()

    def displayTrackInfo(self):
        Hermes = hermesPlaying()
        if Hermes:
            infoDict = Hermes.current_song.properties()
            notifyTrackInfo(infoDict[k.title], infoDict[k.album],
                            infoDict[k.artist], infoDict[k.rating],
                            imageAtURL(infoDict[k.artwork_URL]))
            return

        Spotify = spotifyPlaying()
        if Spotify:
            # XXX this fails; either use the notification or lots of events
            # infoDict = Spotify.current_track.properties()
            track = Spotify.current_track
            notifyTrackInfo(track.name(), track.album(),
                            track.artist(),
                            artwork=imageAtURL(track.artwork_url(), force=True))
            return

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
            notifyTrackInfo(trackName, playing=False)
            return
        if trackClass == k.URL_track:
            # either an Internet radio station or iTunes Radio
            url = iTunes.current_stream_URL()
            if url != k.missing_value:
                notifyTrackInfo(trackName,
                                streamTitle=iTunes.current_stream_title(),
                                streamURL=url)
                return
        if trackClass == k.property:
            notifyTrackInfo(*self.iTunesLastTrackInfo)
            return
        notifyTrackInfo(trackName, iTunes.current_track.album(),
                        iTunes.current_track.artist(),
                        iTunes.current_track.rating(),
                        True)

    def defaultOutputDeviceChanged(self):
        turnStereoOnOrOff()
        self.displayTrackInfo()

    def showTrack(self):
        for playerPlaying in hermesPlaying(), spotifyPlaying():
            if playerPlaying:
                playerPlaying.activate()
                return

        iTunes = iTunesApp()
        if iTunes.player_state() == k.playing:
            url = iTunes.current_stream_URL()
            if url != k.missing_value:
                if 'radioparadise.com' in url and 'review' not in url:
                    growlNotify('Looking up Radio Paradise song...')
                    url = radioParadiseURL()
                NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(url))
            else:
                # XXX Activate first or sometimes iTunes doesn't
                # actually highlight the currently playing track,
                # despite revealing it (iTunes 12.2.2)
                iTunes.activate()
                iTunes.current_track.reveal()
        NSBeep()

    def registerHotKey(self, func, keyCode, mods=0):
        hotKeyRef = RegisterEventHotKey(keyCode, mods, (0, 0),
                                        GetApplicationEventTarget(), 0)
        self.hotKeysActive[hotKeyRef] = (func, keyCode, mods)
        self.hotKeyActions[HotKey.HotKeyAddress(hotKeyRef)] = func
        return hotKeyRef

    def unregisterHotKey(self, hotKeyRef):
        del self.hotKeysActive[hotKeyRef]
        del self.hotKeyActions[HotKey.HotKeyAddress(hotKeyRef)]
        hotKeyRef.UnregisterEventHotKey()

    def suspendHotKeys(self):
        for hotKeyRef, hotKeyParams in self.hotKeysActive.items():
            self.unregisterHotKey(hotKeyRef)
            self.hotKeysSuspended.append(hotKeyParams)

    def resumeHotKeys(self):
        for hotKeyParams in self.hotKeysSuspended:
            self.registerHotKey(*hotKeyParams)
        self.hotKeysSuspended = []

    def applicationDidActivate(self, notification):
        application = notification.userInfo()[NSWorkspaceApplicationKey]
        if application and application.bundleIdentifier() == 'com.citrix.XenAppViewer':
            self.suspendHotKeys()
        else:
            self.resumeHotKeys()

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

    def adjustVolumeBy(self, increment):
        Hermes = hermesPlaying()
        if Hermes:
            if increment > 0: Hermes.increase_volume()
            else: Hermes.decrease_volume()
            return

        for player in spotifyPlaying(), iTunesApp():
            if player is None:
                continue
            volume = player.sound_volume() + increment
            if volume < 0: volume = 0
            elif volume > 100: volume = 100
            player.sound_volume.set(volume)
            volumeIn10 = volume // 10
            growlNotify('Volume ' + (u'▸' * volumeIn10) + (u'▹' * (10 - volumeIn10)),
                icon_of_application=player.AS_appdata.identifier)
            return

    def playPause(self, useStereo=True):
        global needsStereoPowerOn

        # if Hermes or Spotify is open, assume we're using it
        for player in HermesApp(), SpotifyApp():
            if player.isrunning():
                player.playpause()
                return

        iTunes = iTunesApp()
        was_playing = (iTunes.player_state() == k.playing)
        if not useStereo:
            needsStereoPowerOn = False
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

    def nextTrack(self):
        Spotify = spotifyPlaying()
        if Spotify:
            Spotify.next_track()
            return

        Hermes = hermesPlaying()
        if Hermes:
            Hermes.next_song()
            return

        iTunesApp().next_track()

    def previousTrack(self):
        Spotify = spotifyPlaying()
        if Spotify:
            Spotify.previous_track()
            return

        iTunesApp().previous_track()

    def finishLaunching(self):
        global http

        super(StreamVision, self).finishLaunching()

        caches = NSSearchPathForDirectoriesInDomains(NSCachesDirectory,
                                                     NSUserDomainMask, True)[0]
        cache = os.path.join(caches, 'StreamVision')
        http = httplib2.Http(OneFileCache(cache), 5)
        self.imagePath = os.path.join(cache, 'image')

        self.registerHotKey(self.requestedDisplayTrackInfo, 100) # F8
        self.registerHotKey(self.showTrack, 100, cmdKey) # cmd-F8
        self.registerHotKey(self.playPause, 101) # F9
        self.registerHotKey(self.previousTrack, 103) # F11
        self.registerHotKey(self.nextTrack, 111) # F12
        self.registerHotKey(lambda: self.incrementRatingBy(-20), 103, shiftKey) # shift-F11
        self.registerHotKey(lambda: self.incrementRatingBy(20), 111, shiftKey) # shift-F12
        self.registerHotKey(lambda: self.adjustVolumeBy(-10), 103, cmdKey) # cmd-F11
        self.registerHotKey(lambda: self.adjustVolumeBy(10), 111, cmdKey) # cmd-F12

        workspaceNotificationCenter = NSWorkspace.sharedWorkspace().notificationCenter()
        workspaceNotificationCenter.addObserver_selector_name_object_(self, self.applicationDidActivate, NSWorkspaceDidActivateApplicationNotification, None)

        distributedNotificationCenter = NSDistributedNotificationCenter.defaultCenter()
        distributedNotificationCenter.addObserver_selector_name_object_(self, self.playerInfoChanged, 'com.apple.iTunes.playerInfo', None)
        distributedNotificationCenter.addObserver_selector_name_object_(self, self.spotifyPlaybackStateChanged, 'com.spotify.client.PlaybackStateChanged', None)
        distributedNotificationCenter.addObserver_selector_name_object_(self, self.terminate_, 'com.apple.logoutContinued', None)

        set_default_output_device_changed_callback(
            self.defaultOutputDeviceChanged)
        turnStereoOnOrOff()

    def sendEvent_(self, theEvent):
        eventType = theEvent.type()
        if eventType == NSSystemDefined and \
               theEvent.subtype() == kEventHotKeyPressedSubtype:
            self.hotKeyActions[theEvent.data1()]()
        super(StreamVision, self).sendEvent_(theEvent)

if __name__ == "__main__":
    growlRegister()
    AppHelper.runEventLoop(installInterrupt=True)
