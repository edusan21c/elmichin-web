# app/blueprints/inventario/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class ProductoForm(FlaskForm):
    # ---------- Datos básicos ----------
    nombre = StringField(
        'Nombre del producto',
        validators=[DataRequired(message='El nombre es obligatorio'), Length(max=200)]
    )
    codigo_barras = StringField(
        'Código de barras',
        validators=[Optional(), Length(max=50)]
    )
    categoria = SelectField(
        'Categoría',
        choices=[
            ('', '-- Sin categoría --'),
            ('dulce', 'Dulce'),
            ('cigarro', 'Cigarrillo'),
            ('bebida', 'Bebida'),
            ('snack', 'Snack / Mecato'),
            ('aseo', 'Aseo'),
            ('licor', 'Licor'),
            ('otro', 'Otro'),
        ],
        validators=[Optional()]
    )

    # ---------- Precios de proveedor ----------
    precio_proveedor = DecimalField(
        'Precio proveedor 1',
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0
    )
    precio_proveedor2 = DecimalField(
        'Precio proveedor 2',
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0
    )
    precio_proveedor3 = DecimalField(
        'Precio proveedor 3',
        validators=[Optional(), NumberRange(min=0)],
        places=2,
        default=0
    )

    # ---------- Precio venta ----------
    porcentaje = DecimalField(
        '% Ganancia',
        validators=[Optional(), NumberRange(min=0, max=500)],
        places=2,
        default=0
    )
    precio_venta = DecimalField(
        'Precio venta base',
        validators=[DataRequired(message='El precio de venta es obligatorio'), NumberRange(min=0)],
        places=2
    )

    # ---------- Descuentos por cantidad ----------
    condicion1 = StringField('Cantidad mínima 1', validators=[Optional(), Length(max=10)])
    precio_venta1 = DecimalField('Precio unitario 1', validators=[Optional(), NumberRange(min=0)], places=2, default=0)

    condicion2 = StringField('Cantidad mínima 2', validators=[Optional(), Length(max=10)])
    precio_venta2 = DecimalField('Precio unitario 2', validators=[Optional(), NumberRange(min=0)], places=2, default=0)

    condicion3 = StringField('Cantidad mínima 3', validators=[Optional(), Length(max=10)])
    precio_venta3 = DecimalField('Precio unitario 3', validators=[Optional(), NumberRange(min=0)], places=2, default=0)

    submit = SubmitField('Guardar')


class StockForm(FlaskForm):
    """Solo para editar el stock de una tienda específica."""
    cantidad = IntegerField(
        'Cantidad en stock',
        validators=[DataRequired(), NumberRange(min=0)]
    )
    submit = SubmitField('Actualizar stock')
