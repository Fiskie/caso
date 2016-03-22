from oslo_config import cfg

CONF = cfg.CONF
CONF.import_opt("site_name", "caso.extract.manager")
CONF.import_opt("user", "caso.extract.base", "extractor")
CONF.import_opt("password", "caso.extract.base", "extractor")
CONF.import_opt("endpoint", "caso.extract.base", "extractor")
CONF.import_opt("insecure", "caso.extract.base", "extractor")


import keystoneclient

from caso.extract.v3 import CONF
from caso.extract.base import BaseExtractor


class V3BaseExtractor(BaseExtractor):
    def _get_keystone_session(self, tenant=None):
        auth = keystoneclient.auth.identity.v3.Password(
            username=CONF.extractor.user,
            password=CONF.extractor.password,
            auth_url=CONF.extractor.endpoint,
            user_domain_name='default',
            project_name=tenant,
            project_domain_name='default'
        )

        return keystoneclient.session.Session(auth=auth)

    def _get_keystone_client(self, tenant=None):
        """
        :param tenant: Unused in V3 implementation.
        :rtype keystoneclient.httpclient.ZHTTPClient
        """
        return keystoneclient.v3.client.Client(session=self._get_keystone_session(tenant))
