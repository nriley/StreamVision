"""Python module for web browsing and scraping.

Done:
  - navigate to absolute and relative URLs
  - follow links in page or region
  - find first or all occurrences of string or RE in page or region
  - find first, last, next, previous, or all tags with given name/attributes
  - find first, last, next, previous, enclosing, or all elements with given
        name/attributes/content
  - set form fields
  - submit forms
  - strip tags from arbitrary strings of HTML

Todo:
  - cookie-handling is dumb (sends all cookies to all sites)
  - handle CDATA and RCDATA marked sections
  - support for submitting forms with file upload
  - use Regions in striptags instead of duplicating work
  - map of enders
"""

__author__ = 'Ka-Ping Yee'
__date__ = '2005-03-29'
__version__ = '$Revision: 1.16 $'

import os, socket, re, marshal, subprocess
from tempfile import gettempdir
from urlparse import urljoin, urlsplit
from urllib import urlencode

def connect(server, port):
    """Return a TCP socket connected to the given server and port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server, port))
    return sock

def receive(sock):
    """Read all the data from a socket until it closes."""
    chunks = []
    while 1:
        chunk = sock.recv(4096)
        if chunk: chunks.append(chunk)
        else: return ''.join(chunks)

def request(host, method, path, headers, entity=None):
    """Make an HTTP request and return (status, message, headers, document)."""
    sock = connect(host, 80)
    request = method + ' ' + path + ' HTTP/1.0\r\n'
    for name in headers:
        capname = '-'.join([part.capitalize() for part in name.split('-')])
        request += capname + ': ' + str(headers[name]) + '\r\n'
    request += '\r\n'
    if entity:
        request += entity
    sock.sendall(request)
    data = receive(sock)
    try: return splitreply(data)
    except: return (0, '', {}, data)

def splitreply(reply):
    """Split an HTTP response into (status, message, headers, document)."""
    if '\r\n\r\n' in reply:
        head, document = reply.split('\r\n\r\n', 1)
    else:
        head, document = reply, ''
    headers = []
    while True:
	if '\r\n' in head:
            response, head = head.split('\r\n', 1)
            for line in head.split('\r\n'):
                name, value = line.split(': ', 1)
                headers.append((name.lower(), value))
	else:
	    response, head = head, ''
        status = int(response.split()[1])
        message = ' '.join(response.split()[2:])
        if document.startswith('HTTP/1.') and '\r\n\r\n' in document:
            head, document = document.split('\r\n\r\n', 1)
        else:
            return status, message, headers, document

def shellquote(text):
    """Quote a string literal for sh."""
    return "'" + text.replace("'", "'\\''") + "'"

def curl(url, entity=None, follow=1, cookies=[], referrer=None):
    """Invoke curl to perform an HTTP request."""
    command = ['curl', '-s', '-i']
    if referrer:
        command += ['-e', referrer]
    if entity:
        if not isinstance(entity, str):
            entity = urlencode(entity, doseq=1)
        command += ['-d', entity]
    if not follow:
        command += ['-Z', '0']
    else:
        command += ['-L']
    if cookies:
        command += ['-b', '; '.join(cookies)]
    command.append(url)
    reply = subprocess.Popen(command, stdout=subprocess.PIPE).stdout.read()
    return splitreply(reply)

def fetch(url, entity=None, follow=1):
    """Fetch one document in a one-shot session."""
    return Session().fetch(url, entity, follow)

class ScrapeError(Exception): pass
class HTTPError(ScrapeError): pass
LAST_URL = object()

class Session:
    """A Web-browsing session.
    
    Exposed attributes:
    
    agent - set or get the User-Agent string
    location - get the current (i.e. last successfully fetched) URL
    status - get the status code of the last successful request
    message - get the status message of the last successful request
    headers - get the dictionary of headers from the last successful request
    document - get the document returned by the last successful request
    region - get a Region spanning the entire document
    """

    def __init__(self, agent=None):
        self.cookies = []
        self.agent = agent
        self.location = self.status = self.message = None
        self.headers = self.document = self.region = None
        self.history = []

    def fetch(self, url, entity=None, follow=1, referrer=LAST_URL):
        scheme, host, path, query, fragment = urlsplit(url)
        if referrer is LAST_URL:
            referrer = self.location
        self.location = url
        if scheme == 'https':
            status, message, headers, document = \
                curl(url, entity, follow, self.cookies)
        elif scheme == 'http':
            if query:
                path += '?' + query
            headers = {}
            headers['host'] = host
            headers['accept'] = '*/*'
            if referrer:
                headers['referer'] = referrer
            self.location = url
            if self.agent:
                headers['user-agent'] = self.agent
            if self.cookies:
                headers['cookie'] = '; '.join(self.cookies)
            if entity:
                if not isinstance(entity, str):
                    entity = urlencode(entity, doseq=1)
                headers['content-type'] = 'application/x-www-form-urlencoded'
                headers['content-length'] = len(entity)
            method = entity and 'POST' or 'GET'
            status, message, headers, document = \
                request(host, method, path, headers, entity)
        else:
            raise ValueError, scheme + ' not supported'
        headerdict = {}
        for name, value in headers:
            if name == 'set-cookie':
                cookie = value.split(';')[0]
                if cookie not in self.cookies:
                    self.cookies.append(cookie)
            else:
                headerdict[name] = value
        if follow and status in [301, 302] and 'location' in headerdict:
            return self.fetch(urljoin(url, headerdict['location']))
        return status, message, headerdict, document

    def go(self, url, entity=None, follow=1, referrer=LAST_URL):
        """Navigate to a given URL.  If the URL is relative, it is resolved
        with respect to the current location.  If the document is successfully
        fetched, return a Region spanning the entire document."""
        historyentry = (self.location, self.status, self.message,
                        self.headers, self.document, self.region)
        if self.location:
            url = urljoin(self.location, url)
        results = self.fetch(url, entity, follow, referrer)
        if results[0] == 200:
            self.history.append(historyentry)
            self.status, self.message, self.headers, self.document = results
            self.region = Region(self.document)
            return self.region
        raise HTTPError(self.status, self.message)

    def back(self):
        """Return to the previous page."""
        (self.location, self.status, self.message,
         self.headers, self.document, self.region) = self.history.pop()
        return self.location

    def follow(self, anchor, region=None):
        """Follow the first link with the given anchor text.  The anchor may
        be given as a string or a compiled RE.  If a region is given, the
        link is sought within that region instead of the whole document."""
        link = (region or self.region).first('a', content=anchor)
        if not link:
            raise ScrapeError('link %r not found' % anchor)
        if not link['href']:
            raise ScrapeError('link %r has no href' % link)
        return self.go(link['href'])

    def submit(self, form, button=None, **params):
        """Submit a form, optionally by clicking a given button."""
        if form.tagname != 'form':
            raise ScrapeError('%r is not a form' % form)
        p = form.params
        if button:
            p[button['name']] = button['value']
        p.update(params)
        method = form['method'].lower() or 'get'
        if method == 'post':
            return self.go(form['action'], p)
        elif method == 'get':
            return self.go(form['action'] + '?' + urlencode(p, doseq=1))
        else:
            raise ScrapeError('unknown form method %r' % method)

tagcontent_re = r'''(('[^']*'|"[^"]*"|--([^-]|-[^-])*--|-(?!-)|[^'">-])*)'''

def tag_re(tagname_re):
    return '<' + tagname_re + tagcontent_re + '>'

anytag_re = tag_re(r'(\?|!\w*|/?[a-zA-Z_:][\w:.-]*)')
tagpat = re.compile(anytag_re)

def htmldec(text):
    """Decode HTML entities in the given text."""
    chunks = text.split('&#')
    for i in range(1, len(chunks)):
        number, rest = chunks[i].split(';', 1)
        chunks[i] = chr(int(number)) + rest
    text = ''.join(chunks)
    text = text.replace('\xa0', ' ')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&amp;', '&')
    return text

def htmlenc(text):
    """Use HTML entities to encode special characters in the given text."""
    text = text.replace('&', '&amp;')
    text = text.replace('"', '&quot;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text

def no_groups(re):
    return re.replace('(', '(?:').replace('(?:?', '(?')

tagsplitter = re.compile(no_groups(anytag_re))
parasplitter = re.compile(no_groups(tag_re('(p|table|form)')), re.I)
linesplitter = re.compile(no_groups(tag_re('(div|br|tr)')), re.I)
scriptpat = re.compile(r'<script\b', re.I)
endscriptpat = re.compile(r'</script[^>]*>', re.I)
endcommentpat = re.compile(r'--\s*>')

def striptags(text):
    """Strip HTML tags from the given text, yielding line breaks for DIV,
       BR, or TR tags and blank lines for P, TABLE, or FORM tags."""
    chunks = scriptpat.split(text)
    for i in range(1, len(chunks)):
        chunks[i] = endscriptpat.split(chunks[i], 1)[1]
    text = ''.join(chunks)
    chunks = text.split('<!')
    for i in range(1, len(chunks)):
        if chunks[i].split('>', 1)[0].find('--') >= 0:
            chunks[i] = endcommentpat.split(chunks[i], 1)[1]
        else:
            chunks[i] = chunks[i].split('>', 1)[1]
    text = ''.join(chunks)

    paragraphs = []
    for paragraph in parasplitter.split(text):
        lines = []
        for line in linesplitter.split(paragraph):
            line = ''.join(tagsplitter.split(line))
            line = htmldec(line)
            line = ' '.join(line.split())
            lines.append(line)
        paragraphs.append('\n'.join(lines))
    return re.sub('\n\n+', '\n\n', '\n\n'.join(paragraphs)).strip()

attr_re = r'''\s*([\w:.-]+)(\s*=\s*('[^']*'|"[^"]*"|[^\s>]*))?'''
attrpat = re.compile(attr_re)

def parseattrs(text):
    """Turn a string of name=value pairs into an attribute dictionary."""
    attrs = {}
    pos = 0
    while 1:
        match = attrpat.search(text, pos)
        if not match: break
        pos = match.end()
        name, value = match.group(1), match.group(3) or ''
        if value[:1] in ["'", '"']:
            value = value[1:-1]
        attrs[name.lower()] = htmldec(value)
    return attrs

def matchcontent(specimen, desired):
    if hasattr(desired, 'match'):
        return desired.match(specimen)
    elif callable(desired):
        return desired(specimen)
    else:
        return specimen == desired

def matchattrs(specimen, desired):
    for name, value in desired.items():
        name = name.strip('_').replace('_', '-')
        if not (name in specimen and matchcontent(specimen[name], value)):
            return 0
    return 1

class Region:
    """A Region object represents a contiguous region of a document together
    with an associated HTML or XML tag and its attributes."""

    def __init__(self, parent, start=0, end=None, starttag=None, endtag=None):
        """Create a Region.  The parent argument is a string or another
        Region.  The start and end arguments, if given, specify non-negative
        indices into the original string (not into a parent subregion).""" 
        if isinstance(parent, Region):
            self.document = parent.document
            self.tags = parent.tags
        else:
            self.document = parent
            self.tags = self.scantags(self.document)
        if end is None:
            end = len(self.document)
        self.start, self.end = start, end
        self.tagname, self.attrs = None, {}

        # If only starttag is specified, this Region is a tag.
        # If starttag and endtag are specified, this Region is an element.
        self.starttag, self.endtag = starttag, endtag
        if starttag is not None:
            self.start, self.end, self.tagname, self.attrs = self.tags[starttag]
        if endtag is not None:
            self.start, self.end = self.tags[starttag][1], self.tags[endtag][0]

        # Find the minimum and maximum indices of tags within this Region.
        if starttag and endtag:
            self.tagmin, self.tagmax = starttag + 1, endtag - 1
        else:
            self.tagmin, self.tagmax = len(self.tags), -1
            for i, (start, end, tagname, attrs) in enumerate(self.tags):
                if start >= self.start and i < self.tagmin:
                    self.tagmin = i
                if end <= self.end and i > self.tagmax:
                    self.tagmax = i

    def __repr__(self):
        if self.tagname:
            attrs = ''.join([' %s=%r' % item for item in self.attrs.items()])
            return '<Region %d:%d %s%s>' % (
                self.start, self.end, self.tagname, attrs)
        else:
            return '<Region %d:%d>' % (self.start, self.end)

    # Utilities that operate on the array of scanned tags.
    def scantags(self, document):
        """Generate a list of all the tags in a document."""
        tags = []
        pos = 0
        while 1:
            match = tagpat.search(document, pos)
            if not match: break
            start, end = match.span()
            tagname = match.group(1).lower()
            attrs = match.group(2)
            tags.append([start, end, tagname, attrs])
            if tagname == 'script':
                match = endscriptpat.search(document, end)
                if not match: break
                start, end = match.span()
                tags.append([start, end, '/' + tagname, ''])
            pos = end
        return tags

    def matchtag(self, i, tagname, attrs):
        """Return 1 if the ith tag matches the given tagname and attributes."""
        itagname, iattrs = self.tags[i][2], self.tags[i][3]
        if itagname[:1] not in ['', '?', '!', '/']:
            if itagname == tagname or tagname is None:
                if isinstance(iattrs, str):
                    self.tags[i][3] = iattrs = parseattrs(iattrs)
                return matchattrs(iattrs, attrs)

    def findendtag(self, starttag, outside=0):
        """Find the index of the matching end tag for the given start tag.
        If outside is 0, look for the end tag within the current region;
        if outside is 1, look beyond the end of the current region."""
        tagname = self.tags[starttag][2]
        depth = 1
        for i in range(starttag + 1, len(self.tags)):
            if self.tags[i][2] == tagname:
                depth += 1
            if self.tags[i][2] == '/' + tagname:
                depth -= 1
            if depth == 0:
                if not outside and i <= self.tagmax:
                    return i
                if outside and i > self.tagmax:
                    return i
                break

    def matchelement(self, starttag, content=None, outside=0):
        """If the element with the given start tag matches the given content,
        return the index of the matching end tag.  See findendtag() for the
        meaning of the outside flag."""
        endtag = self.findendtag(starttag, outside)
        if endtag is not None:
            start, end = self.tags[starttag][1], self.tags[endtag][0]
            stripped = striptags(self.document[start:end])
            if content is None or matchcontent(stripped, content):
                return endtag

    # Provide the "content" and "text" attributes to access the contents.
    content = property(lambda self: self.document[self.start:self.end])
    text = property(lambda self: striptags(self.content))

    def getparams(self):
        """Get a dictionary of default values for all the form parameters."""
        if self.tagname == 'form':
            params = {}
            for input in self.alltags('input'):
                if 'disabled' not in input:
                    type = input['type'].lower()
                    if type in ['text', 'password', 'hidden'] or (
                       type in ['checkbox', 'radio'] and 'checked' in input):
                        params[input['name']] = input['value']
            for select in self.all('select'):
                if 'disabled' not in select:
                    selections = [option['value']
                                  for option in select.alltags('option')
                                  if 'selected' in option]
                    if 'multiple' in select:
                        params[select['name']] = selections
                    elif selections:
                        params[select['name']] = selections[0]
            for textarea in self.all('textarea'):
                if 'disabled' not in textarea:
                    params[textarea['name']] = textarea.content
            return params

    def getbuttons(self):
        """Get a list of all the form submission buttons."""
        if self.tagname == 'form':
            return [tag for tag in self.alltags('input')
                        if tag['type'].lower() in ['submit', 'image']
               ] + [tag for tag in self.alltags('button')
                        if tag['type'].lower() in ['submit', '']]

    params = property(getparams)
    buttons = property(getbuttons)

    # Provide a dictionary-like interface to the tag attributes.
    def __contains__(self, name):
        return name in self.attrs

    def __getitem__(self, name):
        return self.attrs.get(name, '')

    # Provide subregions by slicing.
    def __getslice__(self, start, end):
        start += (start < 0) and self.end or self.start
        end += (end < 0) and self.end or self.start
        return Region(self, start, end)

    # Search for text.
    def find(self, target, group=0):
        """Search this Region for a string or a compiled RE and return a
        Region representing the match.  The optional group argument specifies
        which grouped subexpression should be returned as the match."""
        if hasattr(target, 'search'):
            match = target.search(self.content)
            if match:
                return self[match.start(group):match.end(group)]
        else:
            start = self.content.find(target)
            if start > -1:
                return self[start:start+len(target)]

    def findall(self, target, group=0):
        """Search this Region for a string or a compiled RE and return a
        sequence of Regions representing all the matches."""
        pos = 0
        content = self.content
        matches = []
        if hasattr(target, 'search'):
            while 1:
                match = target.search(content, pos)
                if not match:
                    break
                start, pos = match.span(group)
                matches.append(self[start:pos])
        else:
            while 1:
                start = content.find(target, pos)
                if start < 0:
                    break
                pos = start + len(target)
                matches.append(self[start:pos])
        return matches

    # Search for tags.
    def firsttag(self, tagname=None, **attrs):
        """Return the Region for the first tag entirely within this Region
        with the given tag name and attributes."""
        for i in range(self.tagmin, self.tagmax + 1):
            if self.matchtag(i, tagname, attrs):
                return Region(self, 0, 0, i)

    def lasttag(self, tagname=None, **attrs):
        """Return the Region for the last tag entirely within this Region
        with the given tag name and attributes."""
        for i in range(self.tagmax, self.tagmin - 1, -1):
            if self.matchtag(i, tagname, attrs):
                return Region(self, 0, 0, i)

    def alltags(self, tagname=None, **attrs):
        """Return a list of Regions for all the tags entirely within this
        Region with the given tag name and attributes."""
        tags = []
        for i in range(self.tagmin, self.tagmax + 1):
            if self.matchtag(i, tagname, attrs):
                tags.append(Region(self, 0, 0, i))
        return tags

    def nexttag(self, tagname=None, **attrs):
        """Return the Region for the nearest tag after the end of this Region
        with the given tag name and attributes."""
        return Region(self, self.end).firsttag(tagname, **attrs)

    def previoustag(self, tagname=None, **attrs):
        """Return the Region for the nearest tag before the start of this
        Region with the given tag name and attributes."""
        return Region(self, 0, self.start).lasttag(tagname, **attrs)

    # Search for elements.
    def first(self, tagname=None, content=None, **attrs):
        """Return the Region for the first properly balanced element entirely
        within this Region with the given tag name, content, and attributes.
        The element content is passed through striptags().  If the content
        argument has a match() method, the stripped content is passed into
        this method; otherwise it is compared directly as a string."""
        for starttag in range(self.tagmin, self.tagmax + 1):
            if self.matchtag(starttag, tagname, attrs):
                endtag = self.matchelement(starttag, content)
                if endtag is not None:
                    return Region(self, 0, 0, starttag, endtag)

    def last(self, tagname=None, content=None, **attrs):
        """Return the Region for the last properly balanced element entirely
        within this Region with the given tag name, content, and attributes."""
        for starttag in range(self.tagmax, self.tagmin - 1, -1):
            if self.matchtag(starttag, tagname, attrs):
                endtag = self.matchelement(starttag, content)
                if endtag is not None:
                    return Region(self, 0, 0, starttag, endtag)

    def all(self, tagname=None, content=None, **attrs):
        """Return Regions for all non-overlapping balanced elements entirely
        within this Region with the given tag name, content, and attributes."""
        elements = []
        starttag = self.tagmin
        while starttag <= self.tagmax:
            if self.matchtag(starttag, tagname, attrs):
                endtag = self.matchelement(starttag, content)
                if endtag is not None:
                    elements.append(Region(self, 0, 0, starttag, endtag))
                    starttag = endtag
            starttag += 1
        return elements

    def next(self, tagname=None, content=None, **attrs):
        """Return the Region for the nearest balanced element after the end of
        this Region with the given tag name, content, and attributes."""
        return Region(self, self.end).first(tagname, content, **attrs)

    def previous(self, tagname=None, content=None, **attrs):
        """Return the Region for the nearest balanced element before the start
        of this Region with the given tag name, content, and attributes."""
        return Region(self, 0, self.start).last(tagname, content, **attrs)

    def enclosing(self, tagname=None, content=None, **attrs):
        """Return the Region for the nearest balanced element that encloses
        this Region with the given tag name, content, and attributes."""
        if self.starttag and self.endtag: # skip our own start tag
            laststarttag = self.starttag - 1
        else:
            laststarttag = self.tagmin - 1
        for starttag in range(laststarttag, -1, -1):
            if self.matchtag(starttag, tagname, attrs):
                endtag = self.matchelement(starttag, content, outside=1)
                if endtag is not None:
                    return Region(self, 0, 0, starttag, endtag)

def read(path):
    """Read and return the entire contents of the file at the given path."""
    return open(path).read()

def write(path, text):
    """Write the given text to a file at the given path."""
    file = open(path, 'w')
    file.write(text)
    file.close()

def load(path):
    """Return the deserialized contents of the file at the given path."""
    return marshal.load(open(path))

def dump(path, data):
    """Serialize the given data and write it to a file at the given path."""
    file = open(path, 'w')
    marshal.dump(data, file)
    file.close()

def getnumber(text):
    """Find and parse a floating-point or integer number in the given text,
       ignoring commas, percentage signs, and non-numeric words."""
    for word in striptags(text).replace(',', '').replace('%', '').split():
        try: return int(word)
        except:
            try: return float(word)
            except: continue
