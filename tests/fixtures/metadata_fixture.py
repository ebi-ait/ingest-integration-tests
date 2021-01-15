from os import path

from tests.fixtures.util import load_file


class MetadataFixture:
    def __init__(self):
        dir_path = path.dirname(path.realpath(__file__))
        self.biomaterial = load_file(f'{dir_path}/metadata/donor_organism.json')
        self.project = load_file(f'{dir_path}/metadata/project.json')
        self.sequence_file = load_file(
            f'{dir_path}/metadata/sequence_file.json')
        self.data_files_upload_area_uuid = "3125f4a0-dda1-40c6-ab69-d27f795f08e1"