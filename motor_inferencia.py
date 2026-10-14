"""
Motor de inferencia – P9 Mesa de ayuda para fallas de red y computadores
Sistema experto basado en casos (RBC) · Inteligencia Artificial – Grupo B · USAT 2026

Lee la base de conocimientos de la carpeta «base_conocimientos/» (archivos JSON) y ejecuta
el ciclo de cuatro pasos de Aamodt y Plaza [8]:

    1. RECUPERAR  – compara el ticket nuevo con los casos VALIDADOS y devuelve los k más similares.
    2. REUTILIZAR – propone la solución del caso recuperado y la adapta con las reglas R1–R5.
    3. REVISAR    – el técnico confirma si la solución funcionó y el usuario da su conformidad.
    4. RETENER    – con la clave de administrador, refuerza un caso existente o crea uno nuevo
                    (queda «Pendiente» hasta que se le agregue su respaldo documental).

Cómo se justifica cada decisión
  * Fuentes METODOLÓGICAS [1]–[12] (fuentes.json → "metodologicas"): justifican CÓMO razona el motor.
    [1]–[11] tienen la misma numeración que los archivos cita 1 … cita 11 del equipo.
  * Fuentes TÉCNICAS T01–Tnn (fuentes.json → "tecnicas"): documentación oficial verificada que
    valida el CONTENIDO de cada caso (síntoma, causa y solución). Cada caso guarda en
    "validacion.respaldo" la fuente, la sección y el fragmento literal que lo respalda.
  * Los VALORES numéricos (pesos, umbrales, k) son decisiones de diseño del equipo; el método para
    fijarlos viene de [10] y [7], y se contrastan con analisis_sensibilidad().

Requisitos: Python 3.9 o superior (solo biblioteca estándar).
Uso rápido:  python motor_inferencia.py                -> ejemplo + validación
             python motor_inferencia.py --validar      -> validación dejando un caso fuera
             python motor_inferencia.py --verificar    -> verificación de la base de conocimientos
             python motor_inferencia.py --sensibilidad -> análisis de sensibilidad de pesos y umbral
             python motor_inferencia.py --auditar      -> auditoría de coherencia de todas las propuestas
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

RUTA_BC = Path(__file__).with_name("base_conocimientos")

# Clave de administrador para agregar o validar casos. Se guarda solo su huella SHA-256,
# no el texto de la clave (la clave está indicada en memoria_descriptiva.txt).
CLAVE_ADMIN_SHA256 = "059a50ce956b7ec61527c7ecc0c55b5a009dc54ab4acddce8852b46baa2aba30"

ESTADOS_ACTIVOS = ("Validado", "Validado parcialmente")   # participan en la recuperación [1] p. 9
NIVEL_ORDEN = {"1.er nivel": 0, "2.º nivel": 1}
NOMBRES_ATRIB = {"sintomas": "Síntomas", "subcategoria": "Subcategoría", "dispositivo": "Dispositivo",
                 "so": "Sistema operativo", "conexion": "Conexión"}


def verificar_clave(clave: str | None) -> bool:
    """Compara la huella SHA-256 de la clave escrita con la guardada (comparación en tiempo constante)."""
    if not clave:
        return False
    huella = hashlib.sha256(clave.encode("utf-8")).hexdigest()
    return hmac.compare_digest(huella, CLAVE_ADMIN_SHA256)


def _exigir_clave(clave: str | None):
    if not verificar_clave(clave):
        raise PermissionError("Clave de administrador incorrecta: no se modificó la base de conocimientos.")


# ═══════════════════════════════════════════════════════════════════════════
# 1. REPRESENTACIÓN DEL CASO                      [4] p. 96 (ficha); [6] Sec. 3.1–3.2
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class Caso:
    id: str
    codigo_cat: str            # p. ej. "3.1"  (árbol de categorías [7] Sec. 3.1; [4] p. 86)
    categoria: str             # Red, Hardware, Software, Cuentas
    subcategoria: str
    dispositivo: str           # PC de escritorio | Laptop
    so: str                    # Windows 10 | Windows 11 | Ubuntu 22.04
    conexion: str              # Cableada | Wi-Fi
    sintomas: set[str]         # códigos del catálogo cerrado [5]; [4] p. 37 (registrados + inferidos)
    tipo_caso: str = "Incidente"
    ubicacion: str = ""
    efecto: str = ""
    # --- parte de solución (no entra en la similitud) ---
    objeto_fallo: str = ""
    causa: str = ""
    solucion: str = ""
    prioridad: str = ""
    tiempo_min: float = 0
    nivel: str = "1.er nivel"
    resultado: str = ""
    veces_exito: int = 1       # idoneidad de la solución [7] Sec. 3.3
    validacion: dict = field(default_factory=lambda: {"estado": "Pendiente", "respaldo": []})
    origen: str = ""
    so_aplicable: list = field(default_factory=lambda: ["Windows", "Ubuntu"])   # dónde sirve la solución
    conexion_aplicable: list = field(default_factory=lambda: ["Cableada", "Wi-Fi"])
    dispositivo_aplicable: list = field(default_factory=lambda: ["PC de escritorio", "Laptop"])
    registrados: set = field(default_factory=set)   # síntomas tal como se registraron (sin los inferidos)

    def aplica_a(self, q) -> bool:
        """La solución tiene sentido para el SO, la conexión y el dispositivo del ticket [9] Sec. 4."""
        return (q.so.split()[0] in self.so_aplicable and q.conexion in self.conexion_aplicable
                and q.dispositivo in self.dispositivo_aplicable)

    @property
    def estado(self) -> str:
        return self.validacion.get("estado", "Pendiente")

    @property
    def activo(self) -> bool:
        return self.estado in ESTADOS_ACTIVOS

    def a_dict(self) -> dict:
        d = {k: getattr(self, k) for k in (
            "id", "codigo_cat", "categoria", "subcategoria", "tipo_caso", "dispositivo", "so", "conexion",
            "ubicacion", "sintomas", "efecto", "objeto_fallo", "causa", "solucion", "prioridad", "tiempo_min",
            "nivel", "resultado", "veces_exito", "validacion", "origen", "so_aplicable", "conexion_aplicable",
            "dispositivo_aplicable")}
        d["sintomas"] = sorted(self.registrados or self.sintomas)
        return d


@dataclass
class Consulta:
    """Ticket nuevo: solo la parte de problema (entradas del sistema)."""
    codigo_cat: str
    dispositivo: str
    so: str
    conexion: str
    sintomas: set[str]
    categoria: str = ""        # se completa con el árbol si no se indica
    registrados: set | None = None   # síntomas que marcó el técnico (antes de inferir los generales)


@dataclass
class Resultado:
    caso: Caso
    similitud: float
    detalle: dict = field(default_factory=dict)   # aporte de cada atributo (explicación «¿por qué?»)


# ═══════════════════════════════════════════════════════════════════════════
# 2. CARGA Y GUARDADO DE LA BASE DE CONOCIMIENTOS (JSON)
# ═══════════════════════════════════════════════════════════════════════════
def _leer(ruta: Path) -> dict:
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _escribir(ruta: Path, datos: dict):
    """Escritura atómica: se escribe un temporal y luego se reemplaza el archivo."""
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, ruta)


class BaseConocimientos:
    """Los cuatro contenedores de conocimiento de un sistema RBC [9]: vocabulario (catálogo y
    categorías), medida de similitud, base de casos y conocimiento de adaptación (reglas)."""

    ARCHIVOS = ("casos.json", "catalogo_sintomas.json", "categorias.json", "similitud_y_parametros.json",
                "reglas_adaptacion.json", "fuentes.json", "estructura_caso.json")

    def __init__(self, ruta: Path = RUTA_BC):
        self.ruta = Path(ruta)
        faltan = [a for a in self.ARCHIVOS if not (self.ruta / a).exists()]
        if faltan:
            raise FileNotFoundError(f"Faltan archivos en {self.ruta}: {', '.join(faltan)}")
        self._cargar_catalogo(_leer(self.ruta / "catalogo_sintomas.json"))
        self._cargar_categorias(_leer(self.ruta / "categorias.json"))
        self._cargar_similitud(_leer(self.ruta / "similitud_y_parametros.json"))
        self.reglas_json = _leer(self.ruta / "reglas_adaptacion.json")
        self.reglas = {r["id"]: r for r in self.reglas_json["reglas"]}
        self.estructura = _leer(self.ruta / "estructura_caso.json")
        self._cargar_fuentes(_leer(self.ruta / "fuentes.json"))
        self._cargar_casos(_leer(self.ruta / "casos.json"))

    # Vocabulario cerrado [5]; [9] Sec. 3.1
    def _cargar_catalogo(self, d):
        self.catalogo_json = d
        self.sintoma_nombre = {s["codigo"]: s["nombre"] for s in d["sintomas"]}
        self.sintoma_grupo = {s["codigo"]: s["grupo"] for s in d["sintomas"]}
        self.sintoma_codigo = {s["nombre"].lower(): s["codigo"] for s in d["sintomas"]}
        self.sintoma_tipo = {s["codigo"]: s.get("tipo", "falla") for s in d["sintomas"]}
        self.sintoma_requiere = {s["codigo"]: s["requiere"] for s in d["sintomas"] if s.get("requiere")}
        self.excluyentes = [set(g["sintomas"]) for g in d.get("excluyentes", [])]
        # Inferencia de rasgos [8] Sec. 5 (Identify Features): un síntoma específico implica uno general
        self.implica = {s["codigo"]: list(s.get("implica", [])) for s in d["sintomas"] if s.get("implica")}

    def cerrar(self, sintomas) -> set[str]:
        """Agrega los síntomas generales que se deducen de los específicos (cierre transitivo de «implica»).
        Ej.: «IP 169.254.x.x» → «Sin acceso a internet» → «Páginas no cargan»  [8] Sec. 5 (Identify Features)."""
        out, pendientes = set(sintomas), list(sintomas)
        while pendientes:
            for g in self.implica.get(pendientes.pop(), []):
                if g not in out:
                    out.add(g)
                    pendientes.append(g)
        return out

    def preparar(self, q):
        """Completa el ticket con los síntomas inferidos (una sola vez)."""
        if q.registrados is None:
            q.registrados = set(q.sintomas)
            q.sintomas = self.cerrar(q.sintomas)
        return q

    def preparar_caso(self, c):
        """Guarda los síntomas registrados del caso y usa, para comparar, los registrados más los inferidos."""
        if not c.registrados:
            c.registrados = set(c.sintomas)
        c.sintomas = self.cerrar(c.registrados)
        return c

    def incoherencias(self, q) -> list[str]:
        """Datos del ticket que se contradicen entre sí (p. ej. subcategoría Wi-Fi con conexión cableada)."""
        valores = {"conexion": q.conexion, "dispositivo": q.dispositivo}
        nombre = {"conexion": "conexión", "dispositivo": "dispositivo"}
        out = []
        req = self.sub_requiere.get(q.codigo_cat, {})
        for k, v in req.items():
            if valores[k] != v:
                out.append(f"La subcategoría «{self.subcategoria_de.get(q.codigo_cat)}» exige {nombre[k]} «{v}», "
                           f"pero el ticket indica «{valores[k]}».")
        for s in sorted(q.sintomas):
            for k, v in self.sintoma_requiere.get(s, {}).items():
                if valores[k] != v:
                    out.append(f"El síntoma «{self.sintoma_nombre[s]}» solo ocurre con {nombre[k]} «{v}», "
                               f"pero el ticket indica «{valores[k]}».")
        return out

    def contradice(self, a: set, b: set) -> bool:
        """True si a y b marcan síntomas distintos de un mismo grupo excluyente (p. ej. cable USB vs Bluetooth)."""
        return any((a & g) and (b & g) and (a & g) != (b & g) for g in self.excluyentes)

    def fallas(self, sintomas) -> set[str]:
        """Síntomas de tipo «falla» (los de «contexto» solo afinan la búsqueda)."""
        return {s for s in sintomas if self.sintoma_tipo.get(s, "falla") == "falla"}

    # Árbol de tipificación [7] Sec. 3.1; [4] p. 86
    def _cargar_categorias(self, d):
        self.categorias_json = d
        self.categoria_de, self.subcategoria_de = {}, {}
        self.sub_requiere = {c["codigo"]: c["requiere"] for c in d["categorias"] if c.get("requiere")}
        for c in d["categorias"]:
            self.categoria_de[c["codigo"]] = c["categoria"]
            if c["subcategoria"]:
                self.subcategoria_de[c["codigo"]] = c["subcategoria"]

    # Pesos wj [6] Ec. 5; fijados con conocimiento del dominio [10] Sec. 3.5
    def _cargar_similitud(self, d):
        self.similitud_json = d
        self.atributos = {a["atributo"]: a for a in d["atributos"]}
        self.pesos = {a["atributo"]: float(a["peso"]) for a in d["atributos"]}
        total = sum(self.pesos.values())
        if abs(total - 1) > 1e-6:
            raise ValueError(f"Los pesos deben sumar 1 (suman {total:.3f}). Revise similitud_y_parametros.json.")
        p = d["parametros"]
        self.parametros = p
        self.k = int(p["k"]["valor"])
        self.umbral_minimo = float(p["umbral_minimo"]["valor"])
        self.umbral_retencion = float(p["umbral_retencion"]["valor"])

    def _cargar_fuentes(self, d):
        self.fuentes_json = d
        self.metodologicas = {f"[{f['id']}]": f for f in d["metodologicas"]}
        self.tecnicas = {f["id"]: f for f in d["tecnicas"]}

    def _cargar_casos(self, d):
        self.casos_json_desc = d.get("descripcion", "")
        self.casos: list[Caso] = []
        for c in d["casos"]:
            c = dict(c)
            c["sintomas"] = set(c["sintomas"])
            self.casos.append(self.preparar_caso(Caso(**c)))

    # ── Consultas de conveniencia ──────────────────────────────────────────
    @property
    def casos_activos(self) -> list[Caso]:
        return [c for c in self.casos if c.activo]

    @property
    def casos_pendientes(self) -> list[Caso]:
        return [c for c in self.casos if c.estado == "Pendiente"]

    def caso(self, id_caso: str) -> Caso | None:
        return next((c for c in self.casos if c.id == id_caso), None)

    def fuente(self, ref: str) -> dict | None:
        """Devuelve una fuente a partir de «[6]», «6», «[6] Ec. 5» o «T12»."""
        ref = ref.strip()
        m = re.match(r"\[?(\d+)\]?", ref)
        if m and not ref.startswith("T"):
            return self.metodologicas.get(f"[{m.group(1)}]")
        m = re.match(r"(T\d+)", ref)
        return self.tecnicas.get(m.group(1)) if m else None

    def codigos(self, sintomas) -> set[str]:
        """Acepta nombres o códigos de síntomas. Un descriptor desconocido se descarta [8] Sec. 5."""
        out = set()
        for s in sintomas:
            if s in self.sintoma_nombre:
                out.add(s)
            elif s.lower() in self.sintoma_codigo:
                out.add(self.sintoma_codigo[s.lower()])
            else:
                print(f"  Aviso: el síntoma «{s}» no está en el catálogo y se ignora.")
        return out

    def siguiente_id(self) -> str:
        return f"TK-{max(int(c.id.split('-')[1]) for c in self.casos) + 1:03d}"

    # ── Guardado ───────────────────────────────────────────────────────────
    def guardar_casos(self):
        _escribir(self.ruta / "casos.json", {"descripcion": self.casos_json_desc,
                                             "casos": [c.a_dict() for c in self.casos]})

    def guardar_fuentes(self):
        _escribir(self.ruta / "fuentes.json", self.fuentes_json)

    def guardar_catalogo(self):
        _escribir(self.ruta / "catalogo_sintomas.json", self.catalogo_json)


# ═══════════════════════════════════════════════════════════════════════════
# 3. SIMILITUD LOCAL Y GLOBAL                         [6] Ec. 1, 4 y 5; [3] Ec. 2
# ═══════════════════════════════════════════════════════════════════════════
def sim_sintomas(a: set, b: set) -> float:
    """Índice de Jaccard |A∩B| / |A∪B|  [3] Ec. 2."""
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def sim_subcategoria(cod_a: str, cod_b: str) -> float:
    """Árbol de categorías: misma subcategoría = 1; misma categoría padre = 0,5; si no, 0.
    Similitud por árbol [6] Ec. 4 y árbol de tipificación [7] Sec. 3.1–3.2."""
    if cod_a == cod_b:
        return 1.0
    if cod_a.split(".")[0] == cod_b.split(".")[0]:
        return 0.5
    return 0.0


def sim_exacta(a: str, b: str) -> float:
    """Atributo categórico: 1 si coincide, 0 si no  [6] Ec. 1."""
    return 1.0 if a == b else 0.0


def sim_so(a: str, b: str) -> float:
    """Sistema operativo: igual = 1; misma familia (Windows 10/11) = 0,5; distinto = 0  [6] Ec. 1 y Ec. 4."""
    if a == b:
        return 1.0
    return 0.5 if a.split()[0] == b.split()[0] else 0.0


def similitud_global(q: Consulta, c: Caso, pesos: dict) -> tuple[float, dict]:
    """Sim(q, c) = Σ wj · simj(q, c)  [6] Ec. 5. Devuelve también (similitud local, aporte) por atributo."""
    locales = {
        "sintomas": sim_sintomas(q.sintomas, c.sintomas),
        "subcategoria": sim_subcategoria(q.codigo_cat, c.codigo_cat),
        "dispositivo": sim_exacta(q.dispositivo, c.dispositivo),
        "so": sim_so(q.so, c.so),
        "conexion": sim_exacta(q.conexion, c.conexion),
    }
    detalle = {a: (locales[a], pesos[a] * locales[a]) for a in locales}
    return sum(v[1] for v in detalle.values()), detalle


# ═══════════════════════════════════════════════════════════════════════════
# 4. MOTOR: RECUPERAR · REUTILIZAR · REVISAR · RETENER                         [8]
# ═══════════════════════════════════════════════════════════════════════════
def _minuscula(t: str) -> str:
    """Primera letra en minúscula, salvo siglas o nombres propios (Windows, VGA, DNS…)."""
    if not t or (len(t) > 1 and (t[1].isupper() or t.split()[0] in ("Windows", "Office", "Outlook", "Microsoft"))):
        return t
    return t[0].lower() + t[1:]


def _sustituir(texto: str, pares: list[tuple[str, str]]) -> str:
    """Adaptación por sustitución [9] Sec. 4. Se reemplazan primero las frases más largas
    para que «sudo dhclient -r» no se confunda con «sudo dhclient»."""
    for a, b in sorted(pares, key=lambda p: -len(p[0])):
        texto = re.sub(re.escape(a), b, texto, flags=re.IGNORECASE)
    return texto


class MotorInferencia:
    def __init__(self, bc: BaseConocimientos):
        self.bc = bc
        self.nivel_busqueda = "subcategoria"

    # ── 4.1 RECUPERAR ────────────────────────────────────────────────────────
    def recuperar(self, q: Consulta, k: int | None = None, excluir: str | None = None,
                  pesos: dict | None = None) -> list[Resultado]:
        """Devuelve los k casos validados más similares, ordenados.

        * Solo casos «Validado» o «Validado parcialmente»: los pendientes aún no tienen respaldo [1] p. 9.
        * Filtro previo por categoría padre; si no hay casos, se usa toda la base [7] Sec. 3.2.
        * Orden: similitud global descendente [6] Ec. 5; k vecinos más cercanos [9] Sec. 3.1.1.
        * Desempate: 1) más veces aplicada con éxito [7] Sec. 3.3; 2) 1.er nivel antes que 2.º [4] p. 38;
          3) menor tiempo de resolución [4] p. 98; 4) caso más reciente (decisión de diseño).
        """
        k = k or self.bc.k
        pesos = pesos or self.bc.pesos
        self.bc.preparar(q)
        q.categoria = q.categoria or self.bc.categoria_de.get(q.codigo_cat.split(".")[0], "")
        # Solo casos que explican al menos un síntoma de falla REGISTRADO en el ticket (no basta un síntoma
        # general inferido): «Initially match» por descriptores de entrada [8] Sec. 5
        fallas_q = self.bc.fallas(q.registrados)
        # Solo casos cuya solución aplica al SO, la conexión y el dispositivo del ticket [9] Sec. 4
        base = [c for c in self.bc.casos_activos if c.id != excluir and c.sintomas & fallas_q
                and c.aplica_a(q) and not self.bc.contradice(q.sintomas, c.sintomas)]
        # Búsqueda por niveles del árbol: subcategoría → categoría → toda la base [7] Sec. 3.2
        padre = q.codigo_cat.split(".")[0]
        candidatos, self.nivel_busqueda = [c for c in base if c.codigo_cat == q.codigo_cat], "subcategoria"
        if not candidatos:
            candidatos, self.nivel_busqueda = [c for c in base if c.codigo_cat.split(".")[0] == padre], "categoria"
        if not candidatos:
            candidatos, self.nivel_busqueda = base, "toda la base"
        res = []
        for c in candidatos:
            s, det = similitud_global(q, c, pesos)
            res.append(Resultado(c, s, det))
        res.sort(key=lambda r: (-round(r.similitud, 6), -r.caso.veces_exito,
                                NIVEL_ORDEN.get(r.caso.nivel, 2), r.caso.tiempo_min,
                                -int(r.caso.id.split("-")[1])))
        return res[:k]

    # ── 4.2 REUTILIZAR ───────────────────────────────────────────────────────
    def reutilizar(self, q: Consulta, r: Resultado) -> dict:
        """Copia la solución del caso recuperado y la adapta con R1–R5  [8] Sec. 6; [9] Sec. 4.
        Devuelve la solución propuesta y las reglas aplicadas con sus fuentes (explicación «¿cómo?»)."""
        c, R = r.caso, self.bc.reglas
        solucion = c.solucion
        aplicadas = []

        def anotar(id_regla, texto):
            aplicadas.append({"regla": id_regla, "texto": texto, "fuentes": R[id_regla]["fuentes"]})

        # R1 – sistema operativo distinto (Windows ↔ Ubuntu)
        if c.so.split()[0] != q.so.split()[0]:
            pares = [(s["windows"], s["ubuntu"]) for s in R["R1"]["sustituciones_windows_a_ubuntu"]]
            if not q.so.startswith("Ubuntu"):
                pares = [(b, a) for a, b in pares]
            nuevo = _sustituir(solucion, pares)
            if nuevo != solucion:
                anotar("R1", "Se sustituyeron los comandos del sistema operativo por su equivalente documentado")
            solucion = nuevo
        # R2 – conexión distinta (Cableada ↔ Wi-Fi)
        if c.conexion != q.conexion:
            pares = [(s["cableada"], s["wifi"]) for s in R["R2"]["sustituciones_cableada_a_wifi"]]
            if q.conexion != "Wi-Fi":
                pares = [(b, a) for a, b in pares]
            nuevo = _sustituir(solucion, pares)
            if nuevo != solucion:
                anotar("R2", "Se adaptó la verificación de la conexión")
            solucion = nuevo
        # R3 – dispositivo distinto (PC ↔ Laptop)
        if c.dispositivo != q.dispositivo:
            pares = [(s["pc"], s["laptop"]) for s in R["R3"]["sustituciones_pc_a_laptop"]]
            if q.dispositivo != "Laptop":
                pares = [(b, a) for a, b in pares]
            nuevo = _sustituir(solucion, pares)
            if nuevo != solucion:
                anotar("R3", "Se adaptaron los componentes del equipo")
            solucion = nuevo

        escalar = False
        # R4 – el caso se resolvió en 2.º nivel  [4] p. 38; [2] p. 41; [1] p. 60; [12] Sec. 2.3.1
        if c.nivel.startswith("2"):
            escalar = True
            anotar("R4", "El caso original se resolvió en 2.º nivel: derivar con este diagnóstico")
        # R5 – varios usuarios afectados: posible problema  [4] p. 184; [1] p. 224
        cod_varios = self.bc.sintoma_codigo.get("varios usuarios con el mismo fallo")
        if cod_varios and cod_varios in q.sintomas:
            escalar = True
            anotar("R5", "Varios usuarios afectados: tratar como posible problema y escalar a 2.º nivel")

        if not aplicadas:
            aplicadas.append({"regla": "—", "texto": "Sin adaptación: se copia la solución del caso",
                              "fuentes": ["[8] Sec. 6"]})
        return {"caso": c.id, "causa_probable": c.causa, "solucion": solucion,
                "escalar_2do_nivel": escalar, "reglas": aplicadas}

    # ── 4.3 REVISAR ──────────────────────────────────────────────────────────
    @staticmethod
    def revisar(funciono: bool, conformidad_usuario: bool) -> dict:
        """La evaluación la hace el técnico en el entorno real [8] Sec. 7.
        Se cierra solo con conformidad del usuario [4] p. 49; si no, se escala [4] p. 38."""
        if funciono and conformidad_usuario:
            return {"estado": "Confirmado", "accion": "Retener el caso"}
        return {"estado": "No resuelto", "accion": "Escalar a 2.º nivel y registrar la solución final"}

    # ── 4.4 RETENER ──────────────────────────────────────────────────────────
    def retener(self, q: Consulta, causa: str, solucion: str, objeto_fallo: str, tiempo_min: float,
                nivel: str = "1.er nivel", clave: str | None = None, guardar: bool = True) -> str:
        """Retención con umbral [7] Sec. 3.4–3.5 (requiere la clave de administrador):
        * si existe un caso validado con similitud ≥ umbral y la MISMA solución, se suma 1 a su
          idoneidad (evita duplicados [11]);
        * si no, se crea un caso nuevo «Pendiente»: no se usa para recomendar hasta que un administrador
          le agregue su respaldo documental [1] p. 9; [8] Sec. 7."""
        _exigir_clave(clave)
        mejor = self.recuperar(q, k=1)
        if mejor and mejor[0].similitud >= self.bc.umbral_retencion and \
                mejor[0].caso.solucion.strip().lower() == solucion.strip().lower():
            mejor[0].caso.veces_exito += 1
            msg = f"Se reforzó {mejor[0].caso.id}: veces aplicada con éxito = {mejor[0].caso.veces_exito}"
        else:
            nuevo = Caso(id=self.bc.siguiente_id(), codigo_cat=q.codigo_cat,
                         categoria=self.bc.categoria_de.get(q.codigo_cat.split(".")[0], ""),
                         subcategoria=self.bc.subcategoria_de.get(q.codigo_cat, ""), dispositivo=q.dispositivo,
                         so=q.so, conexion=q.conexion, sintomas=set(q.registrados or q.sintomas), causa=causa, solucion=solucion,
                         objeto_fallo=objeto_fallo, tiempo_min=tiempo_min, nivel=nivel, resultado="Resuelto",
                         validacion={"estado": "Pendiente", "metodo": "", "fecha": str(date.today()), "respaldo": [],
                                     "observacion": "Retenido desde un ticket confirmado; falta su respaldo documental."},
                         origen="Retenido por el sistema desde un ticket confirmado", so_aplicable=[q.so.split()[0]],
                         conexion_aplicable=[q.conexion], dispositivo_aplicable=[q.dispositivo])
            self.bc.casos.append(self.bc.preparar_caso(nuevo))
            msg = f"Se creó el caso {nuevo.id} como «Pendiente»: agréguele su fuente en Administrar casos."
        if guardar:
            self.bc.guardar_casos()
        return msg

    # ── 4.5 CICLO COMPLETO (hasta la propuesta) ─────────────────────────────
    def resolver(self, q: Consulta) -> dict:
        self.bc.preparar(q)
        # Primero se revisa que el ticket no se contradiga [8] Sec. 5 (Identify features)
        inco = self.bc.incoherencias(q)
        if inco:
            return {"sugerencias": [], "propuesta": None, "nivel_busqueda": "subcategoria", "aviso": "", "preguntas": [],
                    "mensaje": "El ticket tiene datos que se contradicen: " + " ".join(inco) + " Corrija el ticket y vuelva a buscar."}
        top = self.recuperar(q)
        nivel = self.nivel_busqueda
        sub_q = self.bc.subcategoria_de.get(q.codigo_cat, q.codigo_cat)
        aviso = ""
        # Umbral de recuperación: el caso debe ser «suficientemente similar» [8] Sec. 5; si no, se escala [4] p. 38; [1] p. 60
        if not top:
            # Explicar el motivo real: otro SO, síntomas que se contradicen o ningún síntoma de falla en común
            fallas_q = self.bc.fallas(q.registrados)
            comparten = [c for c in self.bc.casos_activos if c.sintomas & fallas_q]
            fam = q.so.split()[0]
            otro_so = [c for c in comparten if not c.aplica_a(q)]
            contradicen = [c for c in comparten if c.aplica_a(q) and self.bc.contradice(q.sintomas, c.sintomas)]
            if not fallas_q:
                motivo = "Eligió solo datos adicionales: agregue al menos un síntoma de falla."
            elif otro_so and len(otro_so) + len(contradicen) == len(comparten):
                c0 = otro_so[0]
                limite = (f"solo para {'/'.join(c0.so_aplicable)}" if q.so.split()[0] not in c0.so_aplicable else
                          f"solo para conexión {'/'.join(c0.conexion_aplicable)}" if q.conexion not in c0.conexion_aplicable else
                          f"solo para {'/'.join(c0.dispositivo_aplicable).lower()}")
                motivo = (f"Hay casos con estos síntomas ({', '.join(c.id for c in otro_so[:3])}), pero su solución es {limite} "
                          f"y no aplica a este equipo ({q.dispositivo}, {q.so}, {q.conexion}): escale a 2.º nivel.")
            elif contradicen:
                c0 = contradicen[0]
                g0 = next(g for g in self.bc.excluyentes if (c0.sintomas & g) and (q.sintomas & g) and (c0.sintomas & g) != (q.sintomas & g))
                N = self.bc.sintoma_nombre
                motivo = (f"Los casos con estos síntomas ({', '.join(c.id for c in contradicen[:3])}) suponen "
                          f"«{N[sorted((c0.sintomas & g0) - q.sintomas or c0.sintomas & g0)[0]]}», que se contradice con "
                          f"«{N[sorted((q.sintomas & g0) - c0.sintomas or q.sintomas & g0)[0]]}»: "
                          "revise los síntomas o escale a 2.º nivel.")
            else:
                motivo = "Ningún caso validado comparte un síntoma de falla con el ticket: revise los síntomas o escale a 2.º nivel."
            return {"sugerencias": [], "propuesta": None, "nivel_busqueda": nivel, "aviso": "", "preguntas": [],
                    "mensaje": motivo}
        r = top[0]
        if r.similitud < self.bc.umbral_minimo:
            return {"sugerencias": top, "propuesta": None, "nivel_busqueda": nivel, "aviso": "",
                    "preguntas": [], "mensaje": f"El caso más parecido no llega al {self.bc.umbral_minimo:.0%} de similitud: escalar a 2.º nivel."}
        if nivel != "subcategoria":
            # El caso viene de otra subcategoría: solo se reutiliza si comparte al menos la mitad de los síntomas
            u = float(self.bc.parametros.get("umbral_sintomas_otra_subcategoria", {}).get("valor", 0.5))
            comunes = len(r.caso.sintomas & q.sintomas)
            if r.detalle["sintomas"][0] < u:
                return {"sugerencias": top, "propuesta": None, "nivel_busqueda": nivel, "aviso": "", "preguntas": [],
                        "mensaje": f"Ningún caso de «{sub_q}» comparte los síntomas elegidos. El más parecido es de "
                                   f"«{r.caso.subcategoria}» y solo coincide en {comunes} síntoma(s), así que su solución "
                                   "no se aplica a esta falla. Revise la subcategoría y los síntomas, o escale a 2.º nivel."}
            aviso = (f"No hay casos de «{sub_q}» con estos síntomas; se usa {r.caso.id} de «{r.caso.subcategoria}», "
                     f"que coincide en {comunes} de {len(q.sintomas | r.caso.sintomas)} síntomas. Verifique que la subcategoría elegida sea la correcta.")
        # Suficiencia: el ticket debe confirmar al menos la mitad de los síntomas del caso y no debe haber
        # otra causa casi empatada; si no, se piden más datos  [8] Sec. 5 (p. 16); [9] Sec. 3.3.5; [7] p. 5
        par = self.bc.parametros
        cob_min = float(par.get("cobertura_minima", {}).get("valor", 0.5))
        cobertura = len(r.caso.sintomas & q.sintomas) / len(r.caso.sintomas)
        # Empate por SÍNTOMAS: si otro caso con otra causa coincide igual o mejor en los síntomas, el contexto
        # (dispositivo, SO, conexión) no debe decidir la causa  [8] Sec. 5 (Select); [9] Sec. 3.3.5
        N = self.bc.sintoma_nombre
        candidatos = self.recuperar(q, k=10**6)   # todos los candidatos del nivel (no solo los k mostrados)
        sj = lambda x: x.detalle["sintomas"][0]
        otros = [x for x in candidatos if x.caso.id != r.caso.id and x.caso.causa != r.caso.causa]
        alternativas = [x for x in otros if x.caso.sintomas == r.caso.sintomas]
        # rival: explica al menos los mismos síntomas del ticket que el mejor caso, así que el ticket no los distingue
        explica_r = r.caso.sintomas & q.sintomas
        rivales = [x for x in otros if x.caso.sintomas != r.caso.sintomas
                   and ((x.caso.sintomas & q.sintomas) >= explica_r or sj(x) >= sj(r) - 1e-9)]
        # Si el ticket confirma TODOS los síntomas del mejor caso, ese caso se propone; los rivales que necesitan
        # síntomas adicionales quedan como nota («si además hay X, ver TK-...»)
        notas = []
        if r.caso.sintomas <= q.sintomas:
            notas = [{"caso": x.caso.id, "causa": x.caso.causa,
                      "si_ademas": [N[s_] for s_ in sorted(x.caso.sintomas - q.sintomas)]} for x in rivales]
            rivales = []
        # Dato de contexto supuesto por el caso y no confirmado por el ticket (grupo excluyente sin respuesta)
        # Solo se pregunta si la respuesta distingue entre candidatos: otro candidato (con otra causa) supone el otro
        # valor del grupo  (preguntas que discriminan, RBC conversacional [9] Sec. 3.3.5)
        # Se cuentan todos los casos de la subcategoría que explican un síntoma marcado, aunque su solución no aplique
        # a este equipo: si el dato decide entre ellos, hay que preguntarlo antes de suponerlo.
        fallas_reg = self.bc.fallas(q.registrados)
        dominio = [c for c in self.bc.casos_activos if c.codigo_cat == r.caso.codigo_cat and c.sintomas & fallas_reg
                   and c.causa != r.caso.causa and not self.bc.contradice(q.sintomas, c.sintomas)]
        sin_confirmar = [g for g in self.bc.excluyentes if (r.caso.sintomas & g) and not (q.sintomas & g)
                         and any((c.sintomas & g) - r.caso.sintomas for c in dominio)]
        supuestos = sorted(s_ for g in self.bc.excluyentes if (r.caso.sintomas & g) and not (q.sintomas & g)
                           for s_ in r.caso.sintomas & g)
        # Síntomas de falla del ticket que el caso NO explica: si otro caso (con otra causa) los explica,
        # el ticket mezcla fallas distintas y no se debe elegir una sola  [8] Sec. 5 (Select)
        no_explicados = self.bc.fallas(q.registrados) - r.caso.sintomas
        conflictos = [x for x in candidatos if x.caso.causa != r.caso.causa and x.caso.sintomas & no_explicados]
        if conflictos:
            partes = [f"«{N[s]}» corresponde a {x.caso.id} ({_minuscula(x.caso.causa)})"
                      for x in conflictos[:2] for s in sorted(x.caso.sintomas & no_explicados)][:2]
            explicados = sorted(r.caso.sintomas & self.bc.fallas(q.registrados))
            return {"sugerencias": top, "propuesta": None, "nivel_busqueda": nivel, "aviso": aviso,
                    "preguntas": self.preguntas(q),
                    "mensaje": "Ningún caso explica todos los síntomas juntos: "
                               + f"«{N[explicados[0]]}» corresponde a {r.caso.id} ({_minuscula(r.caso.causa)}) y "
                               + "; ".join(partes) + ". Pueden ser dos fallas distintas (registre un ticket por cada una) "
                               "o una falla que la base aún no tiene (escale a 2.º nivel). Confirme qué síntoma describe el problema principal."}
        if no_explicados:
            # Ningún caso aplicable explica ese síntoma junto con los demás: no se propone una solución que
            # deje sin explicar un síntoma de falla marcado  [8] Sec. 5 (Select); escalar [4] p. 38
            faltan = ", ".join(f"«{N[s]}»" for s in sorted(no_explicados))
            return {"sugerencias": top, "propuesta": None, "nivel_busqueda": nivel, "aviso": aviso, "preguntas": [],
                    "mensaje": f"El caso más parecido ({r.caso.id}, {_minuscula(r.caso.causa)}) no explica {faltan}, y "
                               "ningún caso aplicable a este equipo explica todos los síntomas juntos. Revise ese síntoma "
                               "o escale a 2.º nivel."}
        if cobertura < cob_min or rivales or sin_confirmar:
            preguntas = self.preguntas(q)
            if sin_confirmar and not rivales and cobertura >= cob_min:
                extra = [{"codigo": c_, "pregunta": f"¿{N[c_]}?", "casos": [x.caso.id for x in candidatos if c_ in x.caso.sintomas],
                          "causas": []} for g in sin_confirmar for c_ in sorted(g)]
                preguntas = extra + [p_ for p_ in preguntas if p_["codigo"] not in {e["codigo"] for e in extra}]
            # sin preguntas repetidas (un síntoma puede estar en dos grupos excluyentes)
            vistas = set()
            preguntas = [p_ for p_ in preguntas if not (p_["codigo"] in vistas or vistas.add(p_["codigo"]))]
            motivo = (f"los síntomas elegidos coinciden por igual con {len({x.caso.causa for x in rivales}) + 1} fallas distintas"
                      if rivales else
                      f"el caso más parecido ({r.caso.id}) supone «{N[sorted(r.caso.sintomas & sin_confirmar[0])[0]]}», dato que el ticket no indica"
                      if sin_confirmar and cobertura >= cob_min else
                      f"el ticket solo confirma {len(r.caso.registrados & q.sintomas)} de los {len(r.caso.registrados)} síntomas del caso más parecido ({r.caso.id})")
            pedir = ("Responda las preguntas de abajo (agregue el síntoma que corresponda) para que el sistema pueda "
                     "distinguir la causa." if preguntas else
                     "No hay otro síntoma del catálogo que permita confirmarlo: revise el equipo o escale a 2.º nivel.")
            return {"sugerencias": top, "propuesta": None, "nivel_busqueda": nivel, "aviso": aviso,
                    "preguntas": preguntas, "mensaje": f"Faltan datos para decidir: {motivo}. {pedir}"}
        if supuestos:
            aviso = (aviso + " " if aviso else "") + ("El caso supone " + ", ".join(f"«{N[s_]}»" for s_ in supuestos)
                                                      + ": confírmelo antes de aplicar la solución.")
        propuesta = self.reutilizar(q, r)
        # Una sola entrada por causa (los tickets repetidos de una misma falla no se listan dos veces)
        vistas = set()
        alternativas = [x for x in alternativas if not (x.caso.causa in vistas or vistas.add(x.caso.causa))]
        vistas = set()
        notas = [n_ for n_ in notas if not (n_["causa"] in vistas or vistas.add(n_["causa"]))]
        propuesta["alternativas"] = [{"caso": x.caso.id, "causa": x.caso.causa, "solucion": self.reutilizar(q, x)["solucion"]}
                                     for x in alternativas]
        propuesta["notas"] = notas
        return {"sugerencias": top, "propuesta": propuesta, "mensaje": "OK",
                "nivel_busqueda": nivel, "aviso": aviso, "preguntas": []}

    def preguntas(self, q: Consulta, maximo: int = 6) -> list[dict]:
        """Síntomas que distinguen entre los casos candidatos y que el ticket aún no tiene (RBC
        conversacional [9] Sec. 3.3.5; [7] p. 5). Se ordenan por la similitud del caso al que apuntan."""
        self.bc.preparar(q)
        cands = self.recuperar(q, k=10**6)
        # Se pregunta por los casos que podrían explicar TODOS los síntomas de falla marcados (si los hay)
        fallas_reg = self.bc.fallas(q.registrados)
        completos = [x for x in cands if fallas_reg <= x.caso.sintomas]
        cands = completos or cands
        out, vistos = [], set()
        for r in cands:
            for s in sorted(r.caso.sintomas - q.sintomas):
                if s in vistos:
                    continue
                vistos.add(s)
                casos = [x.caso.id for x in cands if s in x.caso.sintomas]
                if len(casos) == len(cands) and len({x.caso.causa for x in cands}) > 1:
                    continue   # está en todos los candidatos y hay varias causas: no ayuda a distinguir
                out.append({"codigo": s, "pregunta": f"¿{self.bc.sintoma_nombre[s]}?", "casos": casos,
                            "causas": sorted({x.caso.causa for x in cands if s in x.caso.sintomas})})
        return out[:maximo]

    # ── 4.6 EXPLICACIÓN Y JUSTIFICACIÓN ──────────────────────────────────────
    def explicar(self, q: Consulta, r: Resultado) -> str:
        """Explicación «¿por qué?» en texto: aporte de cada atributo [9] Sec. 3.3.5."""
        reg = q.registrados if q.registrados is not None else q.sintomas
        comunes = [self.bc.sintoma_nombre[s] + ("" if s in reg else " (inferido)") for s in sorted(q.sintomas & r.caso.sintomas)]
        lineas = [f"{r.caso.id} – similitud {r.similitud:.0%}"]
        for a, (local, aporte) in r.detalle.items():
            lineas.append(f"   {NOMBRES_ATRIB[a]:<18} sim = {local:.2f}  ×  peso {self.bc.pesos[a]:.2f}  =  {aporte:.3f}"
                          f"   ({self.bc.atributos[a]['fuente_metodo']})")
        lineas.append("   Síntomas en común: " + (", ".join(comunes) if comunes else "ninguno"))
        for x in r.caso.validacion.get("respaldo", []):
            f = self.bc.fuente(x["fuente"]) or {}
            lineas.append(f"   Respaldo {x['fuente']} ({f.get('organizacion', '')}): {x['nota']}")
        return "\n".join(lineas)

    def justificar(self, q: Consulta, salida: dict) -> dict:
        """Responde «¿por qué el sistema decidió esto?» con todas sus fuentes, paso por paso."""
        top = salida["sugerencias"]
        p = salida["propuesta"]
        par = self.bc.parametros
        pasos = [{
            "paso": "1. Recuperar",
            "decision": f"Entre los {len(self.bc.casos_activos)} casos validados se tomaron solo los que comparten al menos "
                        f"un síntoma, buscando primero en la misma subcategoría (nivel usado: {salida.get('nivel_busqueda', 'subcategoria')}), "
                        f"y se muestran hasta {self.bc.k} de los más similares (k-NN).",
            "fuentes": [par["k"]["fuente"], self.bc.similitud_json["fuente_formula"],
                        par.get("busqueda_por_niveles", {}).get("fuente", "[7] Sec. 3.2")]}]
        if top:
            r = top[0]
            pasos.append({
                "paso": "2. Similitud del mejor caso",
                "decision": f"{r.caso.id} obtuvo {r.similitud:.0%}: " + "; ".join(
                    f"{NOMBRES_ATRIB[a]} {loc:.2f}×{self.bc.pesos[a]:.2f}" for a, (loc, _) in r.detalle.items()),
                "fuentes": [f"{NOMBRES_ATRIB[a]}: {self.bc.atributos[a]['fuente_metodo']}" for a in r.detalle]
                           + [self.bc.similitud_json["fuente_pesos"]]})
        pasos.append({
            "paso": "3. Umbral",
            "decision": ((f"El mejor caso supera el umbral de {self.bc.umbral_minimo:.0%} y comparte síntomas: se propone su solución."
                          + (" " + salida["aviso"] if salida.get("aviso") else "")) if p else salida["mensaje"]),
            "fuentes": [par["umbral_minimo"]["fuente"]] + (
                [par["umbral_sintomas_otra_subcategoria"]["fuente"]] if salida.get("nivel_busqueda", "subcategoria") != "subcategoria"
                and "umbral_sintomas_otra_subcategoria" in par else [])})
        if p:
            caso = self.bc.caso(p["caso"])
            pasos.append({
                "paso": "4. Contenido de la solución (respaldo del caso)",
                "decision": f"La causa «{caso.causa}» y la solución de {caso.id} están validadas con documentación técnica "
                            f"({caso.estado.lower()}).",
                "respaldo": caso.validacion.get("respaldo", []),
                "limitacion": caso.validacion.get("limitacion", "")})
            pasos.append({
                "paso": "5. Adaptación y escalamiento",
                "decision": "; ".join(f"{x['regla']}: {x['texto']}" for x in p["reglas"]),
                "fuentes": sorted({f for x in p["reglas"] for f in x["fuentes"]})})
        return {"pasos": pasos}


# ═══════════════════════════════════════════════════════════════════════════
# 5. ADMINISTRACIÓN DE LA BASE (protegida con clave)
# ═══════════════════════════════════════════════════════════════════════════
CAMPOS_OBLIGATORIOS = ("codigo_cat", "dispositivo", "so", "conexion", "sintomas", "objeto_fallo", "causa", "solucion")


def agregar_caso(motor: MotorInferencia, datos: dict, respaldo: list[dict], clave: str | None,
                 estado: str = "Validado", guardar: bool = True) -> str:
    """Agrega un caso nuevo a la base.
    * Exige la clave de administrador.
    * Exige al menos una fuente de respaldo (fuente técnica o metodológica existente, sección y nota):
      sin respaldo el caso queda «Pendiente» y no participa en la recuperación [1] p. 9.
    * Rechaza duplicados: un caso validado con similitud ≥ umbral de retención y la misma solución [7]; [11].
    """
    _exigir_clave(clave)
    bc = motor.bc
    faltan = [c for c in CAMPOS_OBLIGATORIOS if not datos.get(c)]
    if faltan:
        raise ValueError("Faltan datos obligatorios: " + ", ".join(faltan))
    sint = set(datos["sintomas"])
    desconocidos = [s for s in sint if s not in bc.sintoma_nombre]
    if desconocidos or not 1 <= len(sint) <= 3:
        raise ValueError("Los síntomas deben ser de 1 a 3 códigos del catálogo.")
    if not bc.fallas(sint):
        raise ValueError("Elija al menos un síntoma de falla (los «datos adicionales» solos no describen una falla).")
    if any(len(sint & g) > 1 for g in bc.excluyentes):
        raise ValueError("Hay síntomas que se excluyen entre sí (p. ej. cable USB y Bluetooth).")
    if datos["codigo_cat"] not in bc.subcategoria_de:
        raise ValueError("La subcategoría no existe en el árbol de categorías.")
    for x in respaldo:
        if not bc.fuente(x.get("fuente", "")):
            raise ValueError(f"La fuente «{x.get('fuente')}» no está registrada en fuentes.json.")
    q = Consulta(datos["codigo_cat"], datos["dispositivo"], datos["so"], datos["conexion"], sint)
    inco = bc.incoherencias(q)
    if inco:
        raise ValueError(" ".join(inco))
    dup = motor.recuperar(q, k=1)
    if dup and dup[0].similitud >= bc.umbral_retencion and \
            dup[0].caso.solucion.strip().lower() == datos["solucion"].strip().lower():
        raise ValueError(f"Caso duplicado: {dup[0].caso.id} ya tiene el mismo problema y la misma solución.")
    estado = estado if respaldo else "Pendiente"
    nuevo = Caso(id=bc.siguiente_id(), codigo_cat=datos["codigo_cat"],
                 categoria=bc.categoria_de[datos["codigo_cat"].split(".")[0]],
                 subcategoria=bc.subcategoria_de[datos["codigo_cat"]], dispositivo=datos["dispositivo"],
                 so=datos["so"], conexion=datos["conexion"], sintomas=sint,
                 tipo_caso=datos.get("tipo_caso", "Incidente"), ubicacion=datos.get("ubicacion", ""),
                 efecto=datos.get("efecto", ""), objeto_fallo=datos["objeto_fallo"], causa=datos["causa"],
                 solucion=datos["solucion"], prioridad=datos.get("prioridad", "Media"),
                 tiempo_min=float(datos.get("tiempo_min", 10)), nivel=datos.get("nivel", "1.er nivel"),
                 resultado=datos.get("resultado", "Resuelto"), veces_exito=1,
                 validacion={"estado": estado,
                             "metodo": "Fuente documental (registrada por el administrador)" if respaldo else "",
                             "fecha": str(date.today()), "respaldo": respaldo,
                             "observacion": datos.get("observacion", "")},
                 origen="Agregado por el administrador",
                 so_aplicable=list(datos.get("so_aplicable") or [datos["so"].split()[0]]),
                 conexion_aplicable=list(datos.get("conexion_aplicable") or ["Cableada", "Wi-Fi"]),
                 dispositivo_aplicable=list(datos.get("dispositivo_aplicable") or ["PC de escritorio", "Laptop"]))
    bc.casos.append(bc.preparar_caso(nuevo))
    if guardar:
        bc.guardar_casos()
    return f"Se agregó el caso {nuevo.id} con estado «{estado}»."


def validar_caso(motor: MotorInferencia, id_caso: str, respaldo: list[dict], clave: str | None,
                 estado: str = "Validado", guardar: bool = True) -> str:
    """Agrega el respaldo documental a un caso pendiente y lo activa para la recuperación."""
    _exigir_clave(clave)
    c = motor.bc.caso(id_caso)
    if c is None:
        raise ValueError(f"No existe el caso {id_caso}.")
    if not respaldo:
        raise ValueError("Para validar un caso debe indicar al menos una fuente de respaldo.")
    for x in respaldo:
        if not motor.bc.fuente(x.get("fuente", "")):
            raise ValueError(f"La fuente «{x.get('fuente')}» no está registrada.")
    c.validacion.update({"estado": estado, "metodo": "Fuente documental (registrada por el administrador)",
                         "fecha": str(date.today())})
    c.validacion.setdefault("respaldo", []).extend(respaldo)
    if guardar:
        motor.bc.guardar_casos()
    return f"El caso {id_caso} quedó «{estado}» y ya participa en la recuperación."


def rechazar_caso(motor: MotorInferencia, id_caso: str, clave: str | None, guardar: bool = True) -> str:
    """Elimina un caso pendiente que no pudo respaldarse (mantenimiento de la base [11])."""
    _exigir_clave(clave)
    c = motor.bc.caso(id_caso)
    if c is None or c.estado != "Pendiente":
        raise ValueError("Solo se pueden rechazar casos «Pendiente».")
    motor.bc.casos.remove(c)
    if guardar:
        motor.bc.guardar_casos()
    return f"Se eliminó el caso pendiente {id_caso}."


def agregar_fuente_tecnica(bc: BaseConocimientos, datos: dict, clave: str | None, guardar: bool = True) -> str:
    """Registra una fuente técnica nueva (Tnn). Exige título, organización y URL."""
    _exigir_clave(clave)
    for campo in ("titulo", "organizacion", "url"):
        if not datos.get(campo, "").strip():
            raise ValueError(f"Falta el campo «{campo}» de la fuente.")
    if not re.match(r"https?://", datos["url"].strip()):
        raise ValueError("La URL debe empezar con http:// o https://")
    if any(t["url"].strip() == datos["url"].strip() for t in bc.fuentes_json["tecnicas"]):
        raise ValueError("Esa URL ya está registrada como fuente.")
    nuevo_id = f"T{max(int(t['id'][1:]) for t in bc.fuentes_json['tecnicas']) + 1:02d}"
    fuente = {"id": nuevo_id, "clave": datos.get("clave", nuevo_id), "titulo": datos["titulo"].strip(),
              "organizacion": datos["organizacion"].strip(), "anio": datos.get("anio", "s. f.") or "s. f.",
              "url": datos["url"].strip(), "idioma": datos.get("idioma", "es"),
              "tipo": datos.get("tipo", "Documentación oficial"), "verificada": True,
              "fecha_consulta": str(date.today()), "casos": [], "reglas": []}
    bc.fuentes_json["tecnicas"].append(fuente)
    bc.tecnicas[nuevo_id] = fuente
    if guardar:
        bc.guardar_fuentes()
    return nuevo_id


def agregar_sintoma(bc: BaseConocimientos, nombre: str, grupo: str, clave: str | None, guardar: bool = True,
                    tipo: str = "falla") -> str:
    """Amplía el vocabulario cerrado con un síntoma nuevo [5]."""
    _exigir_clave(clave)
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("Escriba el nombre del síntoma.")
    if nombre.lower() in bc.sintoma_codigo:
        raise ValueError(f"El síntoma ya existe: {bc.sintoma_codigo[nombre.lower()]}.")
    cod = f"S{max(int(c[1:]) for c in bc.sintoma_nombre) + 1:03d}"
    bc.catalogo_json["sintomas"].append({"codigo": cod, "nombre": nombre, "grupo": grupo, "pregunta": f"¿{nombre}?",
                                         "tipo": tipo if tipo in ("falla", "contexto") else "falla"})
    bc._cargar_catalogo(bc.catalogo_json)
    if guardar:
        bc.guardar_catalogo()
    return cod


def actualizar_uso_fuentes(bc: BaseConocimientos, guardar: bool = True):
    """Recalcula qué casos usa cada fuente técnica (para la pestaña Fuentes)."""
    uso = {}
    for c in bc.casos:
        for x in c.validacion.get("respaldo", []):
            uso.setdefault(x["fuente"], []).append(c.id)
    for t in bc.fuentes_json["tecnicas"]:
        t["casos"] = uso.get(t["id"], [])
    if guardar:
        bc.guardar_fuentes()


# ═══════════════════════════════════════════════════════════════════════════
# 6. VERIFICACIÓN DE LA BASE DE CONOCIMIENTOS                    [11]; [9] Sec. 5
# ═══════════════════════════════════════════════════════════════════════════
def verificar_base(bc: BaseConocimientos) -> list[tuple[str, str]]:
    """Devuelve una lista de (nivel, mensaje) con nivel «ERROR», «AVISO» u «OK»."""
    out = []
    total = sum(bc.pesos.values())
    out.append(("OK" if abs(total - 1) < 1e-6 else "ERROR", f"Suma de pesos = {total:.2f}"))
    ids = [c.id for c in bc.casos]
    if len(ids) != len(set(ids)):
        out.append(("ERROR", "Hay identificadores de caso repetidos."))
    sin_resp = [c.id for c in bc.casos if c.activo and not c.validacion.get("respaldo")]
    out.append(("ERROR" if sin_resp else "OK",
                f"Casos activos sin respaldo documental: {', '.join(sin_resp) if sin_resp else 'ninguno'}"))
    rotas = sorted({f"{c.id}→{x['fuente']}" for c in bc.casos for x in c.validacion.get("respaldo", [])
                    if not bc.fuente(x["fuente"])})
    for r in bc.reglas.values():
        refs = [e.get("fuente") or "" for e in r.get("evidencias", [])] + list(r.get("fuentes", []))
        for s in r.get("sustituciones_windows_a_ubuntu", []):
            refs += [s["fuente_windows"], s["fuente_ubuntu"]]
        rotas += [f"{r['id']}→{x or 'vacía'}" for x in refs if not bc.fuente(x or "")]
    out.append(("ERROR" if rotas else "OK", f"Referencias a fuentes inexistentes (casos y reglas): {', '.join(rotas) if rotas else 'ninguna'}"))
    sin_evid = sorted({c.id for c in bc.casos for x in c.validacion.get("respaldo", []) if not x.get("evidencia")})
    if sin_evid:
        out.append(("AVISO", f"Respaldos sin fragmento literal (solo nota): {', '.join(sin_evid)}"))
    malos = [c.id for c in bc.casos if any(s not in bc.sintoma_nombre for s in c.sintomas) or not 1 <= len(c.registrados) <= 3]
    out.append(("ERROR" if malos else "OK", f"Casos con síntomas fuera del catálogo o fuera de 1–3: {', '.join(malos) if malos else 'ninguno'}"))
    sin_falla = [c.id for c in bc.casos if not bc.fallas(c.sintomas)]
    out.append(("ERROR" if sin_falla else "OK", f"Casos sin ningún síntoma de falla: {', '.join(sin_falla) if sin_falla else 'ninguno'}"))
    contra = [c.id for c in bc.casos if any(len(c.sintomas & g) > 1 for g in bc.excluyentes)]
    out.append(("ERROR" if contra else "OK", f"Casos con síntomas que se excluyen entre sí: {', '.join(contra) if contra else 'ninguno'}"))
    malcat = [c.id for c in bc.casos if c.codigo_cat not in bc.subcategoria_de]
    out.append(("ERROR" if malcat else "OK", f"Casos con subcategoría inexistente: {', '.join(malcat) if malcat else 'ninguno'}"))
    # duplicados y contradicciones en la parte de problema
    firma = {}
    for c in bc.casos_activos:
        firma.setdefault((c.codigo_cat, c.dispositivo, c.so, c.conexion, frozenset(c.registrados)), []).append(c)
    for grupo in firma.values():
        if len(grupo) > 1:
            sols = {c.solucion.strip().lower() for c in grupo}
            nivel = "AVISO" if len(sols) > 1 else "ERROR"
            out.append((nivel, f"Mismo problema en {', '.join(c.id for c in grupo)}: "
                               + ("soluciones distintas (revisar si son alternativas válidas)" if len(sols) > 1 else "caso duplicado")))
    usados = {s for c in bc.casos for s in c.sintomas}
    no_usados = sorted(set(bc.sintoma_nombre) - usados)
    if no_usados:
        out.append(("AVISO", f"Síntomas del catálogo que ningún caso usa: {', '.join(no_usados)}"))
    tec_usadas = {x["fuente"] for c in bc.casos for x in c.validacion.get("respaldo", [])}
    for r in bc.reglas.values():
        tec_usadas |= {e["fuente"] for e in r.get("evidencias", [])}
        for s in r.get("sustituciones_windows_a_ubuntu", []):
            tec_usadas |= {s["fuente_windows"], s["fuente_ubuntu"]}
    huerfanas = sorted(set(bc.tecnicas) - tec_usadas)
    if huerfanas:
        out.append(("AVISO", f"Fuentes técnicas que no respaldan ningún caso ni regla: {', '.join(huerfanas)}"))
    pend = [c.id for c in bc.casos_pendientes]
    out.append(("AVISO" if pend else "OK", f"Casos pendientes de respaldo (no se usan para recomendar): {', '.join(pend) if pend else 'ninguno'}"))
    out.append(("OK", f"{len(bc.casos_activos)} casos activos · {len(bc.sintoma_nombre)} síntomas · "
                      f"{len(bc.metodologicas)} fuentes metodológicas · {len(bc.tecnicas)} fuentes técnicas"))
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 7. VALIDACIÓN DEJANDO UN CASO FUERA Y ANÁLISIS DE SENSIBILIDAD   [6] Tabla 5; [3]; [7] Sec. 3.5
# ═══════════════════════════════════════════════════════════════════════════
def validar_loo(motor: MotorInferencia, etiqueta: str = "causa", pesos: dict | None = None) -> dict:
    """Cada caso validado se usa como ticket nuevo contra los demás. La respuesta es correcta si el caso
    recuperado tiene el mismo diagnóstico (causa); cada falla tiene al menos dos tickets en la base.
    * Exactitud top-1 = aciertos en el 1.er caso / total                [6] Tabla 5
    * Acierto en los 3 primeros = al menos uno correcto entre los 3     [3]
    * «Evaluables»: casos cuya etiqueta aparece en al menos otro caso (si es única, ningún sistema
      podría acertarla dejando ese caso fuera)."""
    casos = motor.bc.casos_activos
    cuenta = {}
    for c in casos:
        cuenta[getattr(c, etiqueta)] = cuenta.get(getattr(c, etiqueta), 0) + 1
    t1 = t3 = e1 = e3 = ne = sin = 0
    sims, fallos, fallos1 = [], [], []
    for c in casos:
        q = Consulta(c.codigo_cat, c.dispositivo, c.so, c.conexion, set(c.registrados))
        top = motor.recuperar(q, k=3, excluir=c.id, pesos=pesos)
        sin += not top
        ok1 = bool(top) and getattr(top[0].caso, etiqueta) == getattr(c, etiqueta)
        ok3 = any(getattr(r.caso, etiqueta) == getattr(c, etiqueta) for r in top)
        t1 += ok1; t3 += ok3; sims.append(top[0].similitud if top else 0)
        if not ok1:
            fallos1.append((c.id, top[0].caso.id if top else "—"))
        if cuenta[getattr(c, etiqueta)] > 1:
            ne += 1; e1 += ok1; e3 += ok3
            if not ok3:
                fallos.append(c.id)
    n = len(casos)
    return {"etiqueta": etiqueta, "casos": n, "exactitud_top1": t1 / n, "acierto_top3": t3 / n,
            "evaluables": ne, "exactitud_top1_eval": e1 / ne if ne else 0, "acierto_top3_eval": e3 / ne if ne else 0,
            "similitud_media": sum(sims) / n, "casos_fallidos": fallos, "sin_coincidencia": sin,
            "fallos_top1": fallos1}


RUTA_PRUEBAS = Path(__file__).resolve().parent / "validacion" / "casos_prueba.json"


def evaluar_casos_prueba(motor: MotorInferencia, ruta: Path = RUTA_PRUEBAS) -> dict:
    """Ejecuta los casos de prueba (tickets que NO están en la base) y compara con la respuesta esperada.
    * Exactitud = pruebas en que la acción del sistema coincide con la esperada (proponer la causa correcta,
      pedir más datos o no proponer)                                              [6] Tabla 5
    * Acierto en los 3 primeros = una causa esperada aparece entre los 3 casos mostrados      [3]
    * Similitud media del caso recuperado en 1.er lugar."""
    doc = _leer(Path(ruta))
    filas, sims = [], []
    for p in doc["casos"]:
        t = p["ticket"]
        q = Consulta(t["codigo_cat"], t["dispositivo"], t["so"], t["conexion"], set(t["sintomas"]))
        o = motor.resolver(q)
        prop = o["propuesta"]
        causas_ok = set(p["esperado"]["causas"])
        sug = [r.caso.causa for r in o["sugerencias"]]
        if o["sugerencias"]:
            sims.append(o["sugerencias"][0].similitud)
        accion = "proponer" if prop else ("preguntar" if o.get("preguntas") else "no proponer")
        top3 = bool(causas_ok & set(sug)) if causas_ok else None
        esp = p["esperado"]["accion"]
        if esp == "proponer":
            ok = bool(prop) and motor.bc.caso(prop["caso"]).causa in causas_ok
        elif esp == "preguntar":
            ok = accion == "preguntar" and bool(top3)
        else:
            ok = not prop
        filas.append({"id": p["id"], "tipo": p["tipo"], "ticket": t, "esperado": esp,
                      "casos_esperados": p["esperado"]["casos"], "sistema": accion,
                      "caso_sistema": prop["caso"] if prop else (o["sugerencias"][0].caso.id if o["sugerencias"] else "—"),
                      "coincide": ok, "top3": top3, "mensaje": "" if prop else o["mensaje"],
                      "justificacion": p.get("justificacion", "")})
    n = len(filas)
    con_causa = [f for f in filas if f["top3"] is not None]
    por_tipo = {}
    for f in filas:
        d = por_tipo.setdefault(f["tipo"], [0, 0])
        d[0] += f["coincide"]; d[1] += 1
    return {"casos": n, "exactitud": sum(f["coincide"] for f in filas) / n if n else 0,
            "acierto_top3": sum(f["top3"] for f in con_causa) / len(con_causa) if con_causa else 0,
            "similitud_media": sum(sims) / len(sims) if sims else 0,
            "por_tipo": {k: {"aciertos": a, "total": b} for k, (a, b) in por_tipo.items()},
            "filas": filas, "fallos": [f["id"] for f in filas if not f["coincide"]]}


def _pesos_con_sintomas(base: dict, w_sint: float) -> dict:
    """Cambia el peso de los síntomas y reparte el resto en la misma proporción que los pesos base."""
    resto = {a: w for a, w in base.items() if a != "sintomas"}
    s = sum(resto.values())
    return {"sintomas": w_sint, **{a: (1 - w_sint) * w / s for a, w in resto.items()}}


def analisis_sensibilidad(motor: MotorInferencia) -> dict:
    """Justifica con datos los VALORES elegidos (como Heras et al. [7] Sec. 3.5, que fijan su umbral
    experimentalmente y Chen et al. [6] Tabla 5, que comparan valores de k):
    * pesos: peso de los síntomas de 0,4 a 0,8 (el resto se reparte 2:1:1:1);
    * umbral mínimo: de 0,30 a 0,60, midiendo con los casos de prueba la exactitud y cuántos tickets que deberían
      recibir solución la reciben."""
    import itertools
    filas_pesos = []
    for w in (0.4, 0.5, 0.6, 0.7, 0.8):
        p = _pesos_con_sintomas(motor.bc.pesos, w)
        a = validar_loo(motor, "causa", p)
        # Robustez al contexto: cada caso con sus propios síntomas en todas las combinaciones POSIBLES de
        # dispositivo, SO y conexión; cuenta si queda en 1.er lugar un caso con su mismo diagnóstico
        # (o con los mismos síntomas, que el ticket no puede distinguir).
        ok = tot = 0
        for c in motor.bc.casos_activos:
            for d, so_, con in itertools.product(("PC de escritorio", "Laptop"), ("Windows 10", "Windows 11", "Ubuntu 22.04"),
                                                 ("Cableada", "Wi-Fi")):
                q = Consulta(c.codigo_cat, d, so_, con, set(c.registrados))
                if not c.aplica_a(q) or motor.bc.incoherencias(q):
                    continue          # combinación imposible para ese caso
                top = motor.recuperar(q, k=1, pesos=p)
                tot += 1
                ok += bool(top) and (top[0].caso.causa == c.causa or top[0].caso.sintomas == c.sintomas)
        filas_pesos.append({"peso_sintomas": w, "top1_causa": a["exactitud_top1"], "top3_causa": a["acierto_top3"],
                            "similitud_media": a["similitud_media"], "robustez": ok / tot if tot else 0,
                            "actual": abs(w - motor.bc.pesos["sintomas"]) < 1e-9})
    # Umbral mínimo: se mide con los casos de prueba (tickets que no están en la base), porque en la validación
    # dejando un caso fuera el ticket repetido siempre supera cualquier umbral razonable.
    filas_umbral = []
    original = motor.bc.umbral_minimo
    try:
        for u in (0.30, 0.40, 0.50, 0.60):
            motor.bc.umbral_minimo = u
            ev = evaluar_casos_prueba(motor)
            esperan = [f for f in ev["filas"] if f["esperado"] == "proponer"]
            filas_umbral.append({"umbral": u, "exactitud": ev["exactitud"],
                                 "propone": sum(f["sistema"] == "proponer" for f in esperan) / len(esperan) if esperan else 0,
                                 "actual": abs(u - original) < 1e-9})
    finally:
        motor.bc.umbral_minimo = original
    return {"pesos": filas_pesos, "umbral": filas_umbral}


def auditar_coherencia(motor: MotorInferencia, max_sintomas: int = 2) -> dict:
    """Auditoría de coherencia: prueba TODAS las combinaciones de 1 a max_sintomas síntomas de cada subcategoría
    en 8 equipos (PC/laptop × Windows/Ubuntu × cableada/Wi-Fi), omitiendo combinaciones imposibles, y verifica que cada propuesta:
      1) aplique al sistema operativo del ticket;
      2) no contradiga un síntoma del ticket (grupos excluyentes);
      3) explique todos los síntomas de falla que marcó el técnico (directamente o por un síntoma que los implica);
    y que cada caso, con sus propios síntomas y su equipo, recupere su propio diagnóstico (como propuesta o alternativa)."""
    import itertools
    bc = motor.bc
    equipos = [(d, so, con) for d in ("PC de escritorio", "Laptop") for so in ("Windows 11", "Ubuntu 22.04")
               for con in ("Cableada", "Wi-Fi")]
    cuenta = {"consultas": 0, "propone": 0, "pregunta": 0, "escala": 0}
    problemas = []
    for d, so, con in equipos:
        fam = so.split()[0]
        for c in bc.casos_activos:
            if c.aplica_a(Consulta(c.codigo_cat, d, so, con, set())) and c.dispositivo == d and c.conexion == con \
                    and not bc.incoherencias(Consulta(c.codigo_cat, d, so, con, set(c.registrados))):
                o = motor.resolver(Consulta(c.codigo_cat, d, so, con, set(c.registrados)))
                p = o["propuesta"]
                causas = ({bc.caso(p["caso"]).causa} | {a["causa"] for a in p["alternativas"]}) if p else set()
                if c.causa not in causas:
                    problemas.append(f"{c.id} con sus propios síntomas ({d}, {so}) no recupera su propio diagnóstico")
        for sub in bc.subcategoria_de:
            if bc.incoherencias(Consulta(sub, d, so, con, set())):
                continue   # combinación imposible (p. ej. subcategoría Wi-Fi con PC cableada)
            sint = sorted({s for c in bc.casos_activos if c.codigo_cat == sub for s in c.registrados})
            for n in range(1, max_sintomas + 1):
                for comb in itertools.combinations(sint, n):
                    if not bc.fallas(comb) or bc.incoherencias(Consulta(sub, d, so, con, set(comb))):
                        continue
                    cuenta["consultas"] += 1
                    o = motor.resolver(Consulta(sub, d, so, con, set(comb)))
                    p = o["propuesta"]
                    if not p:
                        cuenta["pregunta" if o.get("preguntas") else "escala"] += 1
                        continue
                    cuenta["propone"] += 1
                    cc = bc.caso(p["caso"])
                    nombres = " + ".join(bc.sintoma_nombre[x] for x in comb)
                    if not cc.aplica_a(Consulta(sub, d, so, con, set(comb))):
                        problemas.append(f"{nombres} ({d}, {so}, {con}) → {cc.id}: la solución no aplica a ese equipo")
                    if bc.contradice(set(comb), cc.sintomas):
                        problemas.append(f"{nombres} → {cc.id}: contradice un síntoma del ticket")
                    if bc.fallas(comb) - cc.sintomas:
                        problemas.append(f"{nombres} → {cc.id}: deja un síntoma de falla sin explicar")
    return {**cuenta, "problemas": problemas}


# ═══════════════════════════════════════════════════════════════════════════
# 8. DEMOSTRACIÓN POR CONSOLA
# ═══════════════════════════════════════════════════════════════════════════
def _demo(motor: MotorInferencia):
    bc = motor.bc
    print("═" * 78)
    print("Ejemplo: laptop con Ubuntu, cableada, sin internet con la luz de enlace encendida")
    print("═" * 78)
    q = Consulta(codigo_cat="3.1", dispositivo="Laptop", so="Ubuntu 22.04", conexion="Cableada",
                 sintomas=bc.codigos(["Sin acceso a internet", "Luz de enlace encendida",
                                      "Páginas no cargan por nombre"]))
    out = motor.resolver(q)
    print(f"\nLos {bc.k} casos más similares (¿por qué?):")
    for r in out["sugerencias"]:
        print(motor.explicar(q, r))
    if out["propuesta"]:
        p = out["propuesta"]
        print("\nPropuesta (¿cómo?):")
        print("   Caso base       :", p["caso"])
        print("   Causa probable  :", p["causa_probable"])
        print("   Solución        :", p["solucion"])
        print("   Escalar         :", "Sí" if p["escalar_2do_nivel"] else "No")
        for x in p["reglas"]:
            print(f"   · {x['regla']}: {x['texto']}  [{'; '.join(x['fuentes'])}]")
        for alt in p.get("alternativas", []):
            print(f"   Si no funciona  : {alt['caso']} ({alt['causa']}): {alt['solucion']}")
    else:
        print("\n" + out["mensaje"])
    print("\nRevisión:", motor.revisar(funciono=True, conformidad_usuario=True))
    print("Aviso: el sistema orienta; la decisión final la toma el técnico de soporte.")


def _imprimir_validacion(motor):
    print("\n" + "═" * 78 + "\nValidación dejando un caso fuera (solo casos validados)\n" + "═" * 78)
    for et, nombre in (("causa", "diagnóstico"), ("subcategoria", "subcategoría")):
        m = validar_loo(motor, et)
        print(f"{nombre:<13}: {m['casos']} tickets · top-1 = {m['exactitud_top1']:.1%} · top-3 = {m['acierto_top3']:.1%} · "
              f"similitud media = {m['similitud_media']:.2f}")


def _imprimir_pruebas(motor):
    ev = evaluar_casos_prueba(motor)
    print(f"Casos de prueba: {ev['casos']} · exactitud = {ev['exactitud']:.1%} · acierto en los 3 primeros = "
          f"{ev['acierto_top3']:.1%} · similitud media = {ev['similitud_media']:.2f}")
    print("Por tipo: " + " · ".join(f"{t} {d['aciertos']}/{d['total']}" for t, d in ev["por_tipo"].items()))
    for f in ev["filas"]:
        if not f["coincide"]:
            print(f"  No coincide {f['id']}: esperado «{f['esperado']}», sistema «{f['sistema']}» ({f['caso_sistema']})")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ruta = Path(sys.argv[sys.argv.index("--bc") + 1]) if "--bc" in sys.argv else RUTA_BC
    motor = MotorInferencia(BaseConocimientos(ruta))
    if "--verificar" in sys.argv:
        for nivel, msg in verificar_base(motor.bc):
            print(f"[{nivel:<5}] {msg}")
    elif "--auditar" in sys.argv:
        a = auditar_coherencia(motor)
        print(f"Consultas probadas: {a['consultas']} · propone: {a['propone']} · pide más datos: {a['pregunta']} · escala: {a['escala']}")
        print(f"Problemas de coherencia: {len(a['problemas'])}")
        for x in a["problemas"]:
            print("  -", x)
    elif "--sensibilidad" in sys.argv:
        s = analisis_sensibilidad(motor)
        print("Peso de síntomas → robustez al contexto · LOO top-1 diagnóstico · LOO top-3 · similitud media")
        for f in s["pesos"]:
            print(f"  {f['peso_sintomas']:.1f}{' (actual)' if f['actual'] else '         '}  "
                  f"{f['robustez']:.1%}  ·  {f['top1_causa']:.1%}  ·  {f['top3_causa']:.1%}  ·  {f['similitud_media']:.2f}")
        print("Umbral mínimo → exactitud en casos de prueba · % de propuestas cuando se esperaba propuesta")
        for f in s["umbral"]:
            print(f"  {f['umbral']:.2f}{' (actual)' if f['actual'] else '         '}  {f['exactitud']:.1%}  ·  {f['propone']:.1%}")
    elif "--pruebas" in sys.argv:
        _imprimir_pruebas(motor)
    else:
        if "--validar" not in sys.argv:
            _demo(motor)
        _imprimir_validacion(motor)
