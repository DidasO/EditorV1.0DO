from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from dotenv import load_dotenv
import os
import base64
import json
import hmac
from functools import wraps


def load_environment_vars():
    # Local development (.env in project root).
    load_dotenv()
    # Render secret files are commonly mounted under /etc/secrets.
    for secret_path in ('/etc/secrets/.env', '/etc/secrets/.env.example'):
        if os.path.exists(secret_path):
            load_dotenv(secret_path, override=False)


load_environment_vars()


PDF_TEXT_POINT_FACTOR = 0.90
PDF_TEXT_BASELINE_FACTOR = 0.84
PDF_FONT_METRICS_CACHE = {}
CUSTOM_FONT_FOLDER = os.path.join(os.getcwd(), 'static', 'fonts', 'news_clan')
JN_HELV_FONT_FOLDER = os.path.join(os.getcwd(), 'static', 'fonts', 'helv_jn')
JN_HELV_FONT_MAP = {
    'JN Helvetica':                          'HV______.PFB',
    'JN Helvetica Bold':                     'HVB_____.PFB',
    'JN Helvetica Oblique':                  'HVO_____.PFB',
    'JN Helvetica Bold Oblique':             'HVBO____.PFB',
    'JN Helvetica Light':                    'HelveL62.PFB',
    'JN Helvetica Bold (alt)':               'HelveB39.PFB',
    'JN Helvetica Light Oblique':            'HelvLO19.PFB',
    'JN Helvetica Bold Oblique (alt)':       'HelvBO10.PFB',
    'JN Helvetica Neue Regular':             'HelvNR04.PFB',
    'JN Helvetica Neue Bold':                'HelvNB26.PFB',
    'JN Helvetica Neue Bold (2)':            'HelvNB28.PFB',
    'JN Helvetica Neue Italic':              'HelvNI97.PFB',
    'JN Helvetica Neue Light':               'HelvNL05.PFB',
    'JN Helvetica Neue Medium':              'HelvNM02.PFB',
    'JN Helvetica Neue Heavy':               'HelvNH24.PFB',
    'JN Helvetica Neue Thin':                'HelvNT96.PFB',
    'JN Helvetica Neue Condensed':           'HelvNC04.PFB',
    'JN Helvetica Neue Bold Condensed':      'HelNBC88.PFB',
    'JN Helvetica Neue Bold Italic':         'HelNBI38.PFB',
    'JN Helvetica Neue Bold Italic (2)':     'HelNBI68.PFB',
    'JN Helvetica Neue Heavy Italic':        'HelNHI34.PFB',
    'JN Helvetica Neue Light Condensed':     'HelNLC35.PFB',
    'JN Helvetica Neue Light Italic':        'HelNLI63.PFB',
    'JN Helvetica Neue Medium Condensed':    'HelNMC64.PFB',
    'JN Helvetica Neue Medium Italic':       'HelNMI92.PFB',
    'JN Helvetica Neue Thin Italic':         'HelNTI90.PFB',
    'JN Helvetica Neue Ultra Light':         'HelNUL91.PFB',
    'JN Helvetica Neue Ultra Light Italic':  'HeNULI07.PFB',
}


def parse_color(color_value):
    if not color_value:
        return (0, 0, 0)
    color = str(color_value).strip().lower()
    if color.startswith('#') and len(color) == 7:
        try:
            r = int(color[1:3], 16) / 255.0
            g = int(color[3:5], 16) / 255.0
            b = int(color[5:7], 16) / 255.0
            return (r, g, b)
        except Exception:
            return (0, 0, 0)
    if color.startswith('rgb(') and color.endswith(')'):
        try:
            parts = color[4:-1].split(',')
            r = float(parts[0].strip()) / 255.0
            g = float(parts[1].strip()) / 255.0
            b = float(parts[2].strip()) / 255.0
            return (max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b)))
        except Exception:
            return (0, 0, 0)
    return (0, 0, 0)


