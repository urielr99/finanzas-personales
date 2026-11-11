import streamlit as st
import pandas as pd
from datetime import date
import io
import json
from streamlit_local_storage import LocalStorage
st.set_page_config(
    page_title="Finanzas Personales",
    page_icon="",
    layout="wide"
)

categorias = ["Comidas", "Transporte", "Salud", "Ocio", "Hogar", "Otros"]

def leer_archivo(archivo):
    if archivo.name.lower().endswith(".xlsx"):
        return pd.read_excel(archivo)
    return pd.read_csv(archivo)


def a_fecha(valor):
    # funciona con texto ("2026-11-01") y con fechas de Excel
    return pd.to_datetime(valor).date()


def df_a_excel(df):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transacciones")
        hoja = writer.sheets["Transacciones"]

        for columna in hoja.columns:
            ancho = max(len(str(celda.value)) if celda.value is not None else 0 for celda in columna)
            hoja.column_dimensions[columna[0].column_letter].width = ancho + 3

    return buffer.getvalue()


class Transaccion:
    def __init__(self, descripcion, monto, fecha, categoria, tipo):
        self.descripcion = descripcion
        self.monto = float(monto)
        self.fecha = fecha
        self.categoria = categoria
        self.tipo = tipo

    def es_gasto(self):
        return self.tipo == "Gasto"

    def es_ingreso(self):
        return self.tipo == "Ingreso"

    def a_diccionario(self):
        return {
            "descripcion": self.descripcion,
            "monto": self.monto,
            "fecha": self.fecha,
            "categoria": self.categoria,
            "tipo": self.tipo
        }


class Cartera:
    def __init__(self, transacciones=None):
        self.transacciones = transacciones if transacciones is not None else []
    def a_json(self):
        return json.dumps([
            {**t.a_diccionario(), "fecha": t.fecha.isoformat()}
            for t in self.transacciones
        ])

    @classmethod
    def desde_datos(cls, datos):
        return cls([
            Transaccion(
                d["descripcion"],
                d["monto"],
                date.fromisoformat(d["fecha"]),
                d["categoria"],
                d["tipo"]
            )
            for d in datos
        ])
    def eliminar_transaccion(self, transaccion):
        self.transacciones.remove(transaccion)

    def agregar_transaccion(self, transaccion):
        self.transacciones.append(transaccion)

    def esta_vacia(self):
        return len(self.transacciones) == 0

    def a_lista_diccionarios(self):
        return [transaccion.a_diccionario() for transaccion in self.transacciones]

    def ingresos(self):
        return sum(
            transaccion.monto
            for transaccion in self.transacciones
            if transaccion.es_ingreso()
        )

    def gastos(self):
        return sum(
            transaccion.monto
            for transaccion in self.transacciones
            if transaccion.es_gasto()
        )

    def balance(self):
        return self.ingresos() - self.gastos()

    def gasto_promedio(self):
        gastos = [
            transaccion.monto
            for transaccion in self.transacciones
            if transaccion.es_gasto()
        ]

        return sum(gastos) / len(gastos) if gastos else 0

    def filtrar(self, categorias_seleccionadas, fecha_desde, fecha_hasta):
        transacciones_filtradas = []

        for transaccion in self.transacciones:
            if transaccion.categoria in categorias_seleccionadas and fecha_desde <= transaccion.fecha <= fecha_hasta:
                transacciones_filtradas.append(transaccion)

        return Cartera(transacciones_filtradas)

    def gastos_por_categoria(self):
        gastos_por_categoria = {}

        for transaccion in self.transacciones:
            if transaccion.es_gasto():
                categoria = transaccion.categoria
                monto = transaccion.monto

                if categoria not in gastos_por_categoria:
                    gastos_por_categoria[categoria] = 0
                gastos_por_categoria[categoria] += monto

        return gastos_por_categoria

    def gastos_por_fecha(self):
        gastos_por_fecha = {}

        for transaccion in self.transacciones:
            if transaccion.es_gasto():
                fecha = transaccion.fecha
                monto = transaccion.monto

                if fecha not in gastos_por_fecha:
                    gastos_por_fecha[fecha] = 0
                gastos_por_fecha[fecha] += monto

        return gastos_por_fecha

    def fechas(self):
        return [transaccion.fecha for transaccion in self.transacciones]

