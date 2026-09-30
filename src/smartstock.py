"""
SmartStock — analítica prescriptiva de reposición de inventario.

DATOS -> ANÁLISIS -> RESULTADO -> RECOMENDACIÓN -> ACCIÓN

Uso:  python src/smartstock.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # guarda las gráficas sin abrir ventanas
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "data" / "smartstock.csv"
SALIDAS = RAIZ / "outputs"

DIAS_COBERTURA = 7   # días de venta que queremos cubrir al reponer
TOP_N = 15           # productos que se muestran en las gráficas

COLORES = {"CRÍTICO": "#d62728", "REORDENAR": "#f2b134", "SUFICIENTE": "#2ca02c"}


# ---------------------------------------------------------------- Etapa 1-2: datos
def cargar_datos() -> pd.DataFrame:
    return pd.read_csv(DATOS)


def revisar_datos(df: pd.DataFrame) -> None:
    print("=== REVISIÓN DE DATOS ===")
    print("Filas y columnas:", df.shape)
    print("Valores nulos:", int(df.isnull().sum().sum()))
    print("Duplicados:", int(df.duplicated().sum()))
    print(df.describe().round(1).to_string())
    print()


def limpiar_datos(df: pd.DataFrame) -> pd.DataFrame:
    antes = len(df)
    df = df.drop_duplicates()
    df = df.dropna()
    df = df[(df["stock_actual"] >= 0) & (df["ventas_diarias"] >= 0) & (df["tiempo_entrega"] > 0)]
    print(f"Limpieza: {antes} -> {len(df)} filas\n")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- Etapa 3: decisión
def calcular_reposicion(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["demanda_lead_time"] = df["ventas_diarias"] * df["tiempo_entrega"]
    df["punto_reorden"] = df["demanda_lead_time"] + df["stock_seguridad"]
    df["stock_objetivo"] = df["ventas_diarias"] * DIAS_COBERTURA + df["stock_seguridad"]
    df["estado"] = df.apply(determinar_estado, axis=1)

    df["cantidad_pedir"] = (df["stock_objetivo"] - df["stock_actual"]).clip(lower=0)
    # Si el inventario es suficiente no se pide nada, aunque quede por debajo del objetivo
    df.loc[df["estado"] == "SUFICIENTE", "cantidad_pedir"] = 0
    df["cantidad_pedir"] = df["cantidad_pedir"].round().astype(int)

    df["recomendacion"] = df.apply(generar_recomendacion, axis=1)
    df["demanda_lead_time"] = df["demanda_lead_time"].round(1)
    df["punto_reorden"] = df["punto_reorden"].round(1)
    df["stock_objetivo"] = df["stock_objetivo"].round(1)
    return df


def determinar_estado(fila: pd.Series) -> str:
    if fila["stock_actual"] <= fila["stock_seguridad"]:
        return "CRÍTICO"
    if fila["stock_actual"] <= fila["punto_reorden"]:
        return "REORDENAR"
    return "SUFICIENTE"


def generar_recomendacion(fila: pd.Series) -> str:
    if fila["estado"] == "CRÍTICO":
        return "Comprar inmediatamente"
    if fila["estado"] == "REORDENAR":
        return "Programar pedido"
    return "No comprar"


# ---------------------------------------------------------------- Etapa 4: gráficas
def _barras(df: pd.DataFrame, x: str, titulo: str, xlabel: str, archivo: str) -> None:
    datos = df.sort_values(x).tail(TOP_N)
    colores = [COLORES[e] for e in datos["estado"]]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(datos["producto"], datos[x], color=colores)
    ax.set_title(titulo)
    ax.set_xlabel(xlabel)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in COLORES.values()]
    ax.legend(handles, COLORES.keys(), title="Estado", loc="lower right")
    fig.tight_layout()
    fig.savefig(SALIDAS / archivo, dpi=150)
    plt.close(fig)


def grafica_stock_vs_reorden(df: pd.DataFrame) -> None:
    """Los TOP_N productos con mayor déficit frente al punto de reorden."""
    d = df.assign(deficit=df["punto_reorden"] - df["stock_actual"]).sort_values("deficit").tail(TOP_N)
    fig, ax = plt.subplots(figsize=(10, 6))
    posiciones = range(len(d))
    alto = 0.4
    ax.barh([p + alto / 2 for p in posiciones], d["stock_actual"], height=alto, label="Stock actual", color="#1f77b4")
    ax.barh([p - alto / 2 for p in posiciones], d["punto_reorden"], height=alto, label="Punto de reorden", color="#ff7f0e")
    ax.set_yticks(list(posiciones))
    ax.set_yticklabels(d["producto"])
    ax.set_title(f"Stock actual vs punto de reorden (los {TOP_N} productos con mayor déficit)")
    ax.set_xlabel("Unidades")
    ax.legend()
    fig.tight_layout()
    fig.savefig(SALIDAS / "stock_vs_reorden.png", dpi=150)
    plt.close(fig)


def grafica_demanda(df: pd.DataFrame) -> None:
    _barras(df, "ventas_diarias", f"Demanda diaria: los {TOP_N} productos que más se venden",
            "Ventas diarias (unidades)", "demanda_productos.png")


def grafica_cantidades(df: pd.DataFrame) -> None:
    _barras(df, "cantidad_pedir", f"Cantidad recomendada a pedir: top {TOP_N}",
            "Unidades a pedir", "cantidades_recomendadas.png")


def grafica_estado_por_categoria(df: pd.DataFrame) -> None:
    """Cuántos productos de cada categoría están en cada estado."""
    tabla = df.groupby(["categoria", "estado"]).size().unstack(fill_value=0)
    for estado in COLORES:  # asegura las 3 columnas aunque falte alguna
        if estado not in tabla.columns:
            tabla[estado] = 0
    tabla = tabla[list(COLORES.keys())].sort_values("CRÍTICO", ascending=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    izquierda = pd.Series(0, index=tabla.index)
    for estado, color in COLORES.items():
        ax.barh(tabla.index, tabla[estado], left=izquierda, label=estado, color=color)
        izquierda += tabla[estado]
    ax.set_title("Estado del inventario por categoría")
    ax.set_xlabel("Número de productos")
    ax.legend(title="Estado")
    fig.tight_layout()
    fig.savefig(SALIDAS / "estado_por_categoria.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- Etapa 5: sistema
def mostrar_resumen(df: pd.DataFrame) -> None:
    print("=== RESUMEN DE ESTADOS ===")
    print(df["estado"].value_counts().reindex(["CRÍTICO", "REORDENAR", "SUFICIENTE"], fill_value=0).to_string())
    print(f"\nUnidades totales a pedir: {df['cantidad_pedir'].sum():,}")
    df = df.assign(costo_pedido=df["cantidad_pedir"] * df["precio"])
    print(f"Costo estimado del pedido: ${df['costo_pedido'].sum():,.2f}\n")

    print(f"=== TOP {TOP_N} PEDIDOS MÁS URGENTES ===")
    orden = {"CRÍTICO": 0, "REORDENAR": 1, "SUFICIENTE": 2}
    urgentes = df.assign(o=df["estado"].map(orden)).sort_values(["o", "cantidad_pedir"], ascending=[True, False])
    cols = ["producto", "categoria", "proveedor", "stock_actual", "punto_reorden", "estado", "cantidad_pedir", "recomendacion"]
    print(urgentes[cols].head(TOP_N).to_string(index=False))
    print()

    print("=== PEDIDO POR PROVEEDOR ===")
    por_proveedor = (
        df.groupby("proveedor")
        .agg(productos_a_pedir=("cantidad_pedir", lambda s: int((s > 0).sum())),
             unidades=("cantidad_pedir", "sum"),
             costo_estimado=("costo_pedido", "sum"))
        .round(2)
    )
    print(por_proveedor.to_string())
    print()

    print("=== PEDIDO POR CATEGORÍA ===")
    por_categoria = (
        df.groupby("categoria")
        .agg(total_productos=("producto", "count"),
             criticos=("estado", lambda s: int((s == "CRÍTICO").sum())),
             a_reordenar=("estado", lambda s: int((s == "REORDENAR").sum())),
             unidades_a_pedir=("cantidad_pedir", "sum"),
             costo_estimado=("costo_pedido", "sum"))
        .round(2)
        .sort_values("unidades_a_pedir", ascending=False)
    )
    print(por_categoria.to_string())


def main() -> None:
    SALIDAS.mkdir(exist_ok=True)
    df = cargar_datos()
    revisar_datos(df)
    df = limpiar_datos(df)
    resultado = calcular_reposicion(df)

    grafica_stock_vs_reorden(resultado)
    grafica_demanda(resultado)
    grafica_cantidades(resultado)
    grafica_estado_por_categoria(resultado)

    columnas = [
        "producto", "categoria", "proveedor", "stock_actual", "ventas_diarias", "tiempo_entrega",
        "stock_seguridad", "demanda_lead_time", "punto_reorden", "stock_objetivo",
        "cantidad_pedir", "estado", "recomendacion", "precio",
    ]
    resultado[columnas].to_csv(SALIDAS / "recomendaciones.csv", index=False)

    mostrar_resumen(resultado)
    print(f"\nArchivos guardados en {SALIDAS.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
