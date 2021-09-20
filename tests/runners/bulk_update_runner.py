import os
import time
from copy import deepcopy

from openpyxl import load_workbook, Workbook
from openpyxl.worksheet.worksheet import Worksheet

from tests.ingest_agents import IngestBrokerAgent, IngestApiAgent
from tests.runners.bulk_update_manager import BulkUpdateManager
from tests.runners.submission_manager import SubmissionManager
from tests.utils import Progress

MODIFIED_INSDC_ACCESSION_ID = '999'

UI_CHANGE_VALUE = 'UI CHANGE '


class BulkUpdateRunner:
    def __init__(self, ingest_broker: IngestBrokerAgent, ingest_api: IngestApiAgent,
                 bulk_update_manager: BulkUpdateManager):
        self.ingest_broker = ingest_broker
        self.ingest_api = ingest_api
        self.submission_id = None
        self.project_id = None
        self.biomaterial_ids = None
        self.submission_envelope = None
        self.dataset = None
        self.submission_manager: SubmissionManager = None
        self.bulk_update_manager = bulk_update_manager

    def bulk_update_run(self, dataset_fixture):
        self.__import_spreadsheet_with_files(dataset_fixture)
        self.__get_original_content()
        updated_project_description, updated_contributor_name, updated_insdc_accession = \
            self.__modify_metadata_with_api_calls()
        update_spreadsheet, updated_spreadsheet_path = self.__download_modified_spreadsheet()
        updated_project_title, updated_biomaterial_name, modified_biomaterial_id = \
            self.__modify_metadata_in_sheet(update_spreadsheet)
        self.bulk_update_manager.save_modified_spreadsheet(update_spreadsheet, updated_spreadsheet_path)
        self.__upload_modified_spreadsheet(updated_spreadsheet_path)
        self.__validate_modifications(updated_project_description, updated_contributor_name, updated_insdc_accession,
                                      updated_project_title, updated_biomaterial_name)

    def __import_spreadsheet_with_files(self, dataset_fixture, project_uuid=None):
        self.dataset = dataset_fixture
        self.__upload_spreadsheet_and_create_submission(dataset_fixture, project_uuid)
        self.submission_manager = SubmissionManager(self.submission_envelope)
        self.submission_manager.get_upload_area_credentials()
        self.submission_manager.stage_data_files(self.dataset.config['data_files_upload_area_uuid'])
        self.submission_manager.wait_for_envelope_to_be_validated()

    def __upload_spreadsheet_and_create_submission(self, dataset_fixture, project_uuid=None):
        spreadsheet_filename = os.path.basename(dataset_fixture.metadata_spreadsheet_path)
        Progress.report(f"CREATING SUBMISSION with {spreadsheet_filename}...")
        self.submission_id = self.ingest_broker.upload(dataset_fixture.metadata_spreadsheet_path,
                                                       project_uuid=project_uuid)
        Progress.report(f"submission is in {self.ingest_api.ingest_api_url}/submissionEnvelopes/{self.submission_id}\n")
        self.submission_envelope = self.ingest_api.envelope(self.submission_id)

    def __upload_modified_spreadsheet(self, path_to_spreadsheet):
        self.ingest_broker.upload(path_to_spreadsheet, is_update=True)
        self.submission_manager.wait_for_envelope_to_be_validated()

    def __get_original_content(self):
        project_payload = self.__get_project_content()
        self.project_id = self.bulk_update_manager.get_id_from_entity(project_payload)

        self.__get_biomaterial_content_by_id()
        self.biomaterial_ids = [*self.biomaterial_content_by_id]

    def __get_project_content(self):
        project_payload = \
            self.bulk_update_manager.get_entities_by_submission_id_and_type(self.submission_id, 'projects')[0]
        self.project_content = project_payload.get('content')
        return project_payload

    def __get_biomaterial_content_by_id(self):
        biomaterials_payload = \
            self.bulk_update_manager.get_entities_by_submission_id_and_type(self.submission_id, 'biomaterials')
        self.biomaterial_content_by_id = {
            self.bulk_update_manager.get_id_from_entity(payload): payload.get('content')
            for payload in biomaterials_payload
        }

    def __modify_metadata_with_api_calls(self):
        # simulated by REST calls
        project_content_with_ui_modification = deepcopy(self.project_content)
        updated_project_description = UI_CHANGE_VALUE + project_content_with_ui_modification.get('project_core').get(
            'project_description')
        project_content_with_ui_modification['project_core']['project_description'] = updated_project_description
        updated_contributor_name = UI_CHANGE_VALUE + project_content_with_ui_modification['contributors'][0]['name']
        project_content_with_ui_modification['contributors'][0]['name'] = updated_contributor_name
        self.bulk_update_manager.update_content('projects', self.project_id, project_content_with_ui_modification)

        biomaterial_content_with_ui_modification = deepcopy(list(self.biomaterial_content_by_id.values())[0])
        updated_insdc_accession = \
            biomaterial_content_with_ui_modification['biomaterial_core']['insdc_sample_accession'] \
            + MODIFIED_INSDC_ACCESSION_ID
        biomaterial_content_with_ui_modification['biomaterial_core']['insdc_sample_accession'] = updated_insdc_accession
        self.bulk_update_manager.update_content(
            'biomaterials', self.biomaterial_ids[0], biomaterial_content_with_ui_modification)

        return updated_project_description, updated_contributor_name, updated_insdc_accession

    def __download_modified_spreadsheet(self):
        submission_uuid = self.submission_envelope.uuid
        update_spreadsheet_content = self.ingest_broker.download(submission_uuid)
        update_spreadsheet_filename = f'{submission_uuid}.xlsx'
        update_spreadsheet_path = os.path.abspath(os.path.join(os.path.dirname(__file__), update_spreadsheet_filename))
        with open(update_spreadsheet_path, 'wb') as f:
            f.write(update_spreadsheet_content)

        return load_workbook(update_spreadsheet_path), update_spreadsheet_path

    def __modify_metadata_in_sheet(self, workbook: Workbook):
        project_sheet: Worksheet = workbook.get_sheet_by_name('Project')
        updated_project_title = self.bulk_update_manager.update_project_title(project_sheet)

        specimen_sheet: Worksheet = workbook.get_sheet_by_name('Specimen from organism')
        updated_biomaterial_name, modified_biomaterial_id = \
            self.bulk_update_manager.update_biomaterial_name(specimen_sheet)

        return updated_project_title, updated_biomaterial_name, modified_biomaterial_id

    def __validate_modifications(self, updated_project_description, updated_contributor_name, updated_insdc_accession,
                                 updated_project_title, updated_biomaterial_name):
        time.sleep(5)
        self.__get_project_content()

        assert updated_project_description == self.project_content['project_core']['project_description']
        assert updated_project_title == self.project_content['project_core']['project_title']
        assert updated_contributor_name == self.project_content['contributors'][0]['name']

        self.__get_biomaterial_content_by_id()
        biomaterial1_content = self.biomaterial_content_by_id.get(self.biomaterial_ids[0])
        biomaterial2_content = self.biomaterial_content_by_id.get(self.biomaterial_ids[1])
        assert updated_insdc_accession == biomaterial1_content['biomaterial_core']['insdc_sample_accession']
        assert updated_biomaterial_name == biomaterial2_content['biomaterial_core']['biomaterial_name']
