# -*- coding: utf-8 -*-

# Copyright 2014 Spanish National Research Council (CSIC)
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime
import operator

import dateutil.parser
import novaclient.client
from dateutil import tz
from caso.record import CloudRecord

from caso.extract.v3 import V3BaseExtractor, CONF


class NovaExtractor(V3BaseExtractor):
    def _get_conn(self, tenant):
        client = novaclient.client.Client
        conn = client(
            2,
            session=self._get_keystone_session(tenant),
            insecure=CONF.extractor.insecure)
        return conn

    def get_servers(self, nova_client, since):
        """
        Fetch a list of servers.
        :type nova_client: novaclient
        :type since: datetime.datetime
        """
        servers = nova_client.servers.list(search_opts={"changes-since": since})
        return sorted(servers, key=operator.attrgetter("created"))

    def generate_base_cloud_record(self, server, images, users, vo):
        """
        Generate a CloudRecord based on information fetched from nova.
        :rtype: CloudRecord
        """
        status = self.vm_status(server.status)
        image_id = None

        for image in images:
            if image.id == server.image['id']:
                image_id = image.metadata.get("vmcatcher_event_ad_mpuri",
                                              None)
                break

        if image_id is None:
            image_id = server.image['id']

        return CloudRecord(server.id,
                           CONF.site_name,
                           server.name,
                           server.user_id,
                           server.tenant_id,
                           vo,
                           cloud_type="OpenStack",
                           status=status,
                           image_id=image_id,
                           user_dn=users.get(server.user_id, None))

    def extract_for_tenant(self, tenant, lastrun):
        """Extract records for a tenant from given date querying nova.

        This method will get information from nova.

        :param tenant: Tenant to extract records for.
        :param lastrun: datetime.datetime object indicating the date to
                             extract records from
        :returns: A dictionary of {"server_id": caso.record.Record"}
        """
        # Some API calls do not expect a TZ, so we have to remove the timezone
        # from the dates. We assume that all dates coming from upstream are
        # in UTC TZ.

        now = datetime.datetime.now(tz.tzutc()).replace(tzinfo=None)
        end = now + datetime.timedelta(days=1)

        # Try and except here
        nova_client = self._get_conn(tenant)
        ks_client = self._get_keystone_client(tenant)
        users = self._get_keystone_users(ks_client)
        tenant_id = self.get_project_id(tenant)
        servers = self.get_servers(nova_client, since=lastrun)

        if servers:
            start = dateutil.parser.parse(servers[0].created)
        else:
            start = lastrun

        start = start.replace(tzinfo=None)

        aux = nova_client.usage.get(tenant_id, start, end)
        usages = getattr(aux, "server_usages", [])

        images = nova_client.images.list()

        records = {}

        vo = self.voms_map.get(tenant)

        for server in servers:
            records[server.id] = self.generate_base_cloud_record(server, images, users, vo)

        for usage in usages:
            if usage["instance_id"] not in records:
                continue
            instance_id = usage["instance_id"]
            records[instance_id].memory = usage["memory_mb"]
            records[instance_id].cpu_count = usage["vcpus"]
            records[instance_id].disk = usage["local_gb"]

            started = dateutil.parser.parse(usage["started_at"])
            records[instance_id].start_time = int(started.strftime("%s"))
            if usage.get("ended_at", None) is not None:
                ended = dateutil.parser.parse(usage['ended_at'])
                records[instance_id].end_time = int(ended.strftime("%s"))
                wall = ended - started
            else:
                wall = now - started

            wall = int(wall.total_seconds())
            records[instance_id].wall_duration = wall

            cput = int(usage["hours"] * 3600)
            # NOTE(aloga): in some cases there may be rounding errors and cput
            # may be larger than wall.
            records[instance_id].cpu_duration = cput if cput < wall else wall

        return records
