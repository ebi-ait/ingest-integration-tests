[![pipeline status](https://gitlab.ebi.ac.uk/hca/ingest-integration-tests/badges/dev/pipeline.svg)](https://gitlab.ebi.ac.uk/hca/ingest-integration-tests/-/commits/dev)


# Ingest Integration Tests
Integration tests for ingest components.

## ingest_to_upload

Tests the flow from spreadsheet upload, data file upload and data file validation and verifies that the submission state will transition to `VALID` when metadata an data files are validated.

<details> 
<summary>See sequence diagram</summary>

```mermaid
sequenceDiagram
  participant TestRunner
  participant Broker
  participant Core
  participant Staging Manager
  participant Validator
  participant State as State Tracker
  participant Upload as Upload Service

  TestRunner->>Broker: uploads test spreadsheet
  Broker-->>Core: creates  metadata entities
  Core-->> Staging Manager: requests for upload area
  Staging Manager-->> Core: returns upload area
  Core-->> Validator: requests for metadata validation
  TestRunner->> Upload Area: using hca-util cli, syncs test files from hca-util to Upload Service's upload area
  Core-->> Validator: requests for file metadata file validation
  Validator-->>Upload: requests for data file validation
  Upload -->> Upload: does file validation
  Upload -->> Core: sets file validation job result
  State -->> Core: sets submission state to VALID
  TestRunner ->> Core: polls until submission is VALID, test passes!
```

</details>
## ingest_to_terra
Tests the submission flow from Ingest to Terra. The test will generate a valid submission, verifies that the submission will be exported by checking that transition to `Exported` state.

<details> 
<summary>See sequence diagram</summary>

```mermaid
sequenceDiagram
  participant TestRunner
  participant Core
  participant Exporter
  participant State as State Tracker
  participant Upload as Upload Service

  TestRunner->>TestRunner: generates a VALID submission
  TestRunner->>Core: triggers exporting
  Core->>Exporter: sends messages per assay
  Exporter->>State: sends messages when a message has been started to process and when it's finished.
  State ->> Core: sets submission state to EXPORTING
  State ->> State: keeps track that all messages are processed
  State ->> Core: sets submission state to EXPORTED
  Exporter->>Terra: submits metadata and data files to the Terra staging area
  TestRunner ->> Core: polls until submission is EXPORTED, test passes!
```
</details>

## ingest_to_archives
Tests the submission flow from Ingest to the EBI public archives. The test will generate a valid submission, verifies that the submission will be archived by checking that transition to `Archived` state.
<details> 
<summary>See sequence diagram</summary>
</details>
## ingest_to_direct_archives
Tests the submission flow from Ingest to the EBI public archives using the new implementation for the Archiver which is not using Data Submission Portal API.
<details> 
<summary>See sequence diagram</summary>
</details>
## bulk_update
Tests the bulk updates process. 
<details> 
<summary>See sequence diagram</summary>
</details>

## Developer Notes

### Running Locally

#### Local Shell Environment

##### Setting Up the Environment
1. Go to local directory where repository is cloned.

```
cd ingest-integration-tests
```

2. The tests require a Python 3 environment to run. Set up a python virtual environment.

3. Install dependencies.

```
pip install -r requirements.txt
```
4. For the tests to be able to successfully authenticate with Ingest Core API, the GCP credentials need to be 
made locally available.

    * Create `_local` directory. The `_local` directory is being ignored by git for this repo. This is to avoid accidentally committing this secret to GitHub.
    If you're not downloading to `_local`, make sure you have Git Secrets set up. See the documentation for setting up and configuring Git Secrets.
    ```
    mkdir _local
    ```
    * The GCP credentials are stored in AWS Secrets Manager; To download GCP credentials and save it into a file, the AWS CLI can be used:
    
    ```
     aws secretsmanager get-secret-value \
     --region us-east-1 \
     --secret-id ingest/dev/gcp-credentials.json | jq -r .SecretString > _local/gcp-credentials-dev.json
    ```

##### Running a Single Test

To run a single test, make sure that all necessary environment variables are provided.

```
export AWS_PROFILE=embl-ebi; \
export DEPLOYMENT_ENV=dev; \
export INGEST_API_JWT_AUDIENCE=https://dev.data.humancellatlas.org/; \
export DEPLOYMENT_STAGE=${DEPLOYMENT_ENV}; \
export ARCHIVER_API_KEY=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id ingest/${DEPLOYMENT_ENV}/secrets --query SecretString --output text | jq -jr '.archiver_api_key'); \
export HCA_UTIL_ADMIN_ACCESS=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id hca/util/aws-access-keys --query SecretString --output text | jq -jr '.ADMIN_ACCESS_KEY'); \
export HCA_UTIL_ADMIN_SECRET=$(aws secretsmanager get-secret-value --region us-east-1 --secret-id hca/util/aws-access-keys --query SecretString --output text | jq -jr '.ADMIN_SECRET_ACCESS_KEY'); \
export HCA_UTIL_ADMIN_PROFILE='test-hca-util-admin'; \
export GOOGLE_APPLICATION_CREDENTIALS=_local/gcp-credentials-dev.json; \
python3 -m unittest tests.test_ingest.TestRun.test_ingest_to_upload
``` 

#### Gitlab Runner

The integration tests are primarily designed to run through the Gitlab CI/CD pipeline mechanism. The tests can be run
through Gitlab locally using `gitlab-runner` that can either be installed or be run as Docker container. Please refer
to [the officially documentation](https://docs.gitlab.com/runner/) for more information.