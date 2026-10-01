# app/blueprints/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length


class LoginForm(FlaskForm):
    username = StringField(
        'Usuario',
        validators=[DataRequired(message='Ingresa tu usuario'), Length(max=100)]
    )
    password = PasswordField(
        'Contraseña',
        validators=[DataRequired(message='Ingresa tu contraseña')]
    )
    remember = BooleanField('Recordarme')
    submit = SubmitField('Ingresar')
