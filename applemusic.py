from jwcrypto import jwk, jwt
import httplib2
import json
import os
import pkgutil
import time
import urllib

class AppleMusic(object):
    def __init__(self):
        self.key = jwk.JWK()
        key_path = os.path.join(os.path.dirname(__file__), 'AuthKey_8937YX2XGP.p8')
        self.key.import_from_pem(file(key_path, 'r').read())
        self.http = httplib2.Http()

    def get_authorization_headers(self):
        seconds_since_epoch = int(time.time())
        token = jwt.JWT(header=dict(alg='ES256', kid='8937YX2XGP'),
                        claims=dict(iss='CYEL96ZVC2',
                                        iat=seconds_since_epoch,
                                        exp=seconds_since_epoch + 2592000))
        token.make_signed_token(self.key)
        return dict(Authorization='Bearer ' + token.serialize())

    def search_for_songs(self, search_term):
        query = urllib.urlencode(dict(term=search_term, types='songs'))
        (response, content) = self.http.request(
            'https://api.music.apple.com/v1/catalog/us/search?' + query,
            headers=self.get_authorization_headers())
        if response.status != 200:
            import sys
            print >> sys.stderr, 'Search failed: ', response, content
            return None

        content = json.loads(content)

        # json.dump(content, __import__('sys').stdout, indent=2)

        try:
            results = content['results']
            album_names = {}
            for album in results['albums']['data']:
                attr = album['attributes']
                album_names[int(album['id'])] = attr['name']
            songs = {}
            for song in results['songs']['data']:
                attr = song['attributes']
                artist_album = attr['artistName']
                url = attr['url']
                # XXX dependent on knowing the structure of URLs as .../album/id<album ID>?...
                album_name = album_names.get(int(url[url.rindex('/id')+3:url.rindex('?')]))
                if album_name:
                    artist_album = '%s - %s' % (artist_album, album_name)
                songs['%s - %d %s (%s)' % (artist_album, attr['trackNumber'], attr['name'], attr['releaseDate'])] = url
        except KeyError:
            import traceback
            traceback.print_exc()
            return {}
        return songs

if __name__ == '__main__':
    import pprint, sys
    pprint.pprint(AppleMusic().search_for_songs(' '.join(sys.argv[1:])))
