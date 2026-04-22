"""
anonymize.py: removes identifying information from a roster, Canvas gradebook, and associated submission
                          Gradescope metadata.

The anonymized data is intended to be in a format as close to the original as possible but with entries for
"Student, Test" and staff removed.

Transformations:
* Data is filtered based on a consent form.
* Staff are implicitly removed since they did not submit a consent form and therefore have not consented.
* Remove "Student, Test" if present in the data. (Separate from above due to missing sid.)

The following Canvas gradebook columns will be masked: Student, ID, SIS User ID, SIS Login ID. The SIS Login ID will be
populated with a random four-digit number, and the order of the rows randomized. In the Gradescope export, the following
fields will be masked: name, sid, email. The sid will be replaced with the same random numbers used to mask the Canvas
gradebook.

Unsupported data:
* Gradescope Short Answer Submissions
* Gradescope Programming Source Code

"""
__author__ = "Ruben Acuna"
__copyright__ = "Copyright 2023-25"

import csv
import os
import random

from anonymize_metadata import anonymize_roster, anonymize_gradebook
from anonymize_submissions import anonymize_gs_prog_yaml
from constants import FOLDER_DATA_PROCESSED, FOLDER_DATA_ORIGINAL


def process(filename_gradebook: str, filename_roster: str, filename_consent: str, filenames_gs_prog: list[str], local_anonymization: bool):
    if not os.path.exists(FOLDER_DATA_PROCESSED):
        os.makedirs(FOLDER_DATA_PROCESSED)

    # generate global anonymized IDs (protocol dependent) for students from gradebook (assumed to exist)
    path_gradebook = FOLDER_DATA_ORIGINAL + os.sep + filename_gradebook
    map_ids = generate_id_map(path_gradebook)

    # determine which students have consented
    path_consent = FOLDER_DATA_ORIGINAL + os.sep + filename_consent
    consented = find_consented(path_consent)

    # process roster
    path_roster = FOLDER_DATA_ORIGINAL + os.sep + filename_roster
    path_roster_clean = FOLDER_DATA_PROCESSED + os.sep + filename_roster[:-4] + "_anonymized.csv"
    df_roster = anonymize_roster(path_roster, path_roster_clean, map_ids, consented)

    # process gradebook
    path_gradebook_clean = FOLDER_DATA_PROCESSED + os.sep + filename_gradebook[:-4] + "_anonymized.csv"
    #output_paths = [path_gradebook_clean]
    if local_anonymization: # regenerate the map so IDs are newly random
        map_ids = generate_id_map(path_gradebook)

    anonymize_gradebook(path_gradebook, path_gradebook_clean, map_ids, consented, df_roster)

    # process gradescope files
    if local_anonymization: # regenerate the map so IDs are newly random
        map_ids = generate_id_map(path_gradebook)

    for filename_gs_prog_zip in filenames_gs_prog:
        path_gs_prog_zip = FOLDER_DATA_ORIGINAL + os.sep + filename_gs_prog_zip

        if os.path.exists(path_gs_prog_zip):
            prefix = FOLDER_DATA_PROCESSED + os.sep + filename_gs_prog_zip[:-4]
            filepath_gs_prog_processed = prefix + "metadata_anonymized.yml"
            anonymize_gs_prog_yaml(path_gs_prog_zip, filepath_gs_prog_processed, map_ids, consented, df_roster)
            #output_paths += [filepath_gs_prog_processed]

    #return output_paths


def generate_id_map(path_gradebook: str) -> dict[int, int]:
    """
    Generates an int to int map from original gradebook IDs to randomly generated four-digit IDs. Used for protocols
    performing global (rather than local) anonymization that preserve the same anonymized ID across multiple items.
    Mapping is stored only in memory and never saved to storage.

    :param path_gradebook: input gradebook.
    :return: dictionary that maps original to anonymized IDs.
    """
    # find number of students
    student_count = 0
    student_ids = []

    with open(path_gradebook) as input_csv:
        reader = csv.DictReader(input_csv)

        # skip header lines (removing two lines due to Canvas export format).
        header = list(next(reader).keys())
        next(reader)  # dummy line

        for row in reader:
            if "Student, Test" in row["Student"]:
                continue

            student_ids.append(row["SIS User ID"])
            student_count += 1

    # generate lookup table of original to anonymized IDs
    masked_ids = [x for x in random.sample(range(1000, 10000), student_count)] # .sample returns unique values
    map_ids = dict()
    for i, id in enumerate(student_ids):
        map_ids[int(id)] = masked_ids[i]

    return map_ids


def find_consented(path_consentform):
    """
    Extracts the (real) IDs for students who consented to participate in research from a consent form spreadsheet.

    We use a double agreement system: students must type their name and select a boolean. To be included, students must
    set the boolean (do you consent) to true and type all or part of their name in the text field.

    :param path_consentform: input consent form Canvas quiz student analysis file.
    :return: A list of (real) consented student IDs.
    """
    consented = []

    with open(path_consentform, encoding='utf-8') as input_csv:
        reader = csv.DictReader(input_csv)
        field_name = find_key("leave blank if", reader.fieldnames)
        field_bool = find_key("Do you consent", reader.fieldnames)

        # only the last attempt counts
        attempts = dict()

        for row in reader:
            attempt = row["attempt"]
            lms_name = row["name"].lower().strip()
            sis_id = int(row["sis_id"])


            q_name = row[field_name].lower().strip()
            q_bool = row[field_bool] == "True"
            consent = False # default

            if not q_name and not q_bool:
                consent = False
            elif q_bool:
                if q_name.lower() == lms_name.lower():
                    consent = True
                    #any(chunk in target for chunk in chunks)
                elif any([x for x in lms_name.split() if x in q_name]):
                    consent = True
                else: # disagreement
                    print(f"WARNING: found {q_name} but name was {lms_name}, consent=True. Assumed did not consent.")
            #else:
            #    print(f"WARNING: found {q_name} but name was {lms_name}, consent={q_bool}.")

            if consent:
                if sis_id not in attempts.keys():
                    attempts[sis_id] = attempt
                    consented.append(sis_id)
                else:
                    if attempt > attempts[sis_id]:
                        attempts[sis_id] = attempt
                        consented.append(sis_id)
                    # otherwise, we see an old attempt that should be superseded.

    return consented


def find_key(substr: str, strings: str) -> str:
    matches = [x for x in strings if substr in x]
    if len(matches) != 1:
        raise Exception(f"Found unexpected number of matches for {substr}.")
    z = matches[0]
    return z


if __name__ == "__main__":

    # inputs must be in a sub-folder called data_original. updated files will be saved to data_original.
    #process("ser222_22sc_gradebook.csv", ["ser222_22sc_m1_submission_metadata.yml"])

    #input: consent results, gradebook, roster, protocol, gradescope data, TODO submissions (?)
    process("ser222_25sc_ground_gradebook.csv",
            "ser222_25sc_ground_roster.csv",
            "ser222_25sc_ground_consentform.csv",
            ["ser222_25sc_ground_m1_prog.zip", "ser222_25sc_ground_m2_prog.zip"],
            False)
