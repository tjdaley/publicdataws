from wtforms import Form, StringField, TextAreaField, PasswordField, validators


class RegisterForm(Form):
    name = StringField("Name", [validators.DataRequired(), validators.Length(min=1, max=50)])
    email = StringField("Email", [validators.Length(min=6, max=50)])
    password = PasswordField("Password", [
        validators.DataRequired(),
        validators.EqualTo('confirm', "Passwords do no match.")
        ])
    confirm = PasswordField("Confirm password")
    pd_username = StringField("Public Data username", validators=[validators.DataRequired()])
    pd_password = StringField("Public Data password", validators=[validators.DataRequired()])
    zillow_key = StringField("Zillow API key", validators=[validators.DataRequired()])
