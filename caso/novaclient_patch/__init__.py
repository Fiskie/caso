from oslo_utils import netutils

try:
    import json
except ImportError:
    import simplejson as json

from six.moves.urllib import parse

from novaclient import client
from novaclient import exceptions
from novaclient.i18n import _


def authenticate_wrapper(self):
    if not self.auth_url:
        msg = _("Authentication requires 'auth_url', which should be "
                "specified in '%s'") % self.__class__.__name__
        raise exceptions.AuthorizationFailure(msg)
    magic_tuple = netutils.urlsplit(self.auth_url)
    scheme, netloc, path, query, frag = magic_tuple
    port = magic_tuple.port
    if port is None:
        port = 80
    path_parts = path.split('/')
    for part in path_parts:
        if len(part) > 0 and part[0] == 'v':
            self.version = part
            break

    if self.auth_token and self.management_url:
        self._save_keys()
        return

    # TODO(sandy): Assume admin endpoint is 35357 for now.
    # Ideally this is going to have to be provided by the service catalog.
    new_netloc = netloc.replace(':%d' % port, ':%d' % (35357,))
    admin_url = parse.urlunsplit(
            (scheme, new_netloc, path, query, frag))

    auth_url = self.auth_url

    if self.version == "v2.0":  # FIXME(chris): This should be better.
        while auth_url:
            if not self.auth_system or self.auth_system == 'keystone':
                auth_url = self._v2_auth(auth_url)
            else:
                auth_url = self._plugin_auth(auth_url)

        # Are we acting on behalf of another user via an
        # existing token? If so, our actual endpoints may
        # be different than that of the admin token.
        if self.proxy_token:
            if self.bypass_url:
                self.set_management_url(self.bypass_url)
            else:
                self._fetch_endpoints_from_auth(admin_url)
            # Since keystone no longer returns the user token
            # with the endpoints any more, we need to replace
            # our service account token with the user token.
            self.auth_token = self.proxy_token
    elif self.version == "v3":
        while auth_url:
            auth_url = self._v3_auth(auth_url)
    else:
        try:
            while auth_url:
                auth_url = self._v1_auth(auth_url)
        # In some configurations nova makes redirection to
        # v2.0 keystone endpoint. Also, new location does not contain
        # real endpoint, only hostname and port.
        except exceptions.AuthorizationFailure:
            if auth_url.find('v2.0') < 0:
                auth_url = auth_url + '/v2.0'
            self._v2_auth(auth_url)

    if self.bypass_url:
        self.set_management_url(self.bypass_url)
    elif not self.management_url:
        raise exceptions.Unauthorized('Nova Client')

    self._save_keys()


def _v3_auth(self, auth_url):
    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "domain": {"name": self.domain},
                        "name": self.user,
                        "password": self._get_password()
                    }
                }
            },
            "scope": {
                "project": {
                    "domain": {"name": self.domain},
                    "name": self.projectid
                }
            }
        }
    }

    auth_url += '/auth'

    return self._authenticate(auth_url, body)


client.HTTPClient.domain = "Default"
client.HTTPClient.authenticate = authenticate_wrapper
client.HTTPClient._v3_auth = _v3_auth