def map_font_name(font_family):
    name = (font_family or '').strip().lower()
    normalized = name.replace('-', ' ').replace('_', ' ')
    is_bold = ('bold' in normalized) or ('black' in normalized)
    is_italic = ('italic' in normalized) or ('oblique' in normalized)

    if 'times' in normalized or 'georgia' in normalized:
        if is_bold and is_italic:
            return 'times-bolditalic'
        if is_bold:
            return 'times-bold'
        if is_italic:
            return 'times-italic'
        return 'times-roman'

    if 'courier' in normalized:
        if is_bold and is_italic:
            return 'courier-boldoblique'
        if is_bold:
            return 'courier-bold'
        if is_italic:
            return 'courier-oblique'
        return 'courier'

    # Treat Arial and related sans-serif picks as Helvetica family in PDF base14 fonts.
    if is_bold and is_italic:
        return 'helvetica-boldoblique'
    if is_bold:
        return 'helvetica-bold'
    if is_italic:
        return 'helvetica-oblique'
    return 'helvetica'


def resolve_pdf_font(font_family):
    raw_name = (font_family or '').strip()
    normalized = raw_name.lower()

    if (normalized.startswith('noticias') or normalized.startswith('clanot')) and raw_name:
        candidate = os.path.join(CUSTOM_FONT_FOLDER, f"{raw_name}.otf")
        if os.path.exists(candidate):
            alias = 'custom_' + secure_filename(raw_name).replace('-', '_')[:30]
            return {
                'fontname': alias or 'custom_font',
                'fontfile': candidate
            }

    if raw_name in JN_HELV_FONT_MAP:
        pfb_filename = JN_HELV_FONT_MAP[raw_name]
        pfb_path = os.path.join(JN_HELV_FONT_FOLDER, pfb_filename)
        if os.path.exists(pfb_path):
            alias = 'helv_' + secure_filename(pfb_filename.replace('.PFB', '')).lower()[:30]
            return {
                'fontname': alias or 'helv_font',
                'fontfile': pfb_path
            }

    return {
        'fontname': map_font_name(raw_name),
        'fontfile': None
    }


def get_cached_pymupdf_font(fitz_module, fontname, fontfile=None):
    cache_key = (fontname or '', fontfile or '')
    cached = PDF_FONT_METRICS_CACHE.get(cache_key, None)
    if cached is not None:
        return cached

    font_obj = None
    try:
        if fontfile:
            font_obj = fitz_module.Font(fontfile=fontfile)
        elif fontname:
            font_obj = fitz_module.Font(fontname=fontname)
    except Exception:
        font_obj = None

    # Cache successful objects and failed attempts to avoid repeated construction overhead.
    PDF_FONT_METRICS_CACHE[cache_key] = font_obj or False
    return PDF_FONT_METRICS_CACHE[cache_key]


def measure_pdf_text_width(fitz_module, text, fontname, fontsize, fontfile=None):
    value = str(text or '')

    # Prefer real glyph metrics for embedded/custom fonts to keep auto-fit stable.
    if fontfile:
        try:
            font_obj = get_cached_pymupdf_font(fitz_module, fontname, fontfile)
            if font_obj:
                return float(font_obj.text_length(value, fontsize=float(fontsize)))
        except Exception:
            pass

    try:
        return float(fitz_module.get_text_length(value, fontname=fontname, fontsize=float(fontsize)))
    except Exception:
        return float(len(value) * float(fontsize) * 0.55)


def fit_text_with_ellipsis(fitz_module, text, max_width, fontname, fontsize, fontfile=None):
    value = str(text or '')
    if measure_pdf_text_width(fitz_module, value, fontname, fontsize, fontfile) <= max_width:
        return value
    ellipsis = '...'
    cut = value
    while cut and measure_pdf_text_width(fitz_module, cut + ellipsis, fontname, fontsize, fontfile) > max_width:
        cut = cut[:-1]
    return (cut + ellipsis) if cut else ellipsis


