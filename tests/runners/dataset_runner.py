import os
import time
from datetime import datetime

from ingest.api.ingestapi import IngestApi

from tests.ingest_agents import IngestBrokerAgent, IngestApiAgent, IngestArchiverAgent
from tests.runners.submission_manager import SubmissionManager
from tests.utils import Progress
from tests.wait_for import WaitFor


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
        self.submission_manager.stage_data_files(self.dataset.config['data_files_location'])
        self.submission_manager.wait_for_envelope_to_be_validated()

    def archived_run(self, dataset_fixture):
        self.valid_run(dataset_fixture)
        self.submission_manager.submit_envelope(["Archive"])
        self.submission_manager.wait_for_envelope_to_be_archiving()

        projects = self.submission_envelope.retrieve_projects()
        if len(projects) > 0:
            project = projects[0]
            project_url = project.get_url()
            now = datetime.now()
            r = self.ingest_client_api.patch(project_url, {'releaseDate': now.strftime('%Y-%m-%dT%H:%M:%SZ')})
            r.raise_for_status()

        self.ingest_archiver.archive_submission(self.submission_envelope.uuid)
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
        self.submission_manager.submit_envelope(["Export", "Cleanup"])
        self.submission_manager.wait_for_envelope_to_complete()

    def upload_spreadsheet_and_create_submission(self, dataset_fixture, project_uuid=None):
        spreadsheet_filename = os.path.basename(dataset_fixture.metadata_spreadsheet_path)
        Progress.report(f"CREATING SUBMISSION with {spreadsheet_filename}...")
        self.submission_id = self.ingest_broker.upload(dataset_fixture.metadata_spreadsheet_path,
                                                       project_uuid=project_uuid)
        Progress.report(f"submission is in {self.ingest_api.ingest_api_url}/submissionEnvelopes/{self.submission_id}\n")
        self.submission_envelope = self.ingest_api.envelope(self.submission_id)
