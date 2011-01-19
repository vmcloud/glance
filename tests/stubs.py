# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 OpenStack, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Stubouts, mocks and fixtures for the test suite"""

import datetime
import httplib
import os
import shutil
import StringIO
import sys

import stubout
import webob

from glance.common import exception
from glance.registry import server as rserver
from glance import server
import glance.store
import glance.store.filesystem
import glance.store.http
import glance.store.swift
import glance.registry.db.sqlalchemy.api


FAKE_FILESYSTEM_ROOTDIR = os.path.join('/tmp', 'glance-tests')


def stub_out_http_backend(stubs):
    """Stubs out the httplib.HTTPRequest.getresponse to return
    faked-out data instead of grabbing actual contents of a resource

    The stubbed getresponse() returns an iterator over
    the data "I am a teapot, short and stout\n"

    :param stubs: Set of stubout stubs

    """

    class FakeHTTPConnection(object):

        DATA = 'I am a teapot, short and stout\n'

        def getresponse(self):
            return StringIO.StringIO(self.DATA)

        def request(self, *_args, **_kwargs):
            pass

    fake_http_conn = FakeHTTPConnection()
    stubs.Set(httplib.HTTPConnection, 'request',
              fake_http_conn.request)
    stubs.Set(httplib.HTTPSConnection, 'request',
              fake_http_conn.request)
    stubs.Set(httplib.HTTPConnection, 'getresponse',
              fake_http_conn.getresponse)
    stubs.Set(httplib.HTTPSConnection, 'getresponse',
              fake_http_conn.getresponse)


def clean_out_fake_filesystem_backend():
    """
    Removes any leftover directories used in fake filesystem
    backend
    """
    if os.path.exists(FAKE_FILESYSTEM_ROOTDIR):
        shutil.rmtree(FAKE_FILESYSTEM_ROOTDIR, ignore_errors=True)


def stub_out_filesystem_backend():
    """
    Stubs out the Filesystem Glance service to return fake
    pped image data from files.

    We establish a few fake images in a directory under //tmp/glance-tests
    and ensure that this directory contains the following files:

        //tmp/glance-tests/2 <-- file containing "chunk00000remainder"

    The stubbed service yields the data in the above files.

    """

    # Establish a clean faked filesystem with dummy images
    if os.path.exists(FAKE_FILESYSTEM_ROOTDIR):
        shutil.rmtree(FAKE_FILESYSTEM_ROOTDIR, ignore_errors=True)
    os.mkdir(FAKE_FILESYSTEM_ROOTDIR)

    f = open(os.path.join(FAKE_FILESYSTEM_ROOTDIR, '2'), "wb")
    f.write("chunk00000remainder")
    f.close()


def stub_out_s3_backend(stubs):
    """ Stubs out the S3 Backend with fake data and calls.

    The stubbed swift backend provides back an iterator over
    the data ""

    :param stubs: Set of stubout stubs

    """

    class FakeSwiftAuth(object):
        pass
    class FakeS3Connection(object):
        pass

    class FakeS3Backend(object):
        CHUNK_SIZE = 2
        DATA = 'I am a teapot, short and stout\n'

        @classmethod
        def get(cls, parsed_uri, expected_size, conn_class=None):
            S3Backend = glance.store.s3.S3Backend

            # raise BackendException if URI is bad.
            (user, key, authurl, container, obj) = \
                S3Backend._parse_s3_tokens(parsed_uri)

            def chunk_it():
                for i in xrange(0, len(cls.DATA), cls.CHUNK_SIZE):
                    yield cls.DATA[i:i+cls.CHUNK_SIZE]
            
            return chunk_it()

    fake_swift_backend = FakeS3Backend()
    stubs.Set(glance.store.s3.S3Backend, 'get',
              fake_swift_backend.get)


