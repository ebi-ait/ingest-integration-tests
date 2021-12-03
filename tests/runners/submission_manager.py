import os
import subprocess
import time
from urllib.parse import urlparse

from requests import HTTPError

from tests.utils import Progress
from tests.wait_for import WaitFor

from tests.utils import run_command

MINUTE = 60

HCA_UTIL_ADMIN_PROFILE = os.environ.get('HCA_UTIL_ADMIN_PROFILE')
HCA_UTIL_ADMIN_ACCESS = os.environ.get('HCA_UTIL_ADMIN_ACCESS')
HCA_UTIL_ADMIN_SECRET = os.environ.get('HCA_UTIL_ADMIN_SECRET')


class SubmissionManager:

    def __init__(self, submission_envelope):
        self.submission_envelope = submission_envelope
        self.upload_credentials = None

    def spreadsheet_imported(self):
        manifest = self.submission_envelope.get_submission_manifest()
        summary = self.submission_envelope.get_submission_summary()
        return manifest and summary and \
               manifest.get('expectedBiomaterials', 0) == summary.get('totalBiomaterials', 0) and \
               manifest.get('expectedFiles', 0) == summary.get('totalFiles', 0) and \
               manifest.get('expectedProtocols', 0) == summary.get('totalProtocols', 0) and \
               manifest.get('expectedProcesses', 0) == summary.get('totalProcesses', 0) and \
               manifest.get('actualLinks', 0) == manifest.get('expectedLinks', 0)

    def get_upload_area_credentials(self):
        Progress.report("WAITING FOR STAGING AREA...")
        self.upload_credentials = WaitFor(
            self._get_upload_area_credentials
        ).to_return_a_value_other_than(other_than_value=None, timeout_seconds=2 * MINUTE)
        Progress.report(" credentials received.\n")

    def _get_upload_area_credentials(self):
        return self.submission_envelope.reload().upload_credentials()

    def stage_data_files(self, upload_area_uuid):
        Progress.report("STAGING FILES...\n")
        self._stage_data_files_using_s3_sync(upload_area_uuid)

    def _stage_data_files_using_s3_sync(self, upload_area_uuid):
        Progress.report("STAGING FILES using hca-util cli...")
        self._run_command(
            f'hca-util config {HCA_UTIL_ADMIN_ACCESS} {HCA_UTIL_ADMIN_SECRET} --profile {HCA_UTIL_ADMIN_PROFILE}',
            verbose=False)
        self._run_command(f'hca-util select {upload_area_uuid} --profile {HCA_UTIL_ADMIN_PROFILE}')
        self._run_command(f'hca-util sync {self.upload_credentials} --profile {HCA_UTIL_ADMIN_PROFILE}')

    def validate_envelope_graph(self):
        self.submission_envelope.triggerGraphValidation()

    def submit_envelope(self, submit_actions=None):
        self.submission_envelope.submit(submit_actions)

    def wait_for_envelope_to_be_imported(self):
        Progress.report("WAIT FOR IMPORTING...")
        WaitFor(self.spreadsheet_imported).to_return_value(
            value=True)
        Progress.report("spreadsheet is imported.\n")

    def wait_for_envelope_to_be_validated(self):
        Progress.report("WAIT FOR VALIDATION...")
        WaitFor(self._envelope_is_in_state, 'Valid').to_return_value(
            value=True)
        Progress.report(" envelope is valid.\n")

    def wait_for_envelope_to_have_valid_graph(self):
        Progress.report("WAIT FOR GRAPH VALIDATION...")
        WaitFor(self._envelope_has_graph_validation_state, 'Valid').to_return_value(value=True)
        Progress.report(" envelope graph validation state is valid.\n")

    def wait_for_envelope_to_be_submitted(self):
        Progress.report("WAIT FOR SUBMITTED...")
        WaitFor(self._envelope_is_in_state, 'Submitted').to_return_value(
            value=True)
        Progress.report(" envelope is submitted.\n")

    def wait_for_envelope_to_be_archiving(self):
        Progress.report("WAIT FOR ARCHIVING...")
        WaitFor(self._envelope_is_in_state, 'Archiving').to_return_value(
            value=True)
        Progress.report(" envelope is in Archiving.\n")

    def wait_for_envelope_to_be_archived(self):
        Progress.report("WAIT FOR ARCHIVED...")
        WaitFor(self._envelope_is_in_state, 'Archived').to_return_value(
            value=True)
        Progress.report(" envelope is in Archived.\n")

    def wait_for_envelope_to_be_exported(self):
        Progress.report("WAIT FOR EXPORTED...")
        WaitFor(self._envelope_is_in_state, 'Exported').to_return_value(
            value=True)
        Progress.report(" envelope is in Exported.\n")

    def wait_for_envelope_to_be_in_draft(self):
        Progress.report("WAIT FOR VALIDATION...")
        WaitFor(self._envelope_is_in_state, 'Draft').to_return_value(
            value=True)
        Progress.report(" envelope is in Draft.\n")

    def wait_for_envelope_to_be_invalid(self):
        Progress.report("WAIT FOR VALIDATION...")
        WaitFor(self._envelope_is_in_state, 'Invalid').to_return_value(
            value=True)
        Progress.report(" envelope is in Invalid.\n")

    def wait_for_envelope_to_complete(self):
        Progress.report("WAIT FOR COMPLETE...")
        WaitFor(self._envelope_is_in_state, 'Complete').to_return_value(
            value=True)
        Progress.report(" envelope is in Complete.\n")

    def _envelope_is_in_state(self, state):
        envelope_status = self.submission_envelope.reload().status()
        Progress.report(f"envelope status is {envelope_status}")
        return envelope_status in [state]

    def _envelope_has_graph_validation_state(self, state):
        graph_validation_state = self.submission_envelope.reload().graphValidationState()
        Progress.report(f"Envelope graph validation state is {graph_validation_state}")
        return graph_validation_state == state

    def ensure_submitted(self):
        try:
            self.submit_envelope()
            if self._envelope_is_in_state('Submitted'):
                return
            else:
                time.sleep(1)
                return self.ensure_submitted()
        except HTTPError:
            if self._envelope_is_in_state('Submitted'):
                return
            else:
                raise

    @staticmethod
    def _run_command(cmd: str, expected_retcode=0, verbose=True):
        retcode, output, error = run_command(cmd, verbose=verbose)
        if retcode != 0:
            raise Exception(f"Unexpected return code from '{cmd}', expected {expected_retcode} got {retcode}")
