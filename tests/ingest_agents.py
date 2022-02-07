import json
import os
from copy import deepcopy

import requests
from ingest.utils.s2s_token_client import S2STokenClient, ServiceCredential
from ingest.utils.token_manager import TokenManager


class IngestBrokerAgent:
    INGEST_BROKER_URL_TEMPLATE = "https://ingest.{}.archive.data.humancellatlas.org"
    INGEST_BROKER_PROD_URL = "https://ingest.archive.data.humancellatlas.org"

    def __init__(self, deployment):
        self.deployment = deployment
        if self.deployment == 'prod':
            self.ingest_broker_url = self.INGEST_BROKER_PROD_URL
        else:
            self.ingest_broker_url = self.INGEST_BROKER_URL_TEMPLATE.format(self.deployment)

        self.ingest_auth_agent = IngestAuthAgent()
        self.auth_headers = self.ingest_auth_agent.make_auth_header()

    def upload(self, metadata_spreadsheet_path, is_update=False, project_uuid=None, submission_uuid=None):
        url = self.ingest_broker_url + '/api_upload'

        params = {}
        if is_update:
            params['isUpdate'] = is_update

        if project_uuid:
            params['projectUuid'] = project_uuid

        if submission_uuid:
            params['submissionUuid'] = submission_uuid

        data = {
            'params': json.dumps(params)
        }

        files = {'file': open(metadata_spreadsheet_path, 'rb')}

        response = requests.post(url, data=data, files=files, allow_redirects=False, headers=self.auth_headers)
        if response.status_code != requests.codes.found and response.status_code != requests.codes.created:
            raise RuntimeError(f"POST {url} response was {response.status_code}: {response.content}")
        return json.loads(response.content)['details']['submission_id']

    def download_spreadsheet(self, submission_uuid):
        url = self.ingest_broker_url + f'/submissions/{submission_uuid}/spreadsheet'
        response = requests.get(url)
        return response.content

    def generate_spreadsheet(self, submission_uuid):
        url = self.ingest_broker_url + f'/submissions/{submission_uuid}/spreadsheet'
        response = requests.post(url)
        response.raise_for_status()
        return response


