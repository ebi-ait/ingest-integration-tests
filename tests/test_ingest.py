#!/usr/bin/env python3
import os
import unittest

from ingest.api.ingestapi import IngestApi
from ingest.utils.s2s_token_client import S2STokenClient
from ingest.utils.token_manager import TokenManager

from tests.fixtures.dataset_fixture import DatasetFixture
from tests.fixtures.metadata_fixture import MetadataFixture
from tests.ingest_agents import IngestBrokerAgent, IngestApiAgent
from tests.runners.big_submission_runner import BigSubmissionRunner
from tests.runners.dataset_runner import DatasetRunner

DEPLOYMENTS = ('dev', 'integration', 'staging', 'prod')


class TestIngest(unittest.TestCase):

    def setUp(self):
        self.deployment = os.environ.get('DEPLOYMENT_ENV', None)
        self.no_cleanup = os.environ.get('NO_CLEANUP', False)

        if self.deployment not in DEPLOYMENTS:
            raise RuntimeError(f'DEPLOYMENT_ENV environment variable must be one of {DEPLOYMENTS}')

        if self.deployment == 'prod':
            self.ingest_api_url = f"https://api.ingest.archive.data.humancellatlas.org"
        else:
            self.ingest_api_url = f"https://api.ingest.{self.deployment}.archive.data.humancellatlas.org"

        self.ingest_client_api = IngestApi(url=self.ingest_api_url)
        self.s2s_token_client = S2STokenClient()
        gcp_credentials_file = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        self.s2s_token_client.setup_from_file(gcp_credentials_file)
        self.token_manager = TokenManager(self.s2s_token_client)

        self.ingest_broker = IngestBrokerAgent(self.deployment)
        self.ingest_api = IngestApiAgent(deployment=self.deployment)
        self.runner = None

    def ingest_and_upload_only(self, dataset_name):
        dataset_fixture = DatasetFixture(dataset_name, self.deployment)
        runner = DatasetRunner(self.deployment)
        runner.valid_run(dataset_fixture)
        self.runner = runner
        return runner

    def ingest_to_archives(self, dataset_name):
        dataset_fixture = DatasetFixture(dataset_name, self.deployment)
        runner = DatasetRunner(self.deployment)
        runner.valid_run(dataset_fixture)
        self.runner = runner
        return runner

    def ingest_to_terra(self, dataset_name):
        dataset_fixture = DatasetFixture(dataset_name, self.deployment)
        runner = DatasetRunner(self.deployment)
        runner.valid_run(dataset_fixture)
        # TODO implement test
        self.runner = runner
        return runner

    def ingest_big_submission(self):
        metadata_fixture = MetadataFixture()
        runner = BigSubmissionRunner(self.deployment, self.ingest_client_api, self.token_manager)
        runner.run(metadata_fixture)
        self.runner = runner

    def tearDown(self) -> None:
        if not self.no_cleanup:
            self.runner.submission_envelope.delete()


class TestRun(TestIngest):

    def test_ss2_ingest_to_upload(self):
        runner = self.ingest_and_upload_only('SS2')

    def test_big_submission_run(self):
        self.ingest_big_submission()

    def test_archiving(self):
        runner = self.ingest_to_archives()

    def test_exporting(self):
        runner = self.ingest_to_terra()


if __name__ == '__main__':
    unittest.main()
