"""
AddDiscoveryDocumentForm.py - Add a discovery document

Copyright (c) 2019 by Thomas J. Daley. All Rights Reserved.
"""
from wtforms import Form, StringField, SelectField, validators


class AddDiscoveryDocumentForm(Form):
    court_types_db = [
        'District Court',
        'County Court at Law',
        'Probate Court',
        'Justice Court',
    ]
    court_types_ui = [(i, i) for i in court_types_db]

    discovery_types_db = [
        'PRODUCTION',
        'INTERROGATORIES',
        'ADMISSIONS',
        'DISCLOSURES'
    ]
    discovery_types_ui = [(i, i) for i in discovery_types_db]

    cause_number = StringField(
        "Cause number",
        [validators.DataRequired(), validators.Length(min=1, max=50)]
    )
    county = StringField(
        "County",
        [validators.Length(min=0, max=50)]
    )
    court_type = SelectField(
        'Court type',
        [validators.any_of(court_types_db)],
        choices=court_types_ui
    )
    court_number = StringField(
        'Court number',
        [validators.length(min=1, max=6)]
    )
    discovery_type = SelectField(
        'Discovery type',
        [validators.any_of(discovery_types_db)],
        choices=discovery_types_ui
    )
    requesting_bar_num = StringField(
        "Requestor's Bar number",
        [validators.length(
            min=8,
            max=8,
            message="State bar numbers must be 8 numeric digits."
        )]
    )
    requesting_email = StringField(
        "Requestor's email",
        [validators.DataRequired(), validators.email()]
    )
    requesting_name = StringField("Requesting attorney")
    requesting_license_date = StringField("Licensed since")
    requesting_primary_addr = StringField("Primary location")
    requesting_address = StringField("Office address")
