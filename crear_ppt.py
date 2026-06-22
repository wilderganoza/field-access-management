from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.oxml import parse_xml
from lxml import etree
import copy

# ── Colores ──────────────────────────────────────────────
DARK       = RGBColor(0x0A, 0x0C, 0x10)
DARK2      = RGBColor(0x0F, 0x12, 0x18)
DARK3      = RGBColor(0x16, 0x1B, 0x24)
DARK4      = RGBColor(0x1E, 0x25, 0x33)
SLATE      = RGBColor(0x2A, 0x33, 0x47)
GOLD       = RGBColor(0xC9, 0xA8, 0x4C)
GOLD_LIGHT = RGBColor(0xE2, 0xC9, 0x7E)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
TEXT_MUTED = RGBColor(0x8A, 0x95, 0xA8)
GREEN      = RGBColor(0x22, 0xC5, 0x5E)
RED        = RGBColor(0xEF, 0x44, 0x44)
AMBER      = RGBColor(0xF5, 0x9E, 0x0B)
BLUE       = RGBColor(0x4A, 0x9E, 0xFF)

W = Inches(13.33)
H = Inches(7.5)

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

blank_layout = prs.slide_layouts[6]  # completamente en blanco

# ── Helpers ───────────────────────────────────────────────

def add_slide():
    return prs.slides.add_slide(blank_layout)

def bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

