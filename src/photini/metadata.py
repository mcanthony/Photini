##  Photini - a simple photo metadata editor.
##  http://github.com/jim-easterbrook/Photini
##  Copyright (C) 2012-13  Jim Easterbrook  jim@jim-easterbrook.me.uk
##
##  This program is free software: you can redistribute it and/or
##  modify it under the terms of the GNU General Public License as
##  published by the Free Software Foundation, either version 3 of the
##  License, or (at your option) any later version.
##
##  This program is distributed in the hope that it will be useful,
##  but WITHOUT ANY WARRANTY; without even the implied warranty of
##  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
##  General Public License for more details.
##
##  You should have received a copy of the GNU General Public License
##  along with this program.  If not, see
##  <http://www.gnu.org/licenses/>.

import datetime
import fractions
import locale
import logging
import os
import sys

from PyQt4 import QtCore

try:
    from .metadata_gexiv2 import MetadataHandler
except ImportError as e:
    try:
        from .metadata_pyexiv2 import MetadataHandler
    except ImportError:
        # raise exception on the one we really wanted
        raise e
from . import __version__

class GPSvalue(object):
    def __init__(self, degrees=0.0, latitude=True):
        self.degrees = degrees
        self.latitude = latitude

    def from_xmp_string(self, value):
        degrees, residue = value.split(',')
        minutes = residue[:-1]
        direction = residue[-1]
        self.degrees = float(degrees) + (float(minutes) / 60.0)
        if direction in ('S', 'W'):
            self.degrees = -self.degrees
        self.latitude = direction in ('S', 'N')
        return self

    def to_xmp_string(self):
        if self.degrees >= 0.0:
            ref = ('E', 'N')[self.latitude]
            value = self.degrees
        else:
            ref = ('W', 'S')[self.latitude]
            value = -self.degrees
        degrees = int(value)
        minutes = (value - degrees) * 60.0
        return '%d,%.13f%s' % (degrees, minutes, ref)

    def from_exif_string(self, value, direction):
        parts = map(fractions.Fraction, value.split())
        self.degrees = float(parts[0])
        if len(parts) > 1:
            self.degrees += float(parts[1]) / 60.0
        if len(parts) > 2:
            self.degrees += float(parts[2]) / 3600.0
        if direction in ('S', 'W'):
            self.degrees = -self.degrees
        self.latitude = direction in ('S', 'N')
        return self

    def to_exif_string(self):
        if self.degrees >= 0.0:
            ref = ('E', 'N')[self.latitude]
            value = self.degrees
        else:
            ref = ('W', 'S')[self.latitude]
            value = -self.degrees
        degrees = int(value)
        value = (value - degrees) * 60.0
        minutes = int(value)
        seconds = (value - minutes) * 60.0
        degrees = fractions.Fraction(degrees).limit_denominator(1000000)
        minutes = fractions.Fraction(minutes).limit_denominator(1000000)
        seconds = fractions.Fraction(seconds).limit_denominator(1000000)
        return '%d/%d %d/%d %d/%d' % (
            degrees.numerator, degrees.denominator,
            minutes.numerator, minutes.denominator,
            seconds.numerator, seconds.denominator), ref

