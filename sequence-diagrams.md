# Integration Tests

+ [ingest_to_upload](#ingest_to_upload)
+ [ingest_to_terra](#ingest_to_terra)
+ [ingest_to_archives](#ingest_to_archives)
+ [ingest_to_direct_archives](#ingest_to_direct_archives)
+ [bulk_update](#bulk_update)

### ingest_to_upload

Tests the flow from spreadsheet upload, data file upload and data file validation and verifies that the submission state will transition to `VALID` when metadata an data files are validated.


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
  TestRunner->> Upload Area: using hca-util cli, <br/> syncs test files from hca-util to Upload Service's upload area
  Core-->> Validator: requests for file metadata file validation
  Validator-->>Upload: requests for data file validation
  Upload -->> Upload: does file validation
  Upload -->> Core: sets file validation job result
  State -->> Core: sets submission state to VALID
  TestRunner ->> Core: polls until submission is VALID, test passes!
```

### ingest_to_terra
Tests the submission flow from Ingest to Terra. The test will generate a valid submission, verifies that the submission will be exported by checking that transition to `Exported` state.
```mermaid
sequenceDiagram
  participant TestRunner
  participant Core
  participant Exporter
  participant State as State Tracker
  participant GCPTS as GCP Transfer Service

  TestRunner->>TestRunner: generates a VALID submission
  TestRunner->>Core: triggers exporting
  Core->>Exporter: sends messages per assay
  Exporter->>State: sends messages when a message is being processed <br/> and when it's finished.
  State ->> Core: sets submission state to EXPORTING
  State ->> State: keeps track that all messages are processed
  State ->> Core: sets submission state to EXPORTED
  Exporter->>GCPTS: triggers data file transfer
  GCPTS->Terra: transfers data files to Terra staging area
  Exporter->>Terra: creates metadata files to the Terra staging area
  TestRunner ->> Core: polls until submission is EXPORTED, test passes!
```
### ingest_to_archives
Tests the submission flow from Ingest to the EBI public archives. The test will generate a valid submission, verifies that the submission will be archived by checking that transition to `Archived` state.

```mermaid
sequenceDiagram
  participant TestRunner
  participant Core
  participant Exporter
  participant State as State Tracker
  participant Archiver
  participant DSP

  TestRunner->>TestRunner: generates a VALID submission
  TestRunner-->>Core: triggers creation of 'assay' manifests
  Core->>Exporter: sends messages per assay
  Exporter->>Exporter: generates bundle manifests
  Exporter->>State: sends messages when a message is processing <br/> and when it's finished.
  State ->> Core: sets submission state to PROCESSING
  State ->> State: keeps track that all messages are processed
  State ->> Core: sets submission state to ARCHIVING
  TestRunner-->>Archiver: triggers archiving
  Archiver->>Archiver: converts metadata
  Archiver-->>DSP: creates submission and <br/> creates metadata (no data because data upload is manual)
  Archiver->>DSP: wait for the DSP submission to be valid and submittable
  Archiver->>DSP: submits submission
  Archiver-->>DSP: retrieves accession
  Archiver-->>Core: updates accessions
  Archiver-->>Core: sets status to Archived
  TestRunner ->> Core: polls until submission is ARCHIVED, test passes!
```
### ingest_to_direct_archives
Tests the submission flow from Ingest to the EBI public archives using the new implementation for the Archiver which is not using Data Submission Portal API.

```mermaid
sequenceDiagram
  participant TestRunner
  participant Core
  participant Exporter
  participant State as State Tracker
  participant Archiver

  TestRunner->>TestRunner: generates a VALID submission
  TestRunner-->>Core: triggers creation of 'assay' manifests
  Core->>Exporter: sends messages per assay
  Exporter->>Exporter: generates bundle manifests
  Exporter->>State: sends messages when a message is processing <br/> and when it's finished.
  State ->> Core: sets submission state to PROCESSING
  State ->> State: keeps track that all messages are processed
  State ->> Core: sets submission state to ARCHIVING
  TestRunner-->>Archiver: triggers archiving
  Archiver->>Archiver: converts metadata
  Archiver-->>BioStudies: converts and sends project metadata
  Archiver->>BioSamples: converts and sends samples
  Archiver->>ENA: converts and sends samples
  Archiver-->>Core: updates accessions
  Archiver-->>Core: sets status to Archived
  TestRunner ->> Core: polls until submission is ARCHIVED, test passes!
```
### bulk_update
Tests the bulk updates flow. 

```mermaid
sequenceDiagram
  participant TestRunner
  participant Core
  participant Broker
  
  TestRunner->>Broker: uploads a spreadsheet
  TestRunner->>Core: updates metadata
  TestRunner-->>Broker: generate spreadsheet for download
  Broker->>Core: Gets data 
  Broker->>Broker: Flattens metadata and generate spreadsheet
  TestRunner-->>Core: polls to know if spreadsheet generation finished
  TestRunner->>Broker: downloads spreadsheet
  TestRunner->>TestRunner: updates metadata in spreadsheet
  TestRunner->>Broker: uploads spreadsheet
  Broker->>Broker: imports updates
  Broker-> Core: do updates
  TestRunner->> Core: polls until all updates were done, test passes!
```