CLAVE_STORAGE = "finanzas_cartera"


def sincronizar_navegador():
    almacenamiento = LocalStorage()

    # 1. Restaurar lo que haya en el navegador (solo una vez por sesión)
    if not st.session_state.get("restaurado"):
        guardado = almacenamiento.getItem(CLAVE_STORAGE)

        if guardado:
            try:
                datos = json.loads(guardado) if isinstance(guardado, str) else guardado
                st.session_state.cartera = Cartera.desde_datos(datos)
                st.session_state.restaurado = True
                st.session_state.ultimo_guardado = st.session_state.cartera.a_json()
                st.rerun()
            except (ValueError, KeyError, TypeError):
                pass  # dato corrupto: se ignora y se empieza de cero

    # 2. Guardar solo si algo cambió
    cartera = st.session_state.cartera
    actual = cartera.a_json()

    if actual != st.session_state.get("ultimo_guardado"):
        # no pisar el navegador con una cartera vacía antes de haber restaurado
        if st.session_state.get("restaurado") or not cartera.esta_vacia():
            almacenamiento.setItem(CLAVE_STORAGE, actual, key="ls_set")
            st.session_state.ultimo_guardado = actual
            st.session_state.restaurado = True

def aplicar_estilos():
    st.markdown("""
        <style>
        [data-testid="stMetric"] {
            background-color: #1e293b;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }
        [data-testid="stMetricValue"] {
            font-size: 1.6rem;
        }
        [data-testid="stMetricValue"] div {
            overflow: visible !important;
            text-overflow: clip !important;
            white-space: nowrap !important;
        }
        .stButton > button, .stDownloadButton > button {
            border-radius: 8px;
        }
        </style>
    """, unsafe_allow_html=True)
def mostrar_titulos():
    st.title("Finanzas Personales")
    st.write("Lleva el control de tus gastos e ingresos")


def inicializar_estado():
    if "cartera" not in st.session_state:
        st.session_state.cartera = Cartera()


def mostrar_formulario():
    with st.form("nueva_transaccion"):
        descripcion = st.text_input("Descripción del gasto o ingreso", placeholder="Escribe la descripción de la operación")
        monto = st.number_input("Monto", step=1.0, min_value=0.0, format="%0.2f")
        fecha = st.date_input("Fecha")
        categoria = st.selectbox("categoría", categorias)
        tipo = st.radio("Tipo", ["Ingreso", "Gasto"], horizontal=True)
        enviado = st.form_submit_button("Enviar")

    if enviado:
        transaccion = Transaccion(descripcion, monto, fecha, categoria, tipo)
        st.session_state.cartera.agregar_transaccion(transaccion)
        st.success("Transacción agregada con éxito")


def importar_archivo():
    with st.expander("Importar desde CSV o Excel"):
        archivo = st.file_uploader("Archivo", type=["csv", "xlsx"])
        importar = st.button("Importar transacciones")

        if importar:
            if archivo is None:
                st.warning("Primero sube un archivo")
                return

            try:
                df = leer_archivo(archivo)
            except Exception:
                st.error("El archivo no es válido")
                return

            columnas_esperadas = ["descripcion", "monto", "fecha", "categoria", "tipo"]

            for columna in columnas_esperadas:
                if columna not in df.columns:
                    st.error("El archivo debe contener las columnas: descripcion, monto, fecha, categoria, tipo")
                    return

            transacciones_importadas = 0

            for _, fila in df.iterrows():
                transaccion = Transaccion(
                    fila["descripcion"],
                    float(fila["monto"]),
                    a_fecha(fila["fecha"]),
                    fila["categoria"],
                    fila["tipo"]
                )

                st.session_state.cartera.agregar_transaccion(transaccion)
                transacciones_importadas += 1

            st.success(f"Se importaron {transacciones_importadas} transacciones")


