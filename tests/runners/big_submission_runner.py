import copy

from ingest.api.ingestapi import IngestApi
from ingest.utils.token_manager import TokenManager

from tests.ingest_agents import IngestApiAgent
from tests.runners.submission_manager import SubmissionManager

METADATA_COUNT = 1000


class BigSubmissionRunner:
    def __init__(self, deployment, ingest_client_api: IngestApi, token_manager: TokenManager):
        self.deployment = deployment
        self.ingest_client_api = ingest_client_api
        self.submission_manager = None
        self.submission_envelope = None
        self.ingest_api = IngestApiAgent(deployment=deployment)
        self.token_manager = token_manager

    def run(self, metadata_fixture):
        token = self.token_manager.get_token()
        self.ingest_client_api.set_token(f'Bearer {token}')
        submission = self.ingest_client_api.create_submission()
        submission_url = submission["_links"]["self"]["href"]
        self.submission_envelope = self.ingest_api.envelope(envelope_id=None, url=submission_url)

        # TODO just use the test spreadsheet here instead of constructing the json
        # the schema version has a risk of being outdated here
        project = metadata_fixture.project
        biomaterial = metadata_fixture.biomaterial
        file = copy.deepcopy(metadata_fixture.sequence_file)
        file2 = copy.deepcopy(metadata_fixture.sequence_file)
        filename = 'SRR3562314_1.fastq.gz'
        filename2 = 'SRR3562314_2.fastq.gz'
        file['file_core']['file_name'] = filename
        file2['file_core']['file_name'] = filename2

        self.ingest_client_api.create_project(submission_url, project)
        self.ingest_client_api.create_file(submission_url, filename, file)
        self.ingest_client_api.create_file(submission_url, filename2, file2)

        for i in range(METADATA_COUNT):
            self.ingest_client_api.create_entity(submission_url,
                                                 {'content': biomaterial},
                                                 'biomaterials')

        self.submission_manager = SubmissionManager(self.submission_envelope)
        self.submission_manager.wait_for_envelope_metadata_to_be_invalid()
        self.submission_manager.get_upload_area_credentials()
        self.submission_manager.stage_data_files(f'{metadata_fixture.data_files_upload_area_uuid}')
        self.submission_manager.wait_for_envelope_metadata_to_be_validated()