class Metadata(QtCore.QObject):
    _keys = {
        'date_digitised' : (('Exif.Photo.DateTimeDigitized',     True,  0),),
        'date_modified'  : (('Exif.Image.DateTime',              True,  0),),
        'date_taken'     : (('Exif.Photo.DateTimeOriginal',      True,  0),
                            ('Exif.Image.DateTimeOriginal',      True,  0),),
        'title'          : (('Xmp.dc.title',                     True,  0),
                            ('Iptc.Application2.ObjectName',     False, 64),
                            ('Iptc.Application2.Headline',       False, 256),
                            ('Exif.Image.ImageDescription',      True,  0),),
        'creator'        : (('Xmp.dc.creator',                   True,  0),
                            ('Xmp.tiff.Artist',                  False, 0),
                            ('Iptc.Application2.Byline',         False, 32),
                            ('Exif.Image.Artist',                True,  0),),
        'description'    : (('Xmp.dc.description',               True,  0),
                            ('Iptc.Application2.Caption',        False, 2000),),
        'keywords'       : (('Xmp.dc.subject',                   True,  0),
                            ('Iptc.Application2.Keywords',       False, 64),),
        'copyright'      : (('Xmp.dc.rights',                    True,  0),
                            ('Xmp.tiff.Copyright',               False, 0),
                            ('Iptc.Application2.Copyright',      False, 128),
                            ('Exif.Image.Copyright',             True,  0),),
        'latitude'       : (('Exif.GPSInfo.GPSLatitude',         True,  0),
                            ('Xmp.exif.GPSLatitude',             True,  0),),
        'longitude'      : (('Exif.GPSInfo.GPSLongitude',        True,  0),
                            ('Xmp.exif.GPSLongitude',            True,  0),),
        'orientation'    : (('Exif.Image.Orientation',           True,  0),),
        'soft_full'      : (('Exif.Image.ProcessingSoftware',    True,  0),),
        'soft_name'      : (('Iptc.Application2.Program',        False, 32),),
        'soft_vsn'       : (('Iptc.Application2.ProgramVersion', False, 10),),
        }
    _list_items = ('keywords',)
    def __init__(self, path, parent=None):
        QtCore.QObject.__init__(self, parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        # create metadata handlers for image file and sidecar (if present)
        self._path = path
        self._if = MetadataHandler(path)
        self._sc_path = self._find_side_car(path)
        if self._sc_path:
            self._sc = MetadataHandler(self._sc_path)
        else:
            self._sc = None
        self._unsaved = False
        # possible character encodings of metadata strings
        self._encodings = ['utf_8', 'latin_1']
        char_set = locale.getdefaultlocale()[1]
        if char_set:
            self._encodings.append(char_set)

    def _find_side_car(self, path):
        for base in (os.path.splitext(path)[0], path):
            for ext in ('.xmp', '.XMP'):
                result = base + ext
                if os.path.exists(result):
                    return result
        return None

    def create_side_car(self):
        self._sc_path = self._path + '.xmp'
        with open(self._sc_path, 'w') as of:
            of.write('<x:xmpmeta x:xmptk="XMP Core 4.4.0-Exiv2" ')
            of.write('xmlns:x="adobe:ns:meta/">\n')
            of.write('</x:xmpmeta>')
        self._sc = MetadataHandler(self._sc_path)
        self._sc.copy(self._if, comment=False)

    def save(self, if_mode, sc_mode):
        if not self._unsaved:
            return
        self.set_item('soft_full', 'Photini editor v%s' % (__version__))
        self.set_item('soft_name', 'Photini editor')
        self.set_item('soft_vsn', '%s' % (__version__))
        if sc_mode == 'delete' and self._sc:
            self._if.copy(self._sc, comment=False)
        OK = False
        if if_mode:
            OK = self._if.save()
        if sc_mode == 'delete' and self._sc and OK:
            os.unlink(self._sc_path)
            self._sc = None
        if sc_mode == 'auto' and not self._sc and not OK:
            self.create_side_car()
        if sc_mode == 'always' and not self._sc:
            self.create_side_car()
        if self._sc:
            OK = self._sc.save()
        self._set_unsaved(not OK)

    # tag lists: merge tags from sidecar and image file
    def get_exif_tags(self):
        result = self._if.get_exif_tags()
        if self._sc:
            for tag in self._sc.get_exif_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_iptc_tags(self):
        result = self._if.get_iptc_tags()
        if self._sc:
            for tag in self._sc.get_iptc_tags():
                if tag not in result:
                    result.append(tag)
        return result

    def get_xmp_tags(self):
        result = self._if.get_xmp_tags()
        if self._sc:
            for tag in self._sc.get_xmp_tags():
                if tag not in result:
                    result.append(tag)
        return result

    # getters: use sidecar if tag is present, otherwise use image file
    def get_exif_tag_string(self, tag):
        if self._sc and tag in self._sc.get_exif_tags():
            return self._sc.get_exif_tag_string(tag)
        return self._if.get_exif_tag_string(tag)

    def get_iptc_tag_multiple(self, tag):
        if self._sc and tag in self._sc.get_iptc_tags():
            return self._sc.get_iptc_tag_multiple(tag)
        return self._if.get_iptc_tag_multiple(tag)

    def get_xmp_tag_string(self, tag):
        if self._sc and tag in self._sc.get_xmp_tags():
            return self._sc.get_xmp_tag_string(tag)
        return self._if.get_xmp_tag_string(tag)

    def get_xmp_tag_multiple(self, tag):
        if self._sc and tag in self._sc.get_xmp_tags():
            return self._sc.get_xmp_tag_multiple(tag)
        return self._if.get_xmp_tag_multiple(tag)

    # setters: set in both sidecar and image file
    def set_exif_tag_string(self, tag, value):
        if self._sc:
            self._sc.set_exif_tag_string(tag, value)
        self._if.set_exif_tag_string(tag, value)

    def set_exif_tag_long(self, tag, value):
        if self._sc:
            self._sc.set_exif_tag_long(tag, value)
        self._if.set_exif_tag_long(tag, value)

    def set_iptc_tag_multiple(self, tag, value):
        if self._sc:
            self._sc.set_iptc_tag_multiple(tag, value)
        self._if.set_iptc_tag_multiple(tag, value)

    def set_xmp_tag_string(self, tag, value):
        if self._sc:
            self._sc.set_xmp_tag_string(tag, value)
        self._if.set_xmp_tag_string(tag, value)

    def set_xmp_tag_multiple(self, tag, value):
        if self._sc:
            self._sc.set_xmp_tag_multiple(tag, value)
        self._if.set_xmp_tag_multiple(tag, value)

    def clear_tag(self, tag):
        if self._sc:
            self._sc.clear_tag(tag)
        self._if.clear_tag(tag)

    def get_tags(self):
        return self.get_exif_tags() + self.get_iptc_tags() + self.get_xmp_tags()

    def has_GPS(self):
        return (('Xmp.exif.GPSLatitude' in self.get_xmp_tags()) or
                ('Exif.GPSInfo.GPSLatitude' in self.get_exif_tags()))

    def _decode(self, value):
        if sys.version_info[0] >= 3:
            return value
        for encoding in self._encodings:
            try:
                return unicode(value, encoding)
            except UnicodeDecodeError:
                continue
        return unicode(value, 'utf_8')

    def get_item(self, name):
        for key, required, max_bytes in self._keys[name]:
            family, group, tag = key.split('.')
            if key in self.get_xmp_tags():
                if tag.startswith('GPS'):
                    return GPSvalue().from_xmp_string(
                        self.get_xmp_tag_string(key))
                value = self.get_xmp_tag_multiple(key)
                return '; '.join(value)
            if key in self.get_iptc_tags():
                value = map(lambda x: self._decode(x),
                            self.get_iptc_tag_multiple(key))
                return '; '.join(value)
            if key in self.get_exif_tags():
                value = self._decode(self.get_exif_tag_string(key))
                if tag.startswith('DateTime'):
                    return datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                if tag == 'Orientation':
                    return int(value)
                if group == 'GPSInfo':
                    return GPSvalue().from_exif_string(
                        value, self.get_exif_tag_string('%sRef' % key))
                return value
        return None

    def _encode(self, value, max_bytes):
        result = value.encode('utf_8')
        if max_bytes:
            result = result[:max_bytes]
        if sys.version_info[0] >= 3:
            result = str(result, 'ascii')
        return result

    def set_item(self, name, value):
        if value == self.get_item(name):
            return
        if name in self._list_items:
            value = map(lambda x: x.strip(), value.split(';'))
            for i in reversed(range(len(value))):
                if not value[i]:
                    del value[i]
        elif isinstance(value, (str, unicode)):
            value = [value.strip()]
        if not value:
            self.del_item(name)
            return
        for key, required, max_bytes in self._keys[name]:
            if required or key in self.get_tags():
                family, group, tag = key.split('.')
                if family == 'Xmp':
                    if isinstance(value, GPSvalue):
                        self.set_xmp_tag_string(key, value.to_xmp_string())
                    else:
                        self.set_xmp_tag_multiple(key, value)
                elif family == 'Iptc':
                    value = map(lambda x: self._encode(x, max_bytes), value)
                    self.set_iptc_tag_multiple(key, value)
                elif family == 'Exif':
                    if isinstance(value, GPSvalue):
                        string, ref = value.to_exif_string()
                        self.set_exif_tag_string(key, string)
                        self.set_exif_tag_string('%sRef' % key, ref)
                    elif isinstance(value, datetime.datetime):
                        self.set_exif_tag_string(
                            key, value.strftime('%Y:%m:%d %H:%M:%S'))
                    elif isinstance(value, int):
                        self.set_exif_tag_long(key, value)
                    else:
                        self.set_exif_tag_string(
                            key, self._encode(value[0], max_bytes))
        self._set_unsaved(True)

    def del_item(self, name):
        changed = False
        for key, required, max_bytes in self._keys[name]:
            if key in self.get_tags():
                self.clear_tag(key)
                changed = True
        if changed:
            self._set_unsaved(True)

    new_status = QtCore.pyqtSignal(bool)
    def _set_unsaved(self, status):
        self._unsaved = status
        self.new_status.emit(self._unsaved)

    def changed(self):
        return self._unsaved
