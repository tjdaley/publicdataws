from wtforms import Form, StringField, TextAreaField, PasswordField, validators

class SettingsForm(Form):
    name = StringField("Name", [validators.DataRequired(), validators.Length(min=1, max=50)])
    password = PasswordField("Current password", [
        validators.DataRequired()
        ])
    pd_username = StringField("Public Data username", validators=[validators.DataRequired()])
    pd_password = StringField("Public Data password", validators=[validators.DataRequired()])
    zillow_key = StringField("Zillow API key", validators=[validators.DataRequired()])
