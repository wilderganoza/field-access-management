"""Traduce un rechazo de la base a algo que se pueda leer en pantalla.

La base tiene la última palabra: unicidad, longitudes, no nulos, claves foráneas
y comprobaciones de tipo se validan ahí, y hay que asumir que a veces dirán no
aunque el formulario pareciera correcto. Lo que no se puede hacer es dejar que
ese no salga como un 500 sin cuerpo: con HTMX eso es una pantalla que no
reacciona, y el usuario no sabe si guardó o no.

El mensaje crudo de psycopg2 trae el SQL entero, el nombre de la restricción y a
veces el valor rechazado. Útil en el registro, ilegible en pantalla, y además
filtra la forma interna de las tablas.

Este archivo es el mismo en Field Data Platform y en Verificación de Permisos.
"""

# Importamos las librerias necesarias
from typing import Optional  # Para el nombre opcional de lo que se guardaba


# Convertimos la excepción en una frase que diga qué corregir
def motivo_de_base(exc: Exception, que: Optional[str] = None) -> str:
    """Lo que hay que arreglar, deducido del tipo de violación.

    `que` es el nombre de lo que se estaba guardando —«caso», «pozo»— para que
    el mensaje hable del objeto y no de la tabla.
    """
    # `orig` es la excepción de psycopg2 cuando viene envuelta por SQLAlchemy
    texto = str(getattr(exc, "orig", exc)).lower()

    # El nombre de lo que se guardaba, para redactar en concreto
    cosa = (que or "registro").lower()

    # Un duplicado en una columna con unicidad
    if "unique" in texto or "duplicate key" in texto:
        return f"Ya existe un {cosa} con esos datos."

    # Una referencia a una fila que no está
    if "foreign key" in texto:
        return ("Alguno de los valores seleccionados ya no existe. "
                "Recarga la pantalla e inténtalo de nuevo.")

    # Un obligatorio que la base exige
    if "not-null" in texto or "null value in column" in texto:
        return "Falta un dato obligatorio."

    # Un texto más largo de lo que admite la columna. Es el caso más frecuente
    # cuando alguien pega contenido desde otro sitio.
    if "too long" in texto or "value too long" in texto:
        return "Alguno de los textos es más largo de lo permitido."

    # Un número, fecha o color mal formado
    if "invalid input syntax" in texto or "invalid text representation" in texto:
        return "Alguno de los valores no tiene el formato correcto."

    # Fuera del rango que admite el tipo
    if "out of range" in texto or "overflow" in texto:
        return "Alguno de los números está fuera del rango admitido."

    # Una comprobación declarada en la tabla
    if "check constraint" in texto:
        return "Alguno de los valores no es válido para su campo."

    # Cualquier otro rechazo: se dice que fue la base, sin volcar el SQL
    return f"No se pudo guardar el {cosa}: la base de datos rechazó los datos."
