from oslo_config import cfg

CONF = cfg.CONF
CONF.import_opt("site_name", "caso.extract.manager")
CONF.import_opt("user", "caso.extract.base", "extractor")
CONF.import_opt("password", "caso.extract.base", "extractor")
CONF.import_opt("endpoint", "caso.extract.base", "extractor")
CONF.import_opt("insecure", "caso.extract.base", "extractor")


import keystoneclient

from caso.extract.base import BaseExtractor


class V3BaseExtractor(BaseExtractor):
    _projects = None

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
        :param tenant: project ID.
        :rtype keystoneclient.httpclient.ZHTTPClient
        """
        return keystoneclient.v3.client.Client(session=self._get_keystone_session(tenant))

    def get_project_list(self, dummy_project):
        """
        Get a list of projects.

        For some reason this endpoint likes to throw a 403 if no project ID is supplied,
        even though we just want to get a list of projects.
        Ergo we make a request using an actual project name; it doesn't matter which one.
        """
        # TODO: domain scope 403 is probably to do with faulty keystone policy config -- revise?
        if not self._projects:
            self._projects = self._get_keystone_client(dummy_project).projects.list()

        return self._projects

    def get_project_id(self, tenant):
        for project in self.get_project_list(tenant):
            if project.name == tenant:
                return project.id