class IngestApiAgent:
    INGEST_API_URL_TEMPLATE = "https://api.ingest.{}.archive.data.humancellatlas.org"
    INGEST_API_PROD_URL = "https://api.ingest.archive.data.humancellatlas.org"

    def __init__(self, deployment):
        self.deployment = deployment

        if self.deployment == 'prod':
            self.ingest_api_url = self.INGEST_API_PROD_URL
        else:
            self.ingest_api_url = self.INGEST_API_URL_TEMPLATE.format(self.deployment)

        self.ingest_auth_agent = IngestAuthAgent()
        self.auth_headers = self.ingest_auth_agent.make_auth_header()

    def submissions(self):
        url = self.ingest_api_url + '/submissionEnvelopes?size=1000'
        response = requests.get(url, headers=self.auth_headers)
        return response.json()['_embedded']['submissionEnvelopes']

    def envelope(self, envelope_id=None, url=None):
        return IngestApiAgent.SubmissionEnvelope(envelope_id=envelope_id, ingest_api_url=self.ingest_api_url,
                                                 auth_headers=self.auth_headers, url=url)

    def get_latest_archive_submission(self, ingest_submission_uuid):
        search_url = f'{self.ingest_api_url}/archiveSubmissions/search/findBySubmissionUuid'
        params = {
            "submissionUuid": ingest_submission_uuid,
            "sort": "created,desc"
        }
        r = requests.get(search_url, headers=self.auth_headers, params=params)
        r.raise_for_status()
        data = r.json()
        archive_submissions = data.get('_embedded', {}).get('archiveSubmissions', [])
        latest_archive_submission = archive_submissions[0] if len(archive_submissions) > 0 else None
        return latest_archive_submission

    class Project:
        def __init__(self, source: dict = {}):
            self._source = deepcopy(source)

        def get_uuid(self):
            uuid = self._source.get('uuid')
            return uuid.get('uuid')  # because uuid's are structured as uuid.uuid in the source JSON

        def get_url(self):
            project_url = self._source.get('_links', {}).get('self', {}).get('href', None)
            return project_url

    class SubmissionEnvelope:

        def __init__(self, envelope_id=None, ingest_api_url=None, auth_headers=None, url=None):
            self.envelope_id = envelope_id
            self.url = url
            self.ingest_api_url = ingest_api_url
            self.data = None
            self.auth_headers = auth_headers
            if envelope_id or url:
                self._load()

        def upload_credentials(self):
            """ Return upload area credentials or None if this envelope doesn't have an upload area yet """
            staging_details = self.data.get('stagingDetails', None)
            if staging_details and 'stagingAreaLocation' in staging_details:
                return staging_details.get('stagingAreaLocation', {}).get('value', None)
            return None

        def reload(self):
            self._load()
            return self

        def status(self):
            return self.data['submissionState']

        def last_spreadsheet_generation_job(self):
            return self.data['lastSpreadsheetGenerationJob'] or {}

        def graph_validation_state(self):
            return self.data['graphValidationState']

        def trigger_graph_validation(self):
            r = requests.put(self.url + '/graphValidationRequestedEvent', headers=self.auth_headers)
            r.raise_for_status()
            return r

        def submit(self, submit_actions=None):
            if not submit_actions:
                submit_actions = []

            submit_url = self.url + '/submissionEvent'
            r = requests.put(submit_url, headers=self.auth_headers, json=submit_actions)
            r.raise_for_status()
            return r

        def disable_indexing(self):
            do_not_index = {'triggersAnalysis': False}
            requests.patch(self.url, data=json.dumps(do_not_index))

        def set_as_update_submission(self):
            do_not_index = {'isUpdate': True}
            r = requests.patch(self.url, data=json.dumps(do_not_index), headers=self.auth_headers)
            r.raise_for_status()
            return r

        def get_files(self):
            return self._get_entity_list('files')

        # TODO deprecate this for retrieve_projects; retain get_projects name but use retrieve_projects logic
        def get_projects(self):
            return self._get_entity_list('projects')

        def retrieve_projects(self):
            """
            Similar to get_projects but returns a list of Project objects instead of raw JSON.
            """
            return [IngestApiAgent.Project(source=source) for source in self.get_projects()]

        def get_protocols(self):
            return self._get_entity_list('protocols')

        def get_processes(self):
            return self._get_entity_list('processes')

        def get_biomaterials(self):
            return self._get_entity_list('biomaterials')

        def get_bundle_manifests(self):
            return self._get_entity_list('bundleManifests')

        def get_submission_manifest(self):
            return self._get_entity('submissionManifest')

        def get_submission_summary(self):
            return self._get_entity('summary')

        def delete(self):
            projects = self.get_projects()
            project = projects[0] if len(projects) > 0 else None

            r = requests.delete(self.url, headers=self.auth_headers, params={"force": True})
            r.raise_for_status()

            if project:
                project_url = project['_links']['self']['href']
                r = requests.delete(project_url, headers=self.auth_headers)
                r.raise_for_status()

        def _get_entity_list(self, entity_type):
            url = self.data['_links'][entity_type]['href']
            r = requests.get(url, headers=self.auth_headers)
            r.raise_for_status()
            files = r.json()
            # TODO won't work for paginated result
            result = files['_embedded'][entity_type] if files.get('_embedded') and files['_embedded'].get(
                entity_type) else []
            return result

        def _get_entity(self, entity_type):
            url = self.data['_links'][entity_type]['href']
            headers = {
                'Content-type': 'application/json',
                'Accept': 'application/json'
            }
            self.auth_headers.update(headers)
            r = requests.get(url, headers=self.auth_headers)

            entity = None
            if r.status_code == requests.codes.ok:
                entity = r.json()
            return entity

        @property
        def uuid(self):
            return self.data['uuid']['uuid']

        def _load(self):
            if not self.url:
                self.url = self.ingest_api_url + f'/submissionEnvelopes/{self.envelope_id}'

            self.data = requests.get(self.url, headers=self.auth_headers).json()


