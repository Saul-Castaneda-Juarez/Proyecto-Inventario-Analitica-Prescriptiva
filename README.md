# 📦 SmartStock

Sistema de **analítica prescriptiva** para reposición de inventario.
Toma ventas, inventario y tiempos de entrega de proveedores y responde:
**¿qué productos hay que reponer y cuántas unidades pedir?**

```
DATOS -> ANÁLISIS -> RESULTADO -> RECOMENDACIÓN -> ACCIÓN
```

## Cómo ejecutarlo

```bash
pip install -r requirements.txt
python src/preparar_datos.py   # Etapa 1: genera data/smartstock.csv (solo la primera vez)
python src/smartstock.py       # Etapas 2-5: análisis, decisión, gráficas y recomendaciones
```

## Estructura

```
SmartStock/
├── data/
│   ├── raw/retail_store_inventory.csv   # dataset original (Kaggle, sintético)
│   ├── proveedores.csv                  # proveedores y tiempos de entrega (supuesto)
│   └── smartstock.csv                   # 100 filas, 8 columnas
├── src/
│   ├── preparar_datos.py                # Etapa 1: construye smartstock.csv
│   └── smartstock.py                    # Etapas 2-5: análisis y recomendación
├── outputs/
│   ├── stock_vs_reorden.png
│   ├── demanda_productos.png
│   ├── cantidades_recomendadas.png
│   ├── estado_por_categoria.png
│   └── recomendaciones.csv
├── README.md
├── requirements.txt
└── .gitignore
```

## Cómo se decide

| Cálculo | Fórmula |
|---|---|
| Demanda durante la entrega | `ventas_diarias × tiempo_entrega` |
| Punto de reorden | `demanda durante la entrega + stock_seguridad` |
| Stock objetivo | `ventas_diarias × 7 días + stock_seguridad` |
| Cantidad a pedir | `stock_objetivo − stock_actual` (mínimo 0; 0 si el estado es SUFICIENTE) |

Estados: **CRÍTICO** (stock ≤ stock de seguridad), **REORDENAR** (stock ≤ punto de reorden), **SUFICIENTE**.

## De dónde salen los datos

`preparar_datos.py` convierte los 73,100 registros diarios del dataset original en una fila por tienda-producto (5 tiendas × 20 productos):

- `ventas_diarias`: promedio de `Units Sold` de los últimos 30 días.
- `stock_actual`, `categoria`, `precio`: valores del último día (2024-01-01).
- `stock_seguridad`: `1.65 × desviación de ventas × √tiempo_entrega` (nivel de servicio del 95 %).
- `producto`: `ID de producto_ID de tienda`, por ejemplo `P0001_S001`.

### Supuestos y límites

- **Proveedores y tiempos de entrega son inventados.** El dataset original no los trae. Se asignaron 5 proveedores ficticios (2 a 6 días) con semilla fija, y los cambias en `PROVEEDORES` dentro de `preparar_datos.py`. Mantén los tiempos por debajo de 7 días, o el stock objetivo quedaría por debajo del punto de reorden.
- **La categoría no es confiable.** En el original cada producto cambia de categoría casi al azar, así que se usa la del último registro.
- **El dataset es sintético.** Sirve para demostrar el método, no para sacar conclusiones de un negocio real.
- **Resultado con estos datos:** casi todo sale CRÍTICO o REORDENAR, porque las ventas diarias varían mucho (0 a 499 unidades) y eso infla el stock de seguridad. Para ver más variedad puedes bajar `Z_SERVICIO` o acortar los tiempos de entrega.