def box(slide, x, y, w, h, color, transparency=0):
    shape = slide.shapes.add_shape(1, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    if transparency:
        shape.fill.fore_color.theme_color = None
    shape.line.fill.background()
    return shape

def txt(slide, text, x, y, w, h,
        size=18, bold=False, color=WHITE, align=PP_ALIGN.LEFT,
        italic=False, wrap=True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    p  = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.italic = italic
    run.font.name = "Calibri"
    return tb

def txt_multi(slide, lines, x, y, w, h, default_size=18, default_color=WHITE):
    """lines = list of dicts with keys: text, size, bold, color, align, italic, space_before"""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for line in lines:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.alignment = line.get('align', PP_ALIGN.LEFT)
        if line.get('space_before'):
            p.space_before = Pt(line['space_before'])
        run = p.add_run()
        run.text = line.get('text', '')
        run.font.size = Pt(line.get('size', default_size))
        run.font.bold = line.get('bold', False)
        run.font.color.rgb = line.get('color', default_color)
        run.font.italic = line.get('italic', False)
        run.font.name = "Calibri"
    return tb

def accent_bar(slide, y=Inches(0.08)):
    """Línea dorada decorativa superior"""
    box(slide, 0, y, W, Inches(0.035), GOLD)

def slide_number(slide, n, total=9):
    txt(slide, f"{n:02d} / {total:02d}",
        W - Inches(1.4), H - Inches(0.45), Inches(1.2), Inches(0.35),
        size=9, color=SLATE, align=PP_ALIGN.RIGHT)

def tag_pill(slide, text, x, y):
    """Pequeña pastilla con texto"""
    pill = box(slide, x, y, Inches(2.1), Inches(0.32), DARK4)
    pill.line.color.rgb = GOLD
    pill.line.width = Pt(0.75)
    txt(slide, f"◆  {text.upper()}",
        x + Inches(0.12), y + Inches(0.04), Inches(1.9), Inches(0.25),
        size=8, bold=True, color=GOLD, align=PP_ALIGN.LEFT)

def gold_card(slide, x, y, w, h):
    c = box(slide, x, y, w, h, DARK3)
    c.line.color.rgb = RGBColor(0x2A, 0x33, 0x47)
    c.line.width = Pt(0.5)
    return c

def checkmark(slide, x, y, ok=True):
    color = GREEN if ok else RED
    sym   = "✓" if ok else "✗"
    txt(slide, sym, x, y, Inches(0.3), Inches(0.28), size=11, bold=True, color=color)

# ═══════════════════════════════════════════════════════════
# SLIDE 1 — HERO
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK)
accent_bar(sl)

# Fondo degradado sutil — rectángulo semitransparente derecha
r = box(sl, Inches(7.2), 0, Inches(6.1), H, DARK2)

# Logo / Brand
txt_multi(sl, [
    {'text': 'Permit', 'size': 46, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.LEFT},
], Inches(0.55), Inches(0.6), Inches(3), Inches(1.0))
txt_multi(sl, [
    {'text': 'AI',     'size': 46, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT},
], Inches(1.72), Inches(0.6), Inches(1.5), Inches(1.0))

tag_pill(sl, "IA para Operaciones", Inches(0.55), Inches(1.5))

txt_multi(sl, [
    {'text': 'Acceso a campo,',          'size': 36, 'bold': True, 'color': WHITE,      'align': PP_ALIGN.LEFT},
    {'text': 'validado en segundos.',    'size': 36, 'bold': True, 'color': GOLD_LIGHT, 'align': PP_ALIGN.LEFT, 'space_before': 2},
], Inches(0.55), Inches(2.0), Inches(6.2), Inches(1.8))

txt(sl,
    "PermitAI automatiza la verificación de documentos de ingreso\n"
    "mediante IA generativa — eliminando horas de revisión manual\n"
    "y errores humanos costosos.",
    Inches(0.55), Inches(3.75), Inches(6.0), Inches(1.3),
    size=13, color=TEXT_MUTED)

# Stats
for i, (num, label) in enumerate([("95%","Reducción en\ntiempo de verificación"),
                                    ("~4s","Por expediente\ncompleto"),
                                    ("24/7","Disponibilidad\noperativa")]):
    sx = Inches(0.55) + i * Inches(2.0)
    txt(sl, num,   sx, Inches(5.15), Inches(1.8), Inches(0.7), size=28, bold=True, color=GOLD)
    txt(sl, label, sx, Inches(5.82), Inches(1.8), Inches(0.6), size=9,  color=TEXT_MUTED)
    if i < 2:
        box(sl, sx + Inches(1.85), Inches(5.2), Inches(0.02), Inches(0.9), SLATE)

# Mock panel derecho
panel = box(sl, Inches(7.4), Inches(0.7), Inches(5.5), Inches(6.4), DARK3)
panel.line.color.rgb = RGBColor(0x2A, 0x33, 0x47)
panel.line.width = Pt(1)

# Dots de ventana
for ix, c in enumerate([RED, AMBER, GREEN]):
    d = sl.shapes.add_shape(9, Inches(7.6) + ix*Inches(0.22), Inches(0.95), Inches(0.12), Inches(0.12))
    d.fill.solid(); d.fill.fore_color.rgb = c; d.line.fill.background()

txt(sl, "Resultado del análisis", Inches(10.5), Inches(0.88), Inches(2.2), Inches(0.3), size=8, color=TEXT_MUTED, align=PP_ALIGN.RIGHT)

# Veredicto
verd = box(sl, Inches(7.55), Inches(1.35), Inches(5.1), Inches(0.75), RGBColor(0x0D, 0x2A, 0x1A))
verd.line.color.rgb = GREEN; verd.line.width = Pt(0.75)
txt(sl, "✅", Inches(7.65), Inches(1.45), Inches(0.5), Inches(0.5), size=18)
txt(sl, "VEREDICTO FINAL", Inches(8.15), Inches(1.42), Inches(2.5), Inches(0.25), size=7, color=TEXT_MUTED, bold=True)
txt(sl, "APROBADO", Inches(8.15), Inches(1.65), Inches(2.5), Inches(0.35), size=14, color=GREEN, bold=True)
txt(sl, "✓ Confianza alta", Inches(10.8), Inches(1.55), Inches(1.7), Inches(0.4), size=8, color=GREEN, bold=True, align=PP_ALIGN.RIGHT)

items = [
    (True,  "Hoja de vida con experiencia certificada en Lote X"),
    (True,  "Examen médico vigente — Emitido hace 12 días"),
    (True,  "SCTR en vigencia — Cobertura hasta Dic 2025"),
    (False, "Póliza de seguro de vida — No encontrada"),
    (True,  "Curso de seguridad minera vigente"),
]
for i, (ok, label) in enumerate(items):
    iy = Inches(2.25) + i * Inches(0.66)
    box(sl, Inches(7.55), iy, Inches(5.1), Inches(0.58), DARK4).line.fill.background()
    checkmark(sl, Inches(7.65), iy + Inches(0.14), ok)
    c = TEXT_MUTED if ok else RED
    txt(sl, label, Inches(7.98), iy + Inches(0.14), Inches(4.5), Inches(0.35), size=10, color=c)

txt(sl, "Procesado por GPT-4.1  ·  14 archivos  ·  3.2s",
    Inches(7.55), Inches(5.65), Inches(5.1), Inches(0.3), size=8, color=SLATE)

slide_number(sl, 1)

# ═══════════════════════════════════════════════════════════
# SLIDE 2 — EL PROBLEMA
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK2)
accent_bar(sl)

tag_pill(sl, "El Problema", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'La revisión manual es un cuello', 'size': 32, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT},
    {'text': 'de botella que cuesta',           'size': 32, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT, 'space_before': 2},
    {'text': 'vidas y dinero.',                 'size': 32, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.LEFT, 'space_before': 2},
], Inches(0.55), Inches(1.0), Inches(5.8), Inches(2.2))

txt(sl,
    "En operaciones extractivas, el acceso de personal no calificado\n"
    "o con documentación vencida representa el mayor riesgo operacional.",
    Inches(0.55), Inches(3.15), Inches(5.8), Inches(0.8),
    size=12, color=TEXT_MUTED)

