"""Herramientas que Claude puede llamar. Reemplaza los ejemplos por tus sistemas reales."""
from datetime import datetime

TOOLS = [
    {
        "name": "consultar_pedido",
        "description": "Consulta el estado de un pedido por su número.",
        "input_schema": {
            "type": "object",
            "properties": {"numero_pedido": {"type": "string"}},
            "required": ["numero_pedido"],
        },
    },
    {
        "name": "hora_actual",
        "description": "Devuelve la fecha y hora actual del servidor.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def consultar_pedido(numero_pedido: str) -> str:
    # TODO: conectar con tu base de datos / ERP
    return f"Pedido {numero_pedido}: en preparación, entrega estimada en 2 días."


def hora_actual() -> str:
    return datetime.now().isoformat(timespec="minutes")


HANDLERS = {"consultar_pedido": consultar_pedido, "hora_actual": hora_actual}


def run_tool(name: str, args: dict) -> str:
    fn = HANDLERS.get(name)
    if not fn:
        return f"Herramienta desconocida: {name}"
    try:
        return str(fn(**args))
    except Exception as e:  # el error vuelve a Claude para que lo explique
        return f"Error en {name}: {e}"
