import os
import time
from datetime import datetime

from ingest.api.ingestapi import IngestApi

from tests.ingest_agents import IngestBrokerAgent, IngestApiAgent, IngestArchiverAgent
from tests.runners.submission_manager import SubmissionManager
from tests.utils import Progress
from tests.wait_for import WaitFor

RELEASE_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

BIOSAMPLES_PREFIX = 'SAME'
BIOSTUDIES_PREFIX = 'S-BSST'


class DatasetRunner:
    def __init__(self, ingest_broker: IngestBrokerAgent, ingest_api: IngestApiAgent,
                 ingest_archiver: IngestArchiverAgent = None, ingest_client_api: IngestApi = None):
        self.ingest_broker = ingest_broker
        self.ingest_api = ingest_api
        self.ingest_archiver = ingest_archiver
        self.ingest_client_api = ingest_client_api
        self.submission_id = None
        self.submission_envelope = None
        self.dataset = None
        self.submission_manager: SubmissionManager = None
        self.dsp_submission_uuid: str = None

    def valid_run(self, dataset_fixture, project_uuid=None):
        self.dataset = dataset_fixture
        self.upload_spreadsheet_and_create_submission(dataset_fixture, project_uuid)
        self.submission_manager = SubmissionManager(self.submission_envelope)
        self.submission_manager.get_upload_area_credentials()
        self.submission_manager.stage_data_files(self.dataset.config['data_files_upload_area_uuid'])
        self.submission_manager.wait_for_envelope_to_be_validated()

    def direct_archived_run(self, dataset_fixture):
        self.__submit_archive_submission(dataset_fixture)

        payload = self.__create_archive_submission_payload(True)
        self.ingest_archiver.archive_submission(payload)

        self.__check_accessions(self.submission_id)

    def archived_run(self, dataset_fixture):
        self.__submit_archive_submission(dataset_fixture)

        payload = self.__create_archive_submission_payload(False)
        self.ingest_archiver.archive_submission(payload)
        archive_submission = WaitFor(self.ingest_archiver.get_latest_dsp_submission,
                                     self.submission_envelope.uuid).to_return_a_value_other_than(
            other_than_value=None)
        Progress.report(f"DSP SUBMISSION is created {archive_submission['dspUrl']}")
        self.dsp_submission_uuid = archive_submission['dspUuid']

        if self.dsp_submission_uuid:
            WaitFor(self.ingest_archiver.is_valid_dsp_submission, self.dsp_submission_uuid).to_return_value(True)
            Progress.report(f"Completing DSP submission {self.dsp_submission_uuid}...")
            self.ingest_archiver.complete_submission(self.dsp_submission_uuid)

        self.submission_manager.wait_for_envelope_to_be_archived()

    def complete_run(self, dataset_fixture, project_uuid=None):
        self.valid_run(dataset_fixture, project_uuid)
        
        self.submission_manager.graph_validate_envelope()
        self.submission_manager.wait_for_envelope_to_be_graph_valid()

        self.submission_manager.submit_envelope(["Export", "Cleanup"])
        self.submission_manager.wait_for_envelope_to_complete()

    def upload_spreadsheet_and_create_submission(self, dataset_fixture, project_uuid=None):
        spreadsheet_filename = os.path.basename(dataset_fixture.metadata_spreadsheet_path)
        Progress.report(f"CREATING SUBMISSION with {spreadsheet_filename}...")
        self.submission_id = self.ingest_broker.upload(dataset_fixture.metadata_spreadsheet_path,
                                                       project_uuid=project_uuid)
        Progress.report(f"submission is in {self.ingest_api.ingest_api_url}/submissionEnvelopes/{self.submission_id}\n")
        self.submission_envelope = self.ingest_api.envelope(self.submission_id)

    def __submit_archive_submission(self, dataset_fixture):
        self.valid_run(dataset_fixture)
        
        self.submission_manager.graph_validate_envelope()
        self.submission_manager.wait_for_envelope_to_be_graph_valid()

        self.submission_manager.submit_envelope(["Archive"])
        self.submission_manager.wait_for_envelope_to_be_archiving()
        projects = self.submission_envelope.retrieve_projects()
        if len(projects) > 0:
            project = projects[0]
            project_url = project.get_url()
            now = datetime.now()
            r = self.ingest_client_api.patch(project_url, {'releaseDate': now.strftime(RELEASE_DATE_FORMAT)})
            r.raise_for_status()

    def __create_archive_submission_payload(self, is_direct: bool):
        payload = {
            'submission_uuid': self.submission_envelope.uuid,
            'alias_prefix': 'INGEST_INTEGRATION_TEST',
            'exclude_types': 'sequencingRun'
        }

        if is_direct:
            payload['is_direct_archiving'] = True

        return payload

    def __check_accessions(self, submission_id):
        time.sleep(10)
        submission_envelope: IngestApiAgent.SubmissionEnvelope = self.ingest_api.envelope(envelope_id=submission_id)
        biomaterials = submission_envelope.get_biomaterials()
        self.__verify_biosamples_accession(biomaterials)

        project = submission_envelope.get_projects()[0]
        self.__verify_project_accession(project  )

    @staticmethod
    def __verify_project_accession(project):
        project_accessions: str = project['content']['biostudies_accessions']
        assert len(project_accessions) == 1
        project_accession = project_accessions[0]
        assert project_accession.startswith(BIOSTUDIES_PREFIX)

    @staticmethod
    def __verify_biosamples_accession(biomaterials):
        biosamples_accessions = list(map(
            lambda biomaterial: biomaterial['content']['biomaterial_core']['biosamples_accession'],
            biomaterials
        ))
        assert len(biosamples_accessions) == len(biomaterials)
        biosamples_accession: str
        for biosamples_accession in biosamples_accessions:
            assert biosamples_accession.startswith(BIOSAMPLES_PREFIX)