pains = [
    ("⏳", "Horas de revisión por expediente",
           "Un revisor tarda entre 45 y 90 minutos por persona verificando PDFs, correos y adjuntos dispersos."),
    ("⚠️", "Errores humanos por volumen",
           "Con alta carga de solicitudes, documentos vencidos pasan inadvertidos — generando incidentes y multas."),
    ("📨", "Información dispersa en correos",
           "Archivos llegan en correos con múltiples adjuntos, ZIPs, formatos heterogéneos — sin estandarización."),
]
for i, (ico, title, desc) in enumerate(pains):
    py = Inches(3.95) + i * Inches(1.05)
    c = box(sl, Inches(0.55), py, Inches(5.8), Inches(0.9), RGBColor(0x14, 0x0A, 0x0A))
    c.line.color.rgb = RED; c.line.width = Pt(0.5)
    txt(sl, ico,   Inches(0.7),  py + Inches(0.18), Inches(0.45), Inches(0.55), size=16)
    txt(sl, title, Inches(1.2),  py + Inches(0.1),  Inches(5.0),  Inches(0.33), size=11, bold=True, color=WHITE)
    txt(sl, desc,  Inches(1.2),  py + Inches(0.44), Inches(5.0),  Inches(0.38), size=9,  color=TEXT_MUTED)

# Costo box (derecha)
cost_bg = box(sl, Inches(7.0), Inches(0.9), Inches(5.8), Inches(3.2), DARK3)
cost_bg.line.color.rgb = RED; cost_bg.line.width = Pt(0.75)

txt(sl, "COSTO ESTIMADO MENSUAL",
    Inches(7.2), Inches(1.15), Inches(5.4), Inches(0.3),
    size=8, bold=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
txt(sl, "$8,400",
    Inches(7.2), Inches(1.45), Inches(5.4), Inches(1.2),
    size=64, bold=True, color=RED, align=PP_ALIGN.CENTER)
txt(sl, "en horas-hombre de revisión",
    Inches(7.2), Inches(2.55), Inches(5.4), Inches(0.35),
    size=11, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
txt(sl,
    "Estimado sobre 4 revisores a tiempo parcial procesando\n"
    "300 solicitudes/mes a 45 min promedio por expediente.",
    Inches(7.2), Inches(2.95), Inches(5.4), Inches(0.8),
    size=10, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

# Cita
quote_bg = box(sl, Inches(7.0), Inches(4.3), Inches(5.8), Inches(1.5), DARK4)
quote_bg.line.color.rgb = GOLD; quote_bg.line.width = Pt(2)
txt(sl,
    '"El mayor riesgo en operaciones de campo no es el peligro\nfísico — es el personal que no debería haber ingresado."',
    Inches(7.25), Inches(4.45), Inches(5.3), Inches(0.95),
    size=10.5, italic=True, color=WHITE)
txt(sl, "— Gerente de Seguridad, operación minera",
    Inches(7.25), Inches(5.45), Inches(5.3), Inches(0.3),
    size=9, bold=True, color=TEXT_MUTED)

slide_number(sl, 2)

# ═══════════════════════════════════════════════════════════
# SLIDE 3 — LA SOLUCIÓN
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK)
accent_bar(sl)

tag_pill(sl, "La Solución", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'PermitAI',                    'size': 34, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.LEFT},
    {'text': ' — el copiloto de',           'size': 34, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT},
    {'text': 'verificación de acceso.',     'size': 34, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT, 'space_before': 2},
], Inches(0.55), Inches(1.0), Inches(9), Inches(1.8))

txt(sl,
    "Una plataforma web que recibe expedientes completos, los procesa con IA de última\n"
    "generación y entrega un veredicto estructurado en segundos.",
    Inches(0.55), Inches(2.75), Inches(9.5), Inches(0.7),
    size=12.5, color=TEXT_MUTED)

features = [
    ("🧠", "IA de vanguardia",        "Powered by GPT-4.1 con 1M tokens de contexto — procesa expedientes completos en una sola llamada."),
    ("📁", "Cualquier formato",        "PDF, Word, Excel, imágenes, correos .eml, RAR y ZIP. Extrae, convierte y analiza todo automáticamente."),
    ("✅", "Checklist inteligente",    "Valida cada documento contra requisitos configurables por tipo de caso: personal, conductor o vehículo."),
    ("📊", "Resultados auditables",    "Cada análisis queda registrado con veredicto, evidencia y justificación — trazabilidad para auditorías."),
    ("⚙️", "100% configurable",        "Checklists, prompts de IA, usuarios y roles administrables sin necesidad de desarrollo adicional."),
    ("🔐", "Seguro y privado",         "JWT, bcrypt, API keys encriptadas, roles diferenciados. Cero documentos almacenados en el servidor."),
]

