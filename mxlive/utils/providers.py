from __future__ import annotations

import logging
import weakref
from typing import Any

import httpx2
from basiclive.core.lims.models import (
    ProjectMembership,
)
from basiclive.core.lims.providers import (
    BaseProjectProvider,
    ExternalMemberData,
    ExternalProjectData
)
from basiclive.utils.misc import parse_date_value, NestedDict

logger = logging.getLogger(__name__)

_ROLE_RANK = {
    ProjectMembership.Role.MEMBER: 1,
    ProjectMembership.Role.CO_INVESTIGATOR: 2,
    ProjectMembership.Role.PI: 3,
}


class USOProjectProvider(BaseProjectProvider):
    ALLOCATIONS = '/v2/projects/allocations/'
    CYCLE = '/v2/projects/cycles/active'
    INSTITUTION = '/v2/institution/'

    def __init__(self, cache_ttl: int | None = 900, **options: Any):
        super().__init__(cache_ttl=cache_ttl, **options)
        self.base_url: str = str(options.get("base_url", "")).rstrip("/")
        self.headers: dict[str, str] = dict(options.get("headers") or {})
        self.search: str = str(options.get("search", "")).strip()
        self.timeout: float = float(options.get("timeout", 10.0))
        self.client = httpx2.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            follow_redirects=True,
        )
        self._finalizer = weakref.finalize(self, self._close)

    def _close(self):
        self.client.close()

    def _fetch(self, uri: str, **params):
        # initial request
        response = self.client.get(uri, params=params)
        response.raise_for_status()
        data = response.json()

        # check if results are lists and pull remaining entries
        if {'count', 'next', 'previous', 'results'}.issubset(set(data.keys())):
            results = []
            results.extend(data.get('results', []))
            next_uri = data.get('next')

            while next_uri:
                response = self.client.get(next_uri)
                response.raise_for_status()
                data = response.json()
                results.extend(data.get('results', []))
                next_uri = data.get('next')
            return results
        else:
            return data

    def _fetch_cycle(self):
        return self._fetch(self.CYCLE)

    @staticmethod
    def _get_role(roles: list[str]) -> ProjectMembership.Role:
        if 'pi' in roles:
            return ProjectMembership.Role.PI
        elif 'delegate' in roles:
            return ProjectMembership.Role.DELEGATE
        else:
            return ProjectMembership.Role.MEMBER

    @staticmethod
    def _get_contact(team: list[dict]) -> dict:
        # find spokesperson first
        for member in team:
            if 'spokesperson' in member['team_roles']:
                return member

        # fall back to pi
        for member in team:
            if 'pi' in member['team_roles']:
                return member

        return team[0]

    def _parse_member(self, raw: dict[str, Any]) -> ExternalMemberData:
        member = NestedDict(raw)
        return ExternalMemberData(
            username=str(member.username).strip(),
            email=str(member.email).strip().lower(),
            first_name=str(member.first_name).strip(),
            last_name=str(member.last_name).strip(),
            role=self._get_role(member.team_roles),
            phone="",
        )

    def _parse_project(self, raw: dict[str, Any]) -> ExternalProjectData:
        project = NestedDict(raw)
        members = [
            self._parse_member(m)
            for m in project.team
            if isinstance(m, dict)
        ]
        raw_contact = self._get_contact(project.team)
        raw_institution = self.fetch_institution(raw_contact['institution'])
        if isinstance(raw_institution, dict):
            raw_contact.update(raw_institution)
        contact = NestedDict(raw_contact)

        return ExternalProjectData(
            source_id=str(project.code).strip(),
            code=str(project.code).strip(),
            title=str(project.title).strip(),
            start_date=parse_date_value(project.start_date),
            end_date=parse_date_value(project.end_date),
            kind=str(project.proposal_type).strip(),
            alias=None,
            contact_person=f"{contact.first_name} {contact.last_name}",
            contact_email=contact.email,
            contact_phone="",
            organisation=contact.institution,
            department=contact.department,
            address=contact.adress,
            city=contact.city,
            region_code=contact.region,
            country_code=contact.country,
            postal_code=contact.postal_code,
            members=members,
        )

    def fetch_projects(self) -> list[ExternalProjectData]:
        cycle = self._fetch_cycle()
        if not cycle:
            return []
        cur_cycle = int(cycle['id'])
        params = {
            'search': self.search
        }
        raw_projects: dict[str, dict] = {}
        for cycle_id in [cur_cycle, cur_cycle + 1]:
            params['cycle'] = str(cycle_id)
            raw_projects.update({
                alloc['project']['code']: alloc['project']
                for alloc in self._fetch(self.ALLOCATIONS, **params)
            })

        projects: list[ExternalProjectData] = [
            self._parse_project(item)
            for item in raw_projects.values()
            if isinstance(item, dict)
        ]

        return projects

    def fetch_institution(self, name: str) -> dict | None:
        raw = self._fetch(self.INSTITUTION, name=name)
        if isinstance(raw, dict):
            return raw
        elif isinstance(raw, list) and len(raw) > 0:
            return raw[0]
        return None

