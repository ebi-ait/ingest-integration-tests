import subprocess
import time
from urllib.parse import urlparse

from requests import HTTPError

from tests.utils import Progress
from tests.wait_for import WaitFor

MINUTE = 60


class SubmissionManager:

    def __init__(self, submission_envelope):
        self.submission_envelope = submission_envelope
        self.upload_credentials = None

    def get_upload_area_credentials(self):
        Progress.report("WAITING FOR STAGING AREA...")
        self.upload_credentials = WaitFor(
            self._get_upload_area_credentials
        ).to_return_a_value_other_than(other_than_value=None, timeout_seconds=2 * MINUTE)
        Progress.report(" credentials received.\n")

    def _get_upload_area_credentials(self):
        return self.submission_envelope.reload().upload_credentials()

    def stage_data_files(self, files):
        Progress.report("STAGING FILES...\n")
        self._stage_data_files_using_s3_sync(files)

    def _stage_data_files_using_s3_sync(self, files):
        Progress.report("STAGING FILES using hca cli...")
        self.select_upload_area()
        self.upload_files(files)
        self.forget_about_upload_area()

    def select_upload_area(self):
        self._run_command(['hca', 'upload', 'select', self.upload_credentials])

    def upload_files(self, files):
        self._run_command(['hca', 'upload', 'files', files])

    def submit_envelope(self, submit_actions=None):
        self.submission_envelope.submit(submit_actions)

    def forget_about_upload_area(self):
        self.upload_area_uuid = urlparse(self.upload_credentials).path.split('/')[1]
        self._run_command(['hca', 'upload', 'forget', self.upload_area_uuid])

    def wait_for_envelope_to_be_validated(self):
        Progress.report("WAIT FOR VALIDATION...")
        WaitFor(self._envelope_is_in_state, 'Valid').to_return_value(
            value=True)
        Progress.report(" envelope is valid.\n")

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
    def _run_command(cmd_and_args_list, expected_retcode=0):
        retcode = subprocess.call(cmd_and_args_list)
        if retcode != 0:
            raise Exception(
                "Unexpected return code from '{command}', expected {expected_retcode} got {actual_retcode}".format(
                    command=" ".join(cmd_and_args_list), expected_retcode=expected_retcode, actual_retcode=retcode
                )
            )