def wrap_text_for_pdf(fitz_module, text, max_width, fontname, fontsize, fontfile=None):
    raw = str(text or '').strip()
    if not raw:
        return []

    words = raw.split(' ')
    lines = []
    current = ''

    def split_long_token(token):
        chunks = []
        chunk = ''
        for ch in token:
            attempt = chunk + ch
            if measure_pdf_text_width(fitz_module, attempt, fontname, fontsize, fontfile) <= max_width or not chunk:
                chunk = attempt
            else:
                chunks.append(chunk)
                chunk = ch
        if chunk:
            chunks.append(chunk)
        return chunks

    for word in words:
        if not word:
            continue

        if measure_pdf_text_width(fitz_module, word, fontname, fontsize, fontfile) > max_width:
            if current:
                lines.append(current.rstrip())
                current = ''
            pieces = split_long_token(word)
            for i, piece in enumerate(pieces):
                if i < len(pieces) - 1:
                    lines.append(piece)
                else:
                    current = piece + ' '
            continue

        candidate = current + word + ' '
        if measure_pdf_text_width(fitz_module, candidate, fontname, fontsize, fontfile) > max_width and current:
            lines.append(current.rstrip())
            current = word + ' '
        else:
            current = candidate

    if current:
        lines.append(current.rstrip())

    return lines


def build_pdf_wrapped_lines(fitz_module, lines, max_width, scale_factor, default_color, min_font_size=6.0):
    rendered = []
    for ln in lines:
        text = (ln.get('text') or '').strip()
        if not text:
            continue
        font_info = resolve_pdf_font(ln.get('fontFamily', 'Arial'))
        fontname = font_info['fontname']
        fontfile = font_info.get('fontfile')
        base_font_size = max(min_font_size, float(ln.get('fontSize', 16)))
        font_size = max(min_font_size, base_font_size * scale_factor * PDF_TEXT_POINT_FACTOR)
        color = parse_color(ln.get('textColor', default_color))
        wrapped = wrap_text_for_pdf(fitz_module, text, max_width, fontname, font_size, fontfile)
        for wrapped_line in wrapped:
            rendered.append({
                'text': wrapped_line,
                'fontname': fontname,
                'fontfile': fontfile,
                'fontsize': font_size,
                'color': color,
                'width': measure_pdf_text_width(fitz_module, wrapped_line, fontname, font_size, fontfile)
            })
    return rendered


def insert_pdf_text(page, fitz_module, x, y, text, rendered):
    kwargs = {
        'fontsize': rendered['fontsize'],
        'fontname': rendered['fontname'],
        'color': rendered['color'],
        'overlay': True
    }
    if rendered.get('fontfile'):
        kwargs['fontfile'] = rendered['fontfile']
    page.insert_text(fitz_module.Point(x, y), text, **kwargs)


def fit_pdf_text_block(fitz_module, lines, max_width, max_height, line_gap, default_color, base_scale=1.0):
    min_scale = 0.15
    max_scale = 12.0
    base_scale = max(min_scale, min(max_scale, float(base_scale) if base_scale is not None else 1.0))
    epsilon = 0.005

    def evaluate(scale_value):
        scale = max(min_scale, min(max_scale, float(scale_value)))
        rendered = build_pdf_wrapped_lines(
            fitz_module,
            lines,
            max_width,
            scale,
            default_color,
            min_font_size=3.0
        )
        scaled_gap = max(0.5, line_gap * scale)
        total_height = 0.0
        for index, item in enumerate(rendered):
            total_height += item['fontsize']
            if index < len(rendered) - 1:
                total_height += scaled_gap
        return {
            'scale': scale,
            'lines': rendered,
            'gap': scaled_gap,
            'fits': total_height <= max_height,
            'height': total_height
        }

    low = min_scale
    high = base_scale
    best = evaluate(min_scale)
    at_base = evaluate(base_scale)

    if at_base['fits']:
        best = at_base
        low = base_scale
        high = base_scale
        while high < max_scale:
            probe_scale = min(max_scale, high * 1.35)
            probe = evaluate(probe_scale)
            if probe['fits']:
                best = probe
                low = probe_scale
                high = probe_scale
                if probe_scale == max_scale:
                    break
            else:
                high = probe_scale
                break
        if high == low:
            high = min(max_scale, low * 1.35)
    else:
        high = base_scale
        at_floor = evaluate(min_scale)
        if at_floor['fits']:
            best = at_floor
            low = min_scale
        else:
            best = at_floor
            low = min_scale
            high = min_scale

    if best['fits'] and high > low:
        for _ in range(18):
            if (high - low) <= epsilon:
                break
            mid = (low + high) / 2.0
            probe = evaluate(mid)
            if probe['fits']:
                best = probe
                low = mid
            else:
                high = mid

    return best['lines'], best['gap'], (not best['fits'])

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
EDITED_FOLDER = os.path.join(os.getcwd(), 'edited')
ALLOWED_EXTENSIONS = {'pdf'}