class IngestAuthAgent:
    def __init__(self):
        """This class controls the authentication actions with Ingest Service, including retrieving the token,
         store the token and make authenticated headers. Note:
        """
        gcp_credentials_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        credential = ServiceCredential.from_file(gcp_credentials_file)
        audience = os.environ.get('INGEST_API_JWT_AUDIENCE', 'https://dev.data.humancellatlas.org/')
        self.s2s_token_client = S2STokenClient(credential, audience)
        self.token_manager = TokenManager(token_client=self.s2s_token_client)

    def _get_auth_token(self):
        """Generate self-issued JWT token

        :return string auth_token: OAuth0 JWT token
        """
        auth_token = self.token_manager.get_token()
        return auth_token

    def make_auth_header(self):
        """Make the authorization headers to communicate with endpoints which implement Auth0 authentication API.

        :return dict headers: A header with necessary token information to talk to Auth0 authentication required
        endpoints.
        """
        headers = {
            "Authorization": f"Bearer {self._get_auth_token()}"
        }
        return headers


class IngestArchiverAgent:
    INGEST_ARCHIVER_URL_TEMPLATE = "https://archiver.ingest.{}.archive.data.humancellatlas.org"
    INGEST_ARCHIVER_PROD_URL = "https://archiver.ingest.archive.data.humancellatlas.org"

    def __init__(self, deployment: str, api_key: str, ingest_api_agent: IngestApiAgent):
        self.deployment = deployment
        self.api_key = api_key
        self.ingest_api_agent = ingest_api_agent

        if self.deployment == 'prod':
            self.ingest_archiver_url = self.INGEST_ARCHIVER_PROD_URL
        else:
            self.ingest_archiver_url = self.INGEST_ARCHIVER_URL_TEMPLATE.format(self.deployment)

        self.headers = {
            'Api-Key': self.api_key
        }

    def archive_submission(self, payload: dict):
        archive_submission_url = f'{self.ingest_archiver_url}/archiveSubmissions'
        r = requests.post(archive_submission_url, json=payload, headers=self.headers)
        r.raise_for_status()

    def get_dsp_submission_uuid(self, ingest_submission_uuid):
        archive_submission = self.ingest_api_agent.get_latest_archive_submission(ingest_submission_uuid)
        return archive_submission['dspUuid'] if archive_submission else None

    def get_latest_dsp_submission(self, ingest_submission_uuid):
        find_latest_url = f'{self.ingest_archiver_url}/latestArchiveSubmission/{ingest_submission_uuid}'
        r = requests.get(find_latest_url, headers=self.headers)

        if r.status_code == requests.codes.not_found:
            return None

        archive_submission = r.json()
        return archive_submission if archive_submission else None

    def is_valid_dsp_submission(self, dsp_submission_uuid):
        result = self.get_validation_errors(dsp_submission_uuid)
        errors = result.get('errors')
        pending = result.get('pending')
        return (len(errors) == 0) and (len(pending) == 0)

    def get_validation_errors(self, dsp_submission_uuid):
        get_validation_errors_url = f'{self.ingest_archiver_url}/archiveSubmissions/{dsp_submission_uuid}/validationErrors'
        r = requests.get(get_validation_errors_url, headers=self.headers)
        r.raise_for_status()
        return r.json()

    def complete_submission(self, dsp_submission_uuid):
        complete_url = f'{self.ingest_archiver_url}/archiveSubmissions/{dsp_submission_uuid}/complete'
        r = requests.post(complete_url, headers=self.headers)
        r.raise_for_status()
