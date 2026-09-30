"""
Etapa 1 — Datos
Convierte retail_store_inventory.csv (73,100 filas diarias) en smartstock.csv
(una fila por combinación tienda-producto, 100 filas) con las 8 columnas de SmartStock.

Uso:  python src/preparar_datos.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ / "data" / "raw" / "retail_store_inventory.csv"
SALIDA = RAIZ / "data" / "smartstock.csv"
PROVEEDORES_CSV = RAIZ / "data" / "proveedores.csv"

VENTANA_DIAS = 30      # días recientes usados para promedio y variabilidad de ventas
Z_SERVICIO = 1.65      # nivel de servicio del 95 %
SEMILLA = 42           # para que la asignación de proveedores sea reproducible

# SUPUESTO: el dataset original no trae proveedores ni tiempos de entrega.
# Se definen 5 proveedores ficticios. Ningún tiempo pasa de 6 días para que el
# stock objetivo (7 días de cobertura) siempre quede por encima del punto de reorden.
PROVEEDORES = pd.DataFrame(
    {
        "proveedor": ["Proveedor A", "Proveedor B", "Proveedor C", "Proveedor D", "Proveedor E"],
        "tiempo_entrega": [2, 3, 4, 5, 6],
    }
)


def main() -> None:
    df = pd.read_csv(RAW, parse_dates=["Date"])
    ultima_fecha = df["Date"].max()
    desde = ultima_fecha - pd.Timedelta(days=VENTANA_DIAS - 1)

    # 1) Asignar un proveedor a cada producto (el mismo proveedor en todas las tiendas)
    rng = np.random.default_rng(SEMILLA)
    productos = sorted(df["Product ID"].unique())
    asignacion = pd.DataFrame(
        {"Product ID": productos, "proveedor": rng.choice(PROVEEDORES["proveedor"], size=len(productos))}
    ).merge(PROVEEDORES, on="proveedor")

    # 2) Ventas recientes por tienda-producto
    reciente = df[df["Date"] >= desde]
    ventas = (
        reciente.groupby(["Store ID", "Product ID"])["Units Sold"]
        .agg(ventas_diarias="mean", desviacion="std")
        .reset_index()
    )

    # 3) Foto del último día: stock, categoría y precio
    #    (la categoría del dataset original cambia de un día a otro, por eso se toma la del último registro)
    foto = df[df["Date"] == ultima_fecha][
        ["Store ID", "Product ID", "Category", "Inventory Level", "Price"]
    ].rename(columns={"Category": "categoria", "Inventory Level": "stock_actual", "Price": "precio"})

    out = ventas.merge(foto, on=["Store ID", "Product ID"]).merge(asignacion, on="Product ID")

    # 4) Stock de seguridad = Z * desviación de ventas * raíz(tiempo de entrega)
    out["stock_seguridad"] = (Z_SERVICIO * out["desviacion"] * np.sqrt(out["tiempo_entrega"])).round().astype(int)
    out["ventas_diarias"] = out["ventas_diarias"].round(1)
    out["precio"] = out["precio"].round(2)
    out["producto"] = out["Product ID"] + "_" + out["Store ID"]

    columnas = [
        "producto", "categoria", "stock_actual", "ventas_diarias",
        "tiempo_entrega", "stock_seguridad", "precio", "proveedor",
    ]
    out = out[columnas].sort_values("producto").reset_index(drop=True)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SALIDA, index=False)
    PROVEEDORES.to_csv(PROVEEDORES_CSV, index=False)
    print(f"Listo: {SALIDA.relative_to(RAIZ)} ({len(out)} filas) y {PROVEEDORES_CSV.relative_to(RAIZ)}")
    print(f"Ventana de ventas: {desde.date()} a {ultima_fecha.date()}")


if __name__ == "__main__":
    main()