def stub_out_swift_backend(stubs):
    """Stubs out the Swift Glance backend with fake data
    and calls.

    The stubbed swift backend provides back an iterator over
    the data "I am a teapot, short and stout\n"

    :param stubs: Set of stubout stubs

    """
    class FakeSwiftAuth(object):
        pass

    class FakeSwiftConnection(object):
        pass

    class FakeSwiftBackend(object):

        CHUNK_SIZE = 2
        DATA = 'I am a teapot, short and stout\n'

        @classmethod
        def get(cls, parsed_uri, expected_size, conn_class=None):
            SwiftBackend = glance.store.swift.SwiftBackend

            # raise BackendException if URI is bad.
            (user, key, authurl, container, obj) = \
                SwiftBackend._parse_swift_tokens(parsed_uri)

            def chunk_it():
                for i in xrange(0, len(cls.DATA), cls.CHUNK_SIZE):
                    yield cls.DATA[i:i + cls.CHUNK_SIZE]

            return chunk_it()

    fake_swift_backend = FakeSwiftBackend()
    stubs.Set(glance.store.swift.SwiftBackend, 'get',
              fake_swift_backend.get)


def stub_out_registry(stubs):
    """Stubs out the Registry registry with fake data returns.

    The stubbed Registry always returns the following fixture::

        {'files': [
          {'location': 'file:///chunk0', 'size': 12345},
          {'location': 'file:///chunk1', 'size': 1235}
        ]}

    :param stubs: Set of stubout stubs

    """
    class FakeRegistry(object):

        DATA = \
            {'files': [
              {'location': 'file:///chunk0', 'size': 12345},
              {'location': 'file:///chunk1', 'size': 1235}
            ]}

        @classmethod
        def lookup(cls, _parsed_uri):
            return cls.DATA

    fake_registry_registry = FakeRegistry()
    stubs.Set(glance.store.registries.Registry, 'lookup',
              fake_registry_registry.lookup)


def stub_out_registry_and_store_server(stubs):
    """
    Mocks calls to 127.0.0.1 on 9191 and 9292 for testing so
    that a real Glance server does not need to be up and
    running
    """

    class FakeRegistryConnection(object):

        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            return True

        def close(self):
            return True

        def request(self, method, url, body=None, headers={}):
            self.req = webob.Request.blank("/" + url.lstrip("/"))
            self.req.method = method
            if headers:
                self.req.headers = headers
            if body:
                self.req.body = body

        def getresponse(self):
            res = self.req.get_response(rserver.API())

            # httplib.Response has a read() method...fake it out
            def fake_reader():
                return res.body

            setattr(res, 'read', fake_reader)
            return res

    class FakeGlanceConnection(object):

        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            return True

        def close(self):
            return True

        def request(self, method, url, body=None, headers={}):
            self.req = webob.Request.blank("/" + url.lstrip("/"))
            self.req.method = method
            if headers:
                self.req.headers = headers
            if body:
                self.req.body = body

        def getresponse(self):
            res = self.req.get_response(server.API())

            # httplib.Response has a read() method...fake it out
            def fake_reader():
                return res.body

            setattr(res, 'read', fake_reader)
            return res

    def fake_get_connection_type(client):
        """
        Returns the proper connection type
        """
        DEFAULT_REGISTRY_PORT = 9191
        DEFAULT_API_PORT = 9292

        if (client.port == DEFAULT_API_PORT and
            client.host == '0.0.0.0'):
            return FakeGlanceConnection
        elif (client.port == DEFAULT_REGISTRY_PORT and
              client.host == '0.0.0.0'):
            return FakeRegistryConnection

    def fake_image_iter(self):
        for i in self.response.app_iter:
            yield i

    stubs.Set(glance.client.BaseClient, 'get_connection_type',
              fake_get_connection_type)
    stubs.Set(glance.client.ImageBodyIterator, '__iter__',
              fake_image_iter)