cols = 3
for i, (ico, title, desc) in enumerate(features):
    col = i % cols
    row = i // cols
    fx = Inches(0.4) + col * Inches(4.3)
    fy = Inches(3.5) + row * Inches(1.75)
    c = gold_card(sl, fx, fy, Inches(4.1), Inches(1.6))

    txt(sl, ico,   fx + Inches(0.2), fy + Inches(0.15), Inches(0.55), Inches(0.55), size=18)
    txt(sl, title, fx + Inches(0.2), fy + Inches(0.72), Inches(3.7),  Inches(0.35), size=11, bold=True, color=WHITE)
    txt(sl, desc,  fx + Inches(0.2), fy + Inches(1.07), Inches(3.7),  Inches(0.5),  size=9,  color=TEXT_MUTED)

slide_number(sl, 3)

# ═══════════════════════════════════════════════════════════
# SLIDE 4 — CÓMO FUNCIONA (PIPELINE)
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK2)
accent_bar(sl)

tag_pill(sl, "Cómo Funciona", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'Del correo al veredicto', 'size': 32, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.CENTER},
    {'text': ' en 5 pasos automáticos.','size': 32, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.CENTER, 'space_before': 2},
], Inches(0.5), Inches(1.0), Inches(12.3), Inches(1.6))

steps = [
    ("1", "Recepción",  "El revisor arrastra el correo o archivos — cualquier formato aceptado."),
    ("2", "Extracción", "Descomprime ZIPs/RARs, parsea el correo y extrae adjuntos automáticamente."),
    ("3", "Análisis",   "GPT-4.1 recibe todos los docs y el checklist en una sola llamada."),
    ("4", "Veredicto",  "Emite APROBADO / RECHAZADO / PENDIENTE con justificación por ítem."),
    ("5", "Registro",   "Resultado guardado con resumen ejecutivo y trazabilidad completa."),
]

sw = Inches(2.3)
gap = Inches(0.25)
for i, (num, name, desc) in enumerate(steps):
    sx = Inches(0.35) + i * (sw + gap)

    # Círculo numerado
    circ = sl.shapes.add_shape(9, sx + Inches(0.7), Inches(2.7), Inches(0.9), Inches(0.9))
    circ.fill.solid(); circ.fill.fore_color.rgb = GOLD
    circ.line.fill.background()
    txt(sl, num, sx + Inches(0.7), Inches(2.73), Inches(0.9), Inches(0.72), size=20, bold=True, color=DARK, align=PP_ALIGN.CENTER)

    # Flecha
    if i < 4:
        txt(sl, "→", sx + sw - Inches(0.1), Inches(2.82), Inches(0.35), Inches(0.45), size=16, color=GOLD)

    c = gold_card(sl, sx, Inches(3.75), sw, Inches(2.35))
    txt(sl, name, sx + Inches(0.15), Inches(3.9), sw - Inches(0.3), Inches(0.4), size=11, bold=True, color=WHITE)
    txt(sl, desc, sx + Inches(0.15), Inches(4.35), sw - Inches(0.3), Inches(1.5), size=9.5, color=TEXT_MUTED)

# Fila inferior — badges y stats
for j, (label, items_list) in enumerate([
    ("Formatos", ["PDF","DOCX","XLSX","JPG/PNG","EML","RAR","ZIP","7Z"]),
    ("Tipos de caso", ["🧑 Personal No Conductor — 7 ítems",
                       "🚗 Personal Conductor — 8 ítems",
                       "🚛 Vehículos / Equipos — 8 ítems"]),
]):
    bx = Inches(0.4) + j * Inches(6.55)
    c = gold_card(sl, bx, Inches(6.25), Inches(6.25), Inches(1.0))
    txt(sl, label.upper(), bx + Inches(0.2), Inches(6.3), Inches(3), Inches(0.28), size=8, bold=True, color=TEXT_MUTED)
    row_txt = "   ".join(items_list) if j == 0 else "\n".join(items_list)
    txt(sl, row_txt, bx + Inches(0.2), Inches(6.6), Inches(5.9), Inches(0.58), size=9.5, color=GOLD if j==0 else WHITE)

c3 = gold_card(sl, Inches(13.3) - Inches(0.35) - Inches(2.7), Inches(6.25), Inches(2.7), Inches(1.0))
txt(sl, "~4 segundos", Inches(10.65), Inches(6.3), Inches(2.45), Inches(0.4), size=20, bold=True, color=GOLD, align=PP_ALIGN.CENTER)
txt(sl, "por expediente completo\nvs. 45–90 min manual", Inches(10.65), Inches(6.68), Inches(2.45), Inches(0.5), size=8, color=GREEN, align=PP_ALIGN.CENTER)

slide_number(sl, 4)

# ═══════════════════════════════════════════════════════════
# SLIDE 5 — FUNCIONALIDADES DETALLE
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK)
accent_bar(sl)

