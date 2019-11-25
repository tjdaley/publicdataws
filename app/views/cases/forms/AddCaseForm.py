from wtforms import Form, StringField, TextAreaField, PasswordField, validators

class AddCaseForm(Form):
    cause_number = StringField("Cause number", [validators.DataRequired(), validators.Length(min=1, max=50)])
    description = StringField("Description", [validators.DataRequired(), validators.Length(min=1, max=50)])
    us_state = StringField("State", [validators.Length(min=2, max=2)])
    county = StringField("County", [validators.Length(min=0, max=50)])
    case_type = StringField("Case type", [validators.Length(min=0, max=50)])
    created_by = StringField("Created by")
    time_str = StringField("Create date")