def stub_out_registry_db_image_api(stubs):
    """Stubs out the database set/fetch API calls for Registry
    so the calls are routed to an in-memory dict. This helps us
    avoid having to manually clear or flush the SQLite database.

    The "datastore" always starts with this set of image fixtures.

    :param stubs: Set of stubout stubs

    """
    class FakeDatastore(object):

        FIXTURES = [
            {'id': 1,
                'name': 'fake image #1',
                'status': 'active',
                'type': 'kernel',
                'is_public': False,
                'created_at': datetime.datetime.utcnow(),
                'updated_at': datetime.datetime.utcnow(),
                'deleted_at': None,
                'deleted': False,
                'size': 13,
                'location': "swift://user:passwd@acct/container/obj.tar.0",
                'properties': []},
            {'id': 2,
                'name': 'fake image #2',
                'status': 'active',
                'type': 'kernel',
                'is_public': True,
                'created_at': datetime.datetime.utcnow(),
                'updated_at': datetime.datetime.utcnow(),
                'deleted_at': None,
                'deleted': False,
                'size': 19,
                'location': "file:///tmp/glance-tests/2",
                'properties': []}]

        VALID_STATUSES = ('active', 'killed', 'queued', 'saving')

        def __init__(self):
            self.images = FakeDatastore.FIXTURES
            self.next_id = 3

        def image_create(self, _context, values):

            values['id'] = values.get('id', self.next_id)

            if values['id'] in [image['id'] for image in self.images]:
                raise exception.Duplicate("Duplicate image id: %s" %
                                          values['id'])

            if 'status' not in values.keys():
                values['status'] = 'active'
            else:
                if not values['status'] in self.VALID_STATUSES:
                    raise exception.Invalid("Invalid status '%s' for image" %
                                            values['status'])

            values['deleted'] = False
            values['properties'] = values.get('properties', {})
            values['created_at'] = datetime.datetime.utcnow()
            values['updated_at'] = datetime.datetime.utcnow()
            values['deleted_at'] = None

            props = []

            if 'properties' in values.keys():
                for k, v in values['properties'].iteritems():
                    p = {}
                    p['key'] = k
                    p['value'] = v
                    p['deleted'] = False
                    p['created_at'] = datetime.datetime.utcnow()
                    p['updated_at'] = datetime.datetime.utcnow()
                    p['deleted_at'] = None
                    props.append(p)

            values['properties'] = props

            self.next_id += 1
            self.images.append(values)
            return values

        def image_update(self, _context, image_id, values):

            props = []

            if 'properties' in values.keys():
                for k, v in values['properties'].iteritems():
                    p = {}
                    p['key'] = k
                    p['value'] = v
                    p['deleted'] = False
                    p['created_at'] = datetime.datetime.utcnow()
                    p['updated_at'] = datetime.datetime.utcnow()
                    p['deleted_at'] = None
                    props.append(p)

            values['properties'] = props

            image = self.image_get(_context, image_id)
            image.update(values)
            return image

        def image_destroy(self, _context, image_id):
            image = self.image_get(_context, image_id)
            self.images.remove(image)

        def image_get(self, _context, image_id):

            images = [i for i in self.images if str(i['id']) == str(image_id)]

            if len(images) != 1 or images[0]['deleted']:
                new_exc = exception.NotFound("No model for id %s %s" %
                                             (image_id, str(self.images)))
                raise new_exc.__class__, new_exc, sys.exc_info()[2]
            else:
                return images[0]

        def image_get_all_public(self, _context, public):
            return [f for f in self.images
                    if f['is_public'] == public]

    fake_datastore = FakeDatastore()
    stubs.Set(glance.registry.db.sqlalchemy.api, 'image_create',
              fake_datastore.image_create)
    stubs.Set(glance.registry.db.sqlalchemy.api, 'image_update',
              fake_datastore.image_update)
    stubs.Set(glance.registry.db.sqlalchemy.api, 'image_destroy',
              fake_datastore.image_destroy)
    stubs.Set(glance.registry.db.sqlalchemy.api, 'image_get',
              fake_datastore.image_get)
    stubs.Set(glance.registry.db.sqlalchemy.api, 'image_get_all_public',
              fake_datastore.image_get_all_public)