tag_pill(sl, "Funcionalidades", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'Todo lo que un equipo de operaciones', 'size': 30, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT},
    {'text': 'necesita — en un solo lugar.',         'size': 30, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.LEFT, 'space_before': 2},
], Inches(0.55), Inches(1.0), Inches(12), Inches(1.6))

feats = [
    ("📤", "Upload drag-and-drop",
     "Arrastra correos completos con todos sus adjuntos. La plataforma extrae y procesa todo — incluyendo archivos dentro de ZIPs y RARs."),
    ("📋", "Historial auditado",
     "Cada análisis queda registrado con fecha, usuario, resumen y resultados por ítem — accesible para supervisores y auditores."),
    ("👥", "Gestión de usuarios y roles",
     "Roles diferenciados (admin, supervisor, operador, viewer). El administrador gestiona usuarios sin intervención técnica."),
    ("🎛️", "Prompts configurables",
     "Los administradores editan las instrucciones que recibe la IA para cada tipo de caso — desde la interfaz web, sin código."),
    ("🌙", "Interfaz adaptable",
     "Modo oscuro / claro. Diseño responsive. Pensada para operadores que usan la plataforma todo el día sin fatiga visual."),
    ("🔑", "API Key propia o gestionada",
     "El cliente puede usar su propia clave de OpenAI o contratar el modelo gestionado. Flexibilidad total de facturación."),
]

for i, (ico, title, desc) in enumerate(feats):
    col = i % 2
    row = i // 2
    fx = Inches(0.4) + col * Inches(6.5)
    fy = Inches(2.7) + row * Inches(1.55)
    c = gold_card(sl, fx, fy, Inches(6.2), Inches(1.4))

    txt(sl, ico,   fx + Inches(0.2),  fy + Inches(0.2),  Inches(0.55), Inches(0.55), size=18)
    txt(sl, title, fx + Inches(0.85), fy + Inches(0.2),  Inches(5.2),  Inches(0.38), size=11.5, bold=True, color=WHITE)
    txt(sl, desc,  fx + Inches(0.85), fy + Inches(0.6),  Inches(5.2),  Inches(0.7),  size=9.5,  color=TEXT_MUTED)

slide_number(sl, 5)

# ═══════════════════════════════════════════════════════════
# SLIDE 6 — ROI
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK2)
accent_bar(sl)

tag_pill(sl, "Retorno de Inversión", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'Los números hablan', 'size': 32, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT},
    {'text': 'por sí solos.',      'size': 32, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.LEFT, 'space_before': 2},
], Inches(0.55), Inches(1.0), Inches(7), Inches(1.6))

metrics = [("95%","Reducción en tiempo\nde verificación"),
           ("300+","Solicitudes procesadas\nal mes sin esfuerzo"),
           ("$0","Costo por error humano\nde aprobación incorrecta"),
           ("3.2s","Tiempo promedio\nde análisis completo")]

mw = Inches(2.9)
for i, (num, label) in enumerate(metrics):
    mx = Inches(0.4) + i * (mw + Inches(0.25))
    c = gold_card(sl, mx, Inches(2.65), mw, Inches(1.6))
    # barra inferior dorada
    bar = box(sl, mx, Inches(2.65) + Inches(1.6) - Inches(0.05), mw, Inches(0.05), GOLD)
    txt(sl, num,   mx, Inches(2.8),  mw, Inches(0.8), size=30, bold=True, color=GOLD, align=PP_ALIGN.CENTER)
    txt(sl, label, mx, Inches(3.62), mw, Inches(0.55), size=9, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

# Tabla comparativa
headers = ["Criterio", "Proceso Manual", "PermitAI ✓"]
rows = [
    ["Tiempo por expediente",  "45–90 minutos",   "~4 segundos"],
    ["Capacidad diaria",       "8–12 expedientes/revisor", "Ilimitada"],
    ["Consistencia",           "Variable (fatiga)", "100% uniforme"],
    ["Trazabilidad",           "Parcial (planillas)", "Completa y auditable"],
    ["Disponibilidad",         "Horario laboral",  "24/7/365"],
    ["Costo por expediente",   "~$28 USD",         "<$0.50 USD"],
]

col_widths = [Inches(3.2), Inches(3.0), Inches(3.0)]
col_x = [Inches(0.4), Inches(3.65), Inches(6.7)]
ty = Inches(4.45)

# Cabecera
for ci, (h, cx, cw) in enumerate(zip(headers, col_x, col_widths)):
    hbg = box(sl, cx, ty, cw - Inches(0.05), Inches(0.38), DARK4)
    if ci == 2:
        hbg.fill.fore_color.rgb = RGBColor(0x1A, 0x15, 0x05)
        hbg.line.color.rgb = GOLD; hbg.line.width = Pt(0.75)
    color = GOLD if ci == 2 else TEXT_MUTED
    txt(sl, h, cx + Inches(0.15), ty + Inches(0.06), cw - Inches(0.25), Inches(0.28),
        size=9, bold=True, color=color)

for ri, row in enumerate(rows):
    ry = ty + Inches(0.42) + ri * Inches(0.38)
    alt = RGBColor(0x12, 0x17, 0x1F) if ri % 2 else DARK3
    for ci, (cell, cx, cw) in enumerate(zip(row, col_x, col_widths)):
        cbg = box(sl, cx, ry, cw - Inches(0.05), Inches(0.36), alt)
        if ci == 2:
            cbg.fill.fore_color.rgb = RGBColor(0x0C, 0x14, 0x07) if ri % 2 else RGBColor(0x10, 0x1A, 0x08)
        col_c = GREEN if ci == 2 else (RED if ci == 1 else WHITE)
        txt(sl, cell, cx + Inches(0.15), ry + Inches(0.06), cw - Inches(0.25), Inches(0.26),
            size=9, color=col_c, bold=(ci == 2))

slide_number(sl, 6)

# ═══════════════════════════════════════════════════════════
# SLIDE 7 — PRECIOS
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK)
accent_bar(sl)

