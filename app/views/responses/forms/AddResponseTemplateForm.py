"""
AddResponseTemplateForm.py - Add an objection template

Copyright (c) 2020 by Thomas J. Daley. All Rights Reserved.
"""
from wtforms import Form, StringField, SelectMultipleField, TextAreaField, validators


class AddResponseTemplateForm(Form):
    discovery_types_db = [
        'PRODUCTION',
        'INTERROGATORIES',
        'ADMISSIONS',
        'DISCLOSURES'
    ]
    discovery_types_ui = [(i, i) for i in discovery_types_db]

    label = StringField(
        "Label",
        [validators.DataRequired(), validators.Length(min=1, max=50)]
    )
    short_text = StringField(
        "Short text",
        [validators.DataRequired()]
    )
    applies_to = SelectMultipleField(
        "Applies to",
        choices=discovery_types_ui,
        # validators=[validators.DataRequired]
    )
    template = TextAreaField(
        "Template",
        [validators.DataRequired(), validators.Length(min=35)]
    )
    created_by = StringField("Created by")
    updated_by = StringField("Last updated by")
