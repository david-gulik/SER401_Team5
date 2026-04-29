__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2023-25"

import pandas as pd
import random
import yaml
import zipfile

def anonymize_gs_prog_yaml(filename_input_zip: str, filename_output: str, map_ids: dict[int, int], consented: list[int], df_roster: pd.DataFrame):
    with zipfile.ZipFile(filename_input_zip, 'r') as gs_export:
        test = gs_export.namelist()
        candidates = [x for x in gs_export.namelist() if "submission_metadata.yml" in x]
        if len(candidates) != 1:
            raise Exception(f"Unexpected issue finding YAML metadata. Found: {candidates}")
        filename_input = candidates[0]

        #with zip_ref.open(yaml_path) as file:
        with gs_export.open(filename_input) as file_input:
            submissions = yaml.load(file_input, Loader=yaml.CLoader)
            anonymized = dict()

            for key in submissions.keys():
                current = submissions[key]

                # validation: only one submitter.
                if len(current[":submitters"]) != 1:
                    raise Exception(f"Unexpected number of submitters in {key}.")

                for result in current[":history"]:
                    if len(result[":submitters"]) != 0:
                        raise Exception(f"Unexpected number of submitters in {key}'s :history ({result}).")

                # process only rows for students who consented
                sid = int(current[":submitters"][0][":sid"])
                if sid not in consented:
                    continue

                # anonymize existing record. align with anonymized roster.
                anonymized_id = map_ids[sid]
                df_row = df_roster[df_roster['ID'] == anonymized_id].iloc[0]
                current[":submitters"][0][":sid"] = map_ids[sid]
                current[":submitters"][0][":name"] = f"{df_row["First Name"]} {df_row["Last Name"]}"
                current[":submitters"][0][":email"] = df_row["Zoom Email"]

                # mask out ID in each attempt (they are unique parts of the gradescope URL)
                for i, attempt in enumerate(current[":history"]):
                    new_id = "submission_30" + str(i+1).zfill(3) + str(map_ids[sid])  # see note about key below
                    attempt[":id"] = new_id

                # build new dict with masked keys
                new_key = "submission_30000" + str(map_ids[sid]) # normally "9 random" digits. using fake sid for distinctness.
                anonymized[new_key] = current

            # modern versions of python preserve insert order. need to shuffle
            anonymized_keys = list(anonymized.keys())
            random.shuffle(anonymized_keys)
            anonymized_shuffled = {key: anonymized[key] for key in anonymized_keys}

            with open(filename_output, 'w') as file_submissions_updated:
                yaml.dump(anonymized_shuffled, file_submissions_updated, Dumper=yaml.CDumper)