tag_pill(sl, "Modelo Comercial", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'Planes diseñados para cada', 'size': 30, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.CENTER},
    {'text': 'escala de operación.',       'size': 30, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.CENTER, 'space_before': 2},
], Inches(0.5), Inches(1.0), Inches(12.3), Inches(1.6))

plans = [
    {
        "name": "STARTER",
        "price": "$490",
        "period": "/ mes",
        "sub": "Hasta 100 análisis/mes · 5 usuarios",
        "features": [
            "3 tipos de caso predefinidos",
            "Historial de 90 días",
            "Soporte por email",
            "Dashboard básico",
            "API key propia del cliente",
        ],
        "featured": False,
    },
    {
        "name": "PROFESSIONAL",
        "price": "$1,200",
        "period": "/ mes",
        "sub": "Análisis ilimitados · 20 usuarios",
        "features": [
            "Casos y checklists personalizados",
            "Historial ilimitado",
            "Gestión de roles avanzada",
            "Prompts configurables por admin",
            "Soporte prioritario",
            "API key gestionada incluida",
            "Onboarding personalizado",
        ],
        "featured": True,
    },
    {
        "name": "ENTERPRISE",
        "price": "A medida",
        "period": "",
        "sub": "Multi-sitio · Usuarios ilimitados",
        "features": [
            "Deploy en infraestructura propia",
            "Integración con sistemas existentes",
            "SLA garantizado",
            "Modelo de IA privado (opcional)",
            "Soporte 24/7 dedicado",
            "Capacitación in-situ",
        ],
        "featured": False,
    },
]

pw = Inches(3.9)
for i, plan in enumerate(plans):
    px = Inches(0.4) + i * (pw + Inches(0.27))
    py = Inches(2.55)
    ph = Inches(4.65)
    c = gold_card(sl, px, py, pw, ph)
    if plan["featured"]:
        c.line.color.rgb = GOLD; c.line.width = Pt(1.5)
        badge_bg = box(sl, px + Inches(1.05), py - Inches(0.22), Inches(1.8), Inches(0.38), GOLD)
        txt(sl, "MÁS POPULAR", px + Inches(1.05), py - Inches(0.18), Inches(1.8), Inches(0.28),
            size=8, bold=True, color=DARK, align=PP_ALIGN.CENTER)

    txt(sl, plan["name"],  px + Inches(0.2), py + Inches(0.2),  pw - Inches(0.4), Inches(0.3), size=9, bold=True, color=TEXT_MUTED)
    txt(sl, plan["price"], px + Inches(0.2), py + Inches(0.52), pw - Inches(0.4), Inches(0.72), size=28, bold=True, color=GOLD if plan["featured"] else WHITE)
    if plan["period"]:
        txt(sl, plan["period"], px + Inches(0.2), py + Inches(1.22), pw - Inches(0.4), Inches(0.28), size=10, color=TEXT_MUTED)
    txt(sl, plan["sub"], px + Inches(0.2), py + Inches(1.5), pw - Inches(0.4), Inches(0.3), size=8.5, color=TEXT_MUTED)

    # Separador
    box(sl, px + Inches(0.2), py + Inches(1.85), pw - Inches(0.4), Inches(0.01), SLATE)

    for fi, feat in enumerate(plan["features"]):
        fy = py + Inches(1.98) + fi * Inches(0.38)
        txt(sl, "✓", px + Inches(0.2), fy, Inches(0.3), Inches(0.3), size=10, bold=True, color=GOLD)
        txt(sl, feat, px + Inches(0.5), fy, pw - Inches(0.65), Inches(0.3), size=9, color=WHITE if plan["featured"] else TEXT_MUTED)