# ensure directories exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(EDITED_FOLDER):
    os.makedirs(EDITED_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def load_auth_config(target_app):
    username = (os.environ.get('APP_LOGIN_USERNAME') or '').strip()
    password_hash = (os.environ.get('APP_LOGIN_PASSWORD_HASH') or '').strip()
    password_plain = os.environ.get('APP_LOGIN_PASSWORD')
    secret_key = (
        os.environ.get('FLASK_SECRET_KEY')
        or os.environ.get('SECRET_KEY')
        or os.environ.get('FLASH_SECRET_KEY')
        or ''
    ).strip()

    if not secret_key:
        raise RuntimeError('FLASK_SECRET_KEY is required (or SECRET_KEY / FLASH_SECRET_KEY).')

    if not username:
        raise RuntimeError('APP_LOGIN_USERNAME is required.')

    if not password_hash and not password_plain:
        raise RuntimeError('Set APP_LOGIN_PASSWORD_HASH (recommended) or APP_LOGIN_PASSWORD.')

    target_app.secret_key = secret_key
    target_app.config['LOGIN_USERNAME'] = username
    target_app.config['LOGIN_PASSWORD_HASH'] = password_hash
    target_app.config['LOGIN_PASSWORD'] = password_plain


load_auth_config(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('is_authenticated'):
            return redirect(url_for('login'))
        return view_func(*args, **kwargs)
    return wrapped_view


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('is_authenticated'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        valid_username = app.config.get('LOGIN_USERNAME', '')
        valid_password_hash = app.config.get('LOGIN_PASSWORD_HASH', '')
        valid_password = app.config.get('LOGIN_PASSWORD') or ''

        username_ok = hmac.compare_digest(username, valid_username)
        if valid_password_hash:
            password_ok = check_password_hash(valid_password_hash, password)
        else:
            password_ok = hmac.compare_digest(password, valid_password)

        if username_ok and password_ok:
            session['is_authenticated'] = True
            session['username'] = username
            return redirect(url_for('index'))

        flash('Credenciais inválidas')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        # handle PDF upload
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            # redirect to edit page with filename
            return redirect(url_for('edit', filename=filename))
        else:
            flash('Allowed file types are pdf')
            return redirect(request.url)
    return render_template('index.html')


@app.route('/edit/<filename>')
@login_required
def edit(filename):
    # Edit an uploaded/original PDF.
    return render_template(
        'edit.html',
        filename=filename,
        pdf_url=url_for('uploaded_file', filename=filename),
        project_url=None,
        source_pdf_name=filename
    )


@app.route('/edit-saved/<filename>')
@login_required
def edit_saved(filename):
    safe_name = secure_filename(filename)
    pdf_path = os.path.join(EDITED_FOLDER, safe_name)
    if not os.path.exists(pdf_path):
        flash('Ficheiro editado não encontrado')
        return redirect(url_for('index'))

    project_filename = f"{safe_name}.edits.json"
    project_path = os.path.join(EDITED_FOLDER, project_filename)
    project_url = None
    source_pdf_name = safe_name

    if os.path.exists(project_path):
        project_url = url_for('edited_file', filename=project_filename)
        try:
            with open(project_path, 'r', encoding='utf-8') as pf:
                project_data = json.load(pf)
            source_pdf_name = secure_filename(project_data.get('sourcePdf') or safe_name)
        except Exception:
            source_pdf_name = safe_name

    return render_template(
        'edit.html',
        filename=safe_name,
        pdf_url=url_for('edited_file', filename=safe_name),
        project_url=project_url,
        source_pdf_name=source_pdf_name
    )


@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/save', methods=['POST'])
@login_required
def save_image():
    payload = request.json or {}
    data = payload.get('imageData')
    filename = payload.get('filename', 'edited.png')
    custom_pdf_name = payload.get('pdfFilename', '')
    source_pdf_name = secure_filename(payload.get('sourcePdf', ''))
    current_pdf_name = secure_filename(payload.get('currentPdf', ''))
    edits = payload.get('edits')
    editable_edits = payload.get('editableEdits')
    canvas_width = float(payload.get('canvasWidth') or 0)
    canvas_height = float(payload.get('canvasHeight') or 0)
    base_render_scale = float(payload.get('baseRenderScale') or 2.0)
    if base_render_scale <= 0:
        base_render_scale = 2.0

    try:
        import fitz  # PyMuPDF

        def resolve_existing_pdf(*names):
            for raw_name in names:
                safe_name = secure_filename(raw_name or '')
                if not safe_name:
                    continue
                for folder in (UPLOAD_FOLDER, EDITED_FOLDER):
                    candidate = os.path.join(folder, safe_name)
                    if os.path.exists(candidate):
                        return candidate, safe_name
            return None, None

        base_pdf_path, base_pdf_name = resolve_existing_pdf(source_pdf_name, current_pdf_name)

        if base_pdf_path:
            original_pdf = base_pdf_path

            doc = fitz.open(original_pdf)
            page = doc[0]
            page_rect = page.rect
            if canvas_width <= 0 or canvas_height <= 0:
                sx = 1.0
                sy = 1.0
            else:
                sx = page_rect.width / canvas_width
                sy = page_rect.height / canvas_height

            for item in edits or []:
                item_type = item.get('type')
                x = float(item.get('x', 0)) * sx
                y = float(item.get('y', 0)) * sy
                w = float(item.get('w', 0)) * sx
                h = float(item.get('h', 0)) * sy
                rect = fitz.Rect(x, y, x + w, y + h)

                if item_type == 'image':
                    image_data = item.get('imageData', '')
                    if not image_data:
                        continue
                    _, encoded = image_data.split(',', 1)
                    img_binary = base64.b64decode(encoded)
                    page.insert_image(rect, stream=img_binary, keep_proportion=False, overlay=True)

                elif item_type == 'text':
                    bg = parse_color(item.get('bgColor', '#ffffff'))
                    page.draw_rect(rect, color=bg, fill=bg, overlay=True)

                    lines = item.get('lines') or []
                    if not lines and item.get('text'):
                        lines = [{
                            'text': item.get('text', ''),
                            'fontFamily': item.get('fontFamily', 'Arial'),
                            'fontSize': item.get('fontSize', 16),
                            'textColor': item.get('textColor', '#000000')
                        }]

                    # Keep these layout paddings stable across save-time zoom levels.
                    pad_x = max(0.5, 10.0 / base_render_scale)
                    pad_y = max(0.5, 10.0 / base_render_scale)
                    raw_line_spacing = item.get('lineSpacing', 1)
                    try:
                        line_spacing = float(raw_line_spacing)
                    except Exception:
                        line_spacing = 1.0
                    line_gap = max(0.5, 4.0 / base_render_scale) * line_spacing
                    y_cursor = rect.y0 + pad_y
                    y_limit = rect.y1 - max(0.5, 6.0 / base_render_scale)
                    max_width = max(1.0, rect.width - (2.0 * pad_x))
                    auto_fit_text = bool(item.get('autoFitText') or item.get('autoFitSingleLine'))
                    is_centered = (item.get('textAlign') == 'center') or bool(item.get('centerText'))
                    default_color = item.get('textColor', '#000000')

                    line_coord_space = str(item.get('lineCoordSpace') or '').strip().lower()
                    if line_coord_space == 'base':
                        # Base line sizes are independent of current canvas zoom.
                        font_scale_to_pdf = 1.0 / base_render_scale
                    else:
                        # Backward compatibility for older payloads that sent canvas-sized lines.
                        font_scale_to_pdf = sy

                    if auto_fit_text:
                        rendered_lines, scaled_gap, _ = fit_pdf_text_block(
                            fitz,
                            lines,
                            max_width,
                            max(1.0, y_limit - y_cursor),
                            line_gap,
                            default_color,
                            font_scale_to_pdf
                        )
                    else:
                        rendered_lines = build_pdf_wrapped_lines(fitz, lines, max_width, font_scale_to_pdf, default_color)
                        scaled_gap = line_gap

                    if auto_fit_text and len(rendered_lines) == 1:
                        single = rendered_lines[0]
                        draw_x = rect.x0 + pad_x
                        if is_centered:
                            draw_x += max(0.0, (max_width - single['width']) / 2.0)
                        text_top = rect.y0 + pad_y
                        insert_pdf_text(
                            page,
                            fitz,
                            draw_x,
                            text_top + (single['fontsize'] * PDF_TEXT_BASELINE_FACTOR),
                            single['text'],
                            single
                        )
                    else:
                        for index, rendered in enumerate(rendered_lines):
                            font_size = rendered['fontsize']
                            if y_cursor + font_size > y_limit:
                                break
                            draw_value = rendered['text']
                            draw_width = rendered['width']
                            next_y = y_cursor + font_size + scaled_gap
                            has_more = index < len(rendered_lines) - 1
                            if has_more and (next_y + rendered_lines[index + 1]['fontsize'] > y_limit):
                                draw_value = fit_text_with_ellipsis(
                                    fitz,
                                    draw_value + ' ',
                                    max_width,
                                    rendered['fontname'],
                                    font_size,
                                    rendered.get('fontfile')
                                )
                                draw_width = measure_pdf_text_width(
                                    fitz,
                                    draw_value,
                                    rendered['fontname'],
                                    font_size,
                                    rendered.get('fontfile')
                                )

                            draw_x = rect.x0 + pad_x
                            if is_centered:
                                draw_x += max(0.0, (max_width - draw_width) / 2.0)

                            insert_pdf_text(
                                page,
                                fitz,
                                draw_x,
                                y_cursor + (font_size * PDF_TEXT_BASELINE_FACTOR),
                                draw_value,
                                rendered
                            )
                            y_cursor += font_size + scaled_gap
                            if has_more and (next_y + rendered_lines[index + 1]['fontsize'] > y_limit):
                                break

            original_base = os.path.splitext(base_pdf_name)[0]
        else:
            # backward-compatible fallback: raster overlay of full page image
            if not data:
                return jsonify({'status': 'error', 'message': 'Source PDF not found and no raster image data provided'}), 400
            _, encoded = data.split(',', 1)
            binary = base64.b64decode(encoded)
            safe = secure_filename(filename)

            png_name = safe
            png_path = os.path.join(EDITED_FOLDER, png_name)
            with open(png_path, 'wb') as f:
                f.write(binary)

            original_base = safe.replace('-edited.png', '')
            original_pdf = os.path.join(UPLOAD_FOLDER, original_base)
            if not original_pdf.lower().endswith('.pdf'):
                original_pdf += '.pdf'
            if not os.path.exists(original_pdf):
                doc = fitz.open()
                page = doc.new_page()
                page.insert_image(page.rect, stream=binary)
            else:
                doc = fitz.open(original_pdf)
                page = doc[0]
                page.insert_image(page.rect, stream=binary)

            png_name = safe

        if custom_pdf_name:
            custom_pdf_name = secure_filename(custom_pdf_name)
            if not custom_pdf_name.lower().endswith('.pdf'):
                custom_pdf_name += '.pdf'
            pdf_name = custom_pdf_name
        else:
            pdf_name = original_base + '-edited.pdf'
        pdf_path = os.path.join(EDITED_FOLDER, secure_filename(pdf_name))
        doc.save(pdf_path)
        doc.close()

        if (source_pdf_name or current_pdf_name) and isinstance(editable_edits, list):
            project_payload = {
                'sourcePdf': source_pdf_name or current_pdf_name,
                'editedPdf': secure_filename(pdf_name),
                'edits': editable_edits
            }
            project_name = f"{secure_filename(pdf_name)}.edits.json"
            project_path = os.path.join(EDITED_FOLDER, project_name)
            with open(project_path, 'w', encoding='utf-8') as pf:
                json.dump(project_payload, pf, ensure_ascii=False)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    return jsonify({'status': 'ok',
                    'png': url_for('edited_file', filename=png_name) if 'png_name' in locals() else None,
                    'pdf': url_for('edited_file', filename=secure_filename(pdf_name)),
                    'editable': url_for('edited_file', filename=f"{secure_filename(pdf_name)}.edits.json") if (source_pdf_name or current_pdf_name) and isinstance(editable_edits, list) else None,
                    'editUrl': url_for('edit_saved', filename=secure_filename(pdf_name))})

@app.route('/edited/<filename>')
@login_required
def edited_file(filename):
    return send_from_directory(EDITED_FOLDER, filename)


if __name__ == '__main__':
    app.run(debug=True)