def mostrar_filtros():
    categorias_seleccionadas = st.multiselect("Categorías", categorias, default=categorias)

    if not st.session_state.cartera.esta_vacia():
        fechas = st.session_state.cartera.fechas()
        fecha_desde_default = min(fechas)
        fecha_hasta_default = max(fechas)
    else:
        fecha_desde_default = date.today()
        fecha_hasta_default = date.today()

    fecha_desde = st.date_input("Desde", value=fecha_desde_default)
    fecha_hasta = st.date_input("Hasta", value=fecha_hasta_default)

    return categorias_seleccionadas, fecha_desde, fecha_hasta


def mostrar_transacciones(cartera):
    st.subheader("Transacciones registradas:")

    if cartera.esta_vacia():
        st.info("No hay transacciones registradas")
        return

    df = pd.DataFrame(cartera.a_lista_diccionarios())
    df.insert(0, "N°", range(1, len(df) + 1))
    seleccion = st.dataframe(
        df,
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        key="tabla_transacciones"
    )
    filas = [i for i in seleccion.selection.rows if i < len(cartera.transacciones)]


    if filas:
        if st.button(f"Eliminar {len(filas)} seleccionada(s)", type="primary"):
            for i in filas:
                st.session_state.cartera.eliminar_transaccion(cartera.transacciones[i])
            st.rerun()
    df_descarga = df.drop(columns="N°")
    st.download_button(
        "Descargar CSV",
        data=df_descarga.to_csv(index=False),
        file_name="mis_transacciones.csv",
        mime="text/csv"
    )

    st.download_button(
        "Descargar Excel",
        data=df_a_excel(df_descarga),
        file_name="mis_transacciones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def mostrar_resumen(cartera):
    if cartera.esta_vacia():
        st.info("No hay transacciones registradas")
        return

    columna_ingresos, columna_gastos, columna_balance, columna_gasto_promedio = st.columns(4)

    columna_ingresos.metric("Ingresos", f"${cartera.ingresos():.2f}")
    columna_gastos.metric("Gastos", f"${cartera.gastos():.2f}")
    columna_balance.metric("Balance", f"${cartera.balance():.2f}")
    columna_gasto_promedio.metric("Gasto promedio", f"${cartera.gasto_promedio():.2f}")


def mostrar_analisis(cartera):
    gastos_por_categoria = cartera.gastos_por_categoria()
    gastos_por_fecha = cartera.gastos_por_fecha()

    if not gastos_por_categoria:
        st.info("No hay gastos registrados")
        return

    datos_categorias = []
    for categoria, monto in gastos_por_categoria.items():
        datos_categorias.append({
            "categoria": categoria,
            "monto": monto
        })

    datos_fechas = []
    for fecha in sorted(gastos_por_fecha):
        datos_fechas.append({
            "fecha": fecha,
            "monto": gastos_por_fecha[fecha]
        })

    df_categorias = pd.DataFrame(datos_categorias)
    df_fechas = pd.DataFrame(datos_fechas)

    st.subheader("Gastos por categoría")
    st.bar_chart(df_categorias, x="categoria", y="monto")

    st.subheader("Gastos por fecha")
    st.line_chart(df_fechas, x="fecha", y="monto")


mostrar_titulos()
aplicar_estilos()
inicializar_estado()

with st.sidebar:
    mostrar_formulario()
    importar_archivo()
    categorias_seleccionadas, fecha_desde, fecha_hasta = mostrar_filtros()

cartera_filtrada = st.session_state.cartera.filtrar(
    categorias_seleccionadas,
    fecha_desde,
    fecha_hasta
)

tab_resumen, tab_movimientos, tab_analisis = st.tabs(["Resumen", "Movimientos", "Análisis"])

with tab_resumen:
    mostrar_resumen(cartera_filtrada)

with tab_movimientos:
    mostrar_transacciones(cartera_filtrada)

with tab_analisis:
    mostrar_analisis(cartera_filtrada)

sincronizar_navegador()