txt(sl,
    "Todos los planes incluyen 14 días de prueba gratuita  ·  Sin compromiso de permanencia  ·  Setup en 24 horas",
    Inches(0.5), Inches(7.18), Inches(12.3), Inches(0.3),
    size=8.5, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

slide_number(sl, 7)

# ═══════════════════════════════════════════════════════════
# SLIDE 8 — TECNOLOGÍA & SEGURIDAD
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK2)
accent_bar(sl)

tag_pill(sl, "Tecnología & Seguridad", Inches(0.55), Inches(0.55))

txt_multi(sl, [
    {'text': 'Construido sobre infraestructura', 'size': 28, 'bold': True, 'color': WHITE, 'align': PP_ALIGN.LEFT},
    {'text': 'empresarial y segura.',            'size': 28, 'bold': True, 'color': GOLD,  'align': PP_ALIGN.LEFT, 'space_before': 2},
], Inches(0.55), Inches(1.0), Inches(9), Inches(1.6))

# Columna izq — Stack tech
tech = [("React 19", RGBColor(0x61,0xDB,0xFB)), ("Node.js", RGBColor(0x68,0xA0,0x63)),
        ("PostgreSQL", RGBColor(0x33,0x67,0x91)), ("GPT-4.1", RGBColor(0x10,0xA3,0x7F)),
        ("Express 5", RGBColor(0xE0,0x4E,0x2F)), ("Vite", RGBColor(0xFF,0xD0,0x2F)),
        ("Render", RGBColor(0xFF,0x61,0x54)), ("Railway", RGBColor(0xC4,0x88,0xF5))]

cols_tech = 4
for i, (name, color) in enumerate(tech):
    col = i % cols_tech
    row = i // cols_tech
    tx = Inches(0.4) + col * Inches(1.6)
    ty = Inches(2.8) + row * Inches(0.6)
    chip = gold_card(sl, tx, ty, Inches(1.5), Inches(0.48))
    dot = sl.shapes.add_shape(9, tx + Inches(0.15), ty + Inches(0.17), Inches(0.14), Inches(0.14))
    dot.fill.solid(); dot.fill.fore_color.rgb = color; dot.line.fill.background()
    txt(sl, name, tx + Inches(0.35), ty + Inches(0.1), Inches(1.1), Inches(0.28), size=9.5, color=WHITE)

# Capacidades IA
cap_bg = gold_card(sl, Inches(0.4), Inches(4.1), Inches(6.55), Inches(1.6))
txt(sl, "CAPACIDADES DE IA", Inches(0.6), Inches(4.2), Inches(4), Inches(0.3), size=8, bold=True, color=TEXT_MUTED)
caps = [("Ventana de contexto", "1,000,000 tokens"),
        ("Visión de documentos", "Incluida"),
        ("Salida estructurada JSON", "Nativa"),
        ("Modelo", "GPT-4.1")]
for i, (k, v) in enumerate(caps):
    cy = Inches(4.55) + i * Inches(0.27)
    txt(sl, k, Inches(0.6), cy, Inches(3.5), Inches(0.25), size=9, color=TEXT_MUTED)
    txt(sl, v, Inches(5.0), cy, Inches(1.8), Inches(0.25), size=9, bold=True, color=GREEN, align=PP_ALIGN.RIGHT)

# Columna der — Seguridad
tag_pill(sl, "Seguridad", Inches(7.0), Inches(0.55))

security = [("🔐","JWT con expiración configurable"), ("🛡️","Contraseñas hasheadas con bcrypt"),
            ("🔑","API keys encriptadas en DB"),     ("👤","Control de acceso por rol"),
            ("🌐","HTTPS en todas las rutas"),        ("📋","Auditoría de accesos completa"),
            ("🗄️","Base de datos aislada por cliente"),("⚡","Deploy en nube privada")]

for i, (ico, label) in enumerate(security):
    col = i % 2; row = i // 2
    sx = Inches(7.0) + col * Inches(3.15)
    sy = Inches(1.0) + row * Inches(0.72)
    sb = gold_card(sl, sx, sy, Inches(3.0), Inches(0.6))
    sb.line.color.rgb = BLUE; sb.line.width = Pt(0.5)
    txt(sl, ico,   sx + Inches(0.15), sy + Inches(0.14), Inches(0.4), Inches(0.38), size=13)
    txt(sl, label, sx + Inches(0.58), sy + Inches(0.16), Inches(2.3), Inches(0.32), size=9, color=WHITE)

# Cita
qb = box(sl, Inches(7.0), Inches(3.95), Inches(6.1), Inches(1.3), DARK4)
qb.line.color.rgb = GOLD; qb.line.width = Pt(2)
txt(sl, '"El sistema almacena cero documentos de los clientes —\nsolo los resultados del análisis. La privacidad es estructural."',
    Inches(7.25), Inches(4.1), Inches(5.6), Inches(0.9), size=10.5, italic=True, color=WHITE)

