from anonymize import process

if __name__ == "__main__":
    process(
        "gradebook.csv",
        "roster.csv",
        "consent_form.csv",
        [],
        False,
    )