slide_number(sl, 8)

# ═══════════════════════════════════════════════════════════
# SLIDE 9 — CTA FINAL
# ═══════════════════════════════════════════════════════════
sl = add_slide()
bg(sl, DARK)
accent_bar(sl)

# Glow central
glow = sl.shapes.add_shape(9, Inches(3.5), Inches(1.5), Inches(6.3), Inches(5.0))
glow.fill.solid(); glow.fill.fore_color.rgb = RGBColor(0x15, 0x12, 0x05)
glow.line.fill.background()

tag_pill(sl, "Próximo Paso", Inches(4.6), Inches(0.55))

txt_multi(sl, [
    {'text': '¿Listo para transformar su proceso', 'size': 30, 'bold': True, 'color': WHITE,      'align': PP_ALIGN.CENTER},
    {'text': 'de verificación de acceso?',         'size': 30, 'bold': True, 'color': GOLD_LIGHT, 'align': PP_ALIGN.CENTER, 'space_before': 2},
], Inches(1.0), Inches(1.05), Inches(11.3), Inches(1.8))

txt(sl,
    "Agende una demo de 30 minutos y vea PermitAI procesar expedientes reales\n"
    "de su operación — sin compromisos y sin tarjeta de crédito.",
    Inches(2.0), Inches(2.85), Inches(9.3), Inches(0.8),
    size=13, color=TEXT_MUTED, align=PP_ALIGN.CENTER)

# Oferta box
offer = box(sl, Inches(3.3), Inches(3.75), Inches(6.7), Inches(0.85), RGBColor(0x15, 0x12, 0x05))
offer.line.color.rgb = GOLD; offer.line.width = Pt(1)
txt(sl, "OFERTA DE LANZAMIENTO",
    Inches(3.3), Inches(3.82), Inches(6.7), Inches(0.28),
    size=7.5, bold=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
txt(sl, "30 días de prueba gratuita  ·  Sin tarjeta de crédito  ·  Setup en 24 horas",
    Inches(3.3), Inches(4.1), Inches(6.7), Inches(0.38),
    size=11, bold=True, color=GOLD, align=PP_ALIGN.CENTER)

# Botones
b1 = box(sl, Inches(3.3), Inches(4.75), Inches(3.15), Inches(0.6), GOLD)
b1.line.fill.background()
txt(sl, "📅  Agendar Demo gratuita", Inches(3.3), Inches(4.82), Inches(3.15), Inches(0.42), size=11, bold=True, color=DARK, align=PP_ALIGN.CENTER)

b2 = box(sl, Inches(6.65), Inches(4.75), Inches(3.15), Inches(0.6), DARK3)
b2.line.color.rgb = GOLD; b2.line.width = Pt(1)
txt(sl, "💬  Hablar con un especialista", Inches(6.65), Inches(4.82), Inches(3.15), Inches(0.42), size=11, bold=True, color=GOLD, align=PP_ALIGN.CENTER)

# Cards contacto
contacts = [("✉️","Email","contacto@permitai.com"),
            ("📱","WhatsApp Business","+51 999 000 000"),
            ("🌐","Web","www.permitai.com")]
cw = Inches(3.7)
for i, (ico, label, val) in enumerate(contacts):
    cx = Inches(0.95) + i * (cw + Inches(0.25))
    c = gold_card(sl, cx, Inches(5.6), cw, Inches(1.1))
    txt(sl, ico,   cx + cw/2 - Inches(0.25), Inches(5.68), Inches(0.5),  Inches(0.5),  size=18, align=PP_ALIGN.CENTER)
    txt(sl, label, cx,                         Inches(6.18), cw,           Inches(0.25), size=7.5, color=TEXT_MUTED, bold=True, align=PP_ALIGN.CENTER)
    txt(sl, val,   cx,                         Inches(6.42), cw,           Inches(0.25), size=10.5, color=WHITE, bold=True, align=PP_ALIGN.CENTER)

# Logo final
txt(sl, "Permit", Inches(5.25), Inches(6.93), Inches(1.5), Inches(0.55), size=22, bold=True, color=GOLD, align=PP_ALIGN.RIGHT)
txt(sl, "AI",     Inches(6.73), Inches(6.93), Inches(0.75), Inches(0.55), size=22, bold=True, color=WHITE)
txt(sl, "Verificación inteligente de acceso a campo  ·  Powered by GPT-4.1",
    Inches(2.5), Inches(7.2), Inches(8.3), Inches(0.28), size=8, color=SLATE, align=PP_ALIGN.CENTER)

slide_number(sl, 9)

# ── Guardar ──────────────────────────────────────────────
prs.save("/home/user/field-access-management/PermitAI_Presentacion.pptx")
print("✅ PPTX generado exitosamente")
