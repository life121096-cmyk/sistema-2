from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
import gc
from flask_mysqldb import MySQL
from flask_mysqldb import MySQL
import json
from datetime import datetime
# New tables for Excel templates (run once via migration script)
# CREATE TABLE IF NOT EXISTS excel_templates (
#   id INT AUTO_INCREMENT PRIMARY KEY,
#   name VARCHAR(255) NOT NULL,
#   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
# );
# CREATE TABLE IF NOT EXISTS excel_template_mappings (
#   id INT AUTO_INCREMENT PRIMARY KEY,
#   template_id INT NOT NULL,
#   column_name VARCHAR(255) NOT NULL,
#   value VARCHAR(255) NOT NULL,
#   FOREIGN KEY (template_id) REFERENCES excel_templates(id) ON DELETE CASCADE
# );

import os
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'excel_manager_secret_key_2024'

# ─── MySQL Config (XAMPP) ────────────────────────────────────────────
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''   # XAMPP default: sin contraseña
app.config['MYSQL_DB'] = 'excel_manager'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# Ensure custom tables exist (run once at startup)
with app.app_context():
    cur = mysql.connection.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS custom_headers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            file_id INT NOT NULL,
            column_index INT NOT NULL,
            header_name VARCHAR(255) NOT NULL,
            UNIQUE KEY uq_file_col (file_id, column_index)
        ) ENGINE=InnoDB;
        CREATE TABLE IF NOT EXISTS row_images (
            id INT AUTO_INCREMENT PRIMARY KEY,
            file_id INT NOT NULL,
            row_index INT NOT NULL,
            image_path VARCHAR(500) NOT NULL,
            UNIQUE KEY uq_file_row (file_id, row_index)
        ) ENGINE=InnoDB;
    """)
    cur.close()

# API: obtener nombres de columnas (personalizados)
@app.route('/api/columns/<int:file_id>')
def api_get_columns(file_id):
    # Load original column names from the stored file
    cur = mysql.connection.cursor()
    cur.execute('SELECT stored_name FROM files WHERE id = %s', (file_id,))
    row = cur.fetchone()
    cur.close()
    if not row:
        return jsonify({'error': 'Archivo no encontrado'}), 404
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], row['stored_name'])
    df = pd.read_excel(file_path)
    # Apply custom headers if any
    cur = mysql.connection.cursor()
    cur.execute('SELECT column_index, header_name FROM custom_headers WHERE file_id = %s', (file_id,))
    custom = {c['column_index']: c['header_name'] for c in cur.fetchall()}
    cur.close()
    columns = list(df.columns)
    for idx, name in custom.items():
        if 0 <= idx < len(columns):
            columns[idx] = name
    return jsonify(columns)

# API: actualizar nombre de columna
@app.route('/api/column-name/<int:file_id>/<int:col_idx>', methods=['POST'])
def api_update_column_name(file_id, col_idx):
    body = request.get_json() or {}
    new_name = body.get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'Nombre requerido'}), 400
    cur = mysql.connection.cursor()
    # Upsert into custom_headers
    cur.execute('SELECT id FROM custom_headers WHERE file_id=%s AND column_index=%s', (file_id, col_idx))
    exists = cur.fetchone()
    if exists:
        cur.execute('UPDATE custom_headers SET header_name=%s WHERE id=%s', (new_name, exists['id']))
    else:
        cur.execute('INSERT INTO custom_headers (file_id, column_index, header_name) VALUES (%s,%s,%s)', (file_id, col_idx, new_name))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})

# API: subir imagen para fila
@app.route('/api/row-image/<int:file_id>/<int:row_idx>', methods=['POST'])
def api_upload_row_image(file_id, row_idx):
    if 'image' not in request.files:
        return jsonify({'error': 'Archivo de imagen requerido'}), 400
    img = request.files['image']
    if img.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    filename = secure_filename(img.filename)
    img_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'row_images')
    os.makedirs(img_dir, exist_ok=True)
    path = os.path.join(img_dir, f'file{file_id}_row{row_idx}_{filename}')
    img.save(path)
    cur = mysql.connection.cursor()
    cur.execute('SELECT id FROM row_images WHERE file_id=%s AND row_index=%s', (file_id, row_idx))
    exists = cur.fetchone()
    if exists:
        cur.execute('UPDATE row_images SET image_path=%s WHERE id=%s', (path, exists['id']))
    else:
        cur.execute('INSERT INTO row_images (file_id, row_index, image_path) VALUES (%s,%s,%s)', (file_id, row_idx, path))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok', 'url': f'/row-image/{file_id}/{row_idx}'})

# Serve row image
@app.route('/row-image/<int:file_id>/<int:row_idx>')
def serve_row_image(file_id, row_idx):
    cur = mysql.connection.cursor()
    cur.execute('SELECT image_path FROM row_images WHERE file_id=%s AND row_index=%s', (file_id, row_idx))
    row = cur.fetchone()
    cur.close()
    if not row:
        return '', 404
    return send_from_directory(os.path.dirname(row['image_path']), os.path.basename(row['image_path']))


# ─── Upload Config ───────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def detect_col_type(series):
    """Detecta el tipo de dato dominante de una serie pandas."""
    import pandas.api.types as pat
    non_null = series.dropna()
    if len(non_null) == 0:
        return 'text'
    if pat.is_datetime64_any_dtype(series):
        return 'date'
    # Intentar parsear como fecha si es object
    if series.dtype == object:
        sample = non_null.head(50).astype(str)
        try:
            parsed = pd.to_datetime(sample, dayfirst=True, errors='coerce')
            if parsed.notna().sum() / len(sample) > 0.7:
                return 'date'
        except Exception:
            pass
    if pat.is_bool_dtype(series):
        return 'boolean'
    if pat.is_integer_dtype(series):
        return 'integer'
    if pat.is_float_dtype(series):
        return 'float'
    return 'text'


def format_value(val, col_type):
    """Formatea un valor según su tipo para mostrarlo en la web."""
    import pandas as pd
    if val == '' or val is None:
        return ''
    try:
        if col_type == 'date':
            if hasattr(val, 'strftime'):
                return val.strftime('%d/%m/%Y')
            parsed = pd.to_datetime(val, dayfirst=True, errors='coerce')
            return parsed.strftime('%d/%m/%Y') if not pd.isnull(parsed) else str(val)
        if col_type == 'integer':
            return f'{int(val):,}'.replace(',', '.')
        if col_type == 'float':
            fval = float(val)
            # Si parece porcentaje (<= 1 y tiene decimales)
            return f'{fval:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        if col_type == 'boolean':
            return 'Sí' if val else 'No'
    except Exception:
        pass
    return str(val)


def read_excel_file(filepath):
    """Lee un archivo Excel/CSV y retorna un dict con hojas, datos y tipos de columna."""
    ext = filepath.rsplit('.', 1)[1].lower()
    sheets = {}
    if ext == 'csv':
        df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
        col_types = {str(c): detect_col_type(df[c]) for c in df.columns}
        df = df.fillna('')
        sheets['Hoja1'] = {
            'columns': [str(c) for c in df.columns],
            'col_types': col_types,
            'data': df.head(1000).values.tolist(),
            'total_rows': len(df)
        }
    else:
        xf = pd.ExcelFile(filepath)
        for sheet_name in xf.sheet_names:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            col_types = {str(c): detect_col_type(df[c]) for c in df.columns}
            df = df.fillna('')
            sheets[str(sheet_name)] = {
                'columns': [str(c) for c in df.columns],
                'col_types': col_types,
                'data': df.head(1000).values.tolist(),
                'total_rows': len(df)
            }
    return sheets


# ────────────────────────────────────────────────────────────────────
# RUTAS
# ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT f.*, 
               COUNT(DISTINCT fs.id) as sheet_count,
               SUM(fs.total_rows) as total_rows
        FROM files f
        LEFT JOIN file_sheets fs ON f.id = fs.file_id
        GROUP BY f.id
        ORDER BY f.uploaded_at DESC
        LIMIT 10
    """)
    recent_files = cur.fetchall()

    cur.execute("SELECT COUNT(*) as total FROM files")
    total_files = cur.fetchone()['total']

    cur.execute("SELECT SUM(file_size) as total_size FROM files")
    size_result = cur.fetchone()
    total_size = size_result['total_size'] or 0

    cur.execute("SELECT SUM(total_rows) as total_rows FROM file_sheets")
    rows_result = cur.fetchone()
    total_rows = rows_result['total_rows'] or 0

    cur.close()
    return render_template('index.html',
                           recent_files=recent_files,
                           total_files=total_files,
                           total_size=total_size,
                           total_rows=total_rows)


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'files' not in request.files:
            flash('No se seleccionaron archivos', 'error')
            return redirect(request.url)

        files = request.files.getlist('files')
        uploaded = 0
        errors = []

        for file in files:
            if file.filename == '':
                continue
            if not allowed_file(file.filename):
                errors.append(f'"{file.filename}" no es un formato válido')
                continue

            filename = secure_filename(file.filename)
            # Evitar duplicados de nombre
            base, ext = os.path.splitext(filename)
            counter = 1
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            while os.path.exists(save_path):
                filename = f"{base}_{counter}{ext}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                counter += 1

            file.save(save_path)
            file_size = os.path.getsize(save_path)

            try:
                sheets = read_excel_file(save_path)
                sheet_names = list(sheets.keys())
                sheet_count = len(sheet_names)

                cur = mysql.connection.cursor()
                cur.execute("""
                    INSERT INTO files (original_name, stored_name, file_size, file_type, sheet_count, uploaded_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (file.filename, filename, file_size,
                      ext.lstrip('.').upper(), sheet_count, datetime.now()))
                file_id = cur.lastrowid

                for sheet_name, sheet_data in sheets.items():
                    columns_json = json.dumps(sheet_data['columns'], ensure_ascii=False)
                    types_json   = json.dumps(sheet_data['col_types'], ensure_ascii=False)
                    cur.execute("""
                        INSERT INTO file_sheets (file_id, sheet_name, total_rows, columns_info, columns_types)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (file_id, sheet_name, sheet_data['total_rows'], columns_json, types_json))

                mysql.connection.commit()
                cur.close()
                uploaded += 1

            except Exception as e:
                os.remove(save_path)
                errors.append(f'Error procesando "{file.filename}": {str(e)}')

        if uploaded:
            flash(f'✅ {uploaded} archivo(s) subido(s) exitosamente', 'success')
        for err in errors:
            flash(err, 'error')

        return redirect(url_for('files'))

    return render_template('upload.html')


@app.route('/files')
def files():
    search = request.args.get('search', '')
    file_type = request.args.get('type', '')
    sort = request.args.get('sort', 'date_desc')
    page = int(request.args.get('page', 1))
    per_page = 12

    order_map = {
        'date_desc': 'f.uploaded_at DESC',
        'date_asc': 'f.uploaded_at ASC',
        'name_asc': 'f.original_name ASC',
        'name_desc': 'f.original_name DESC',
        'size_desc': 'f.file_size DESC',
        'size_asc': 'f.file_size ASC',
    }
    order_clause = order_map.get(sort, 'f.uploaded_at DESC')

    where_clauses = []
    params = []
    if search:
        where_clauses.append("f.original_name LIKE %s")
        params.append(f'%{search}%')
    if file_type:
        where_clauses.append("f.file_type = %s")
        params.append(file_type.upper())

    where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''

    cur = mysql.connection.cursor()
    cur.execute(f"SELECT COUNT(*) as cnt FROM files f {where_sql}", params)
    total = cur.fetchone()['cnt']

    offset = (page - 1) * per_page
    cur.execute(f"""
        SELECT f.*, 
               COUNT(DISTINCT fs.id) as sheet_count,
               COALESCE(SUM(fs.total_rows), 0) as total_rows
        FROM files f
        LEFT JOIN file_sheets fs ON f.id = fs.file_id
        {where_sql}
        GROUP BY f.id
        ORDER BY {order_clause}
        LIMIT %s OFFSET %s
    """, params + [per_page, offset])
    file_list = cur.fetchall()

    cur.execute("SELECT DISTINCT file_type FROM files ORDER BY file_type")
    file_types = [r['file_type'] for r in cur.fetchall()]
    cur.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template('files.html',
                           files=file_list,
                           total=total,
                           page=page,
                           total_pages=total_pages,
                           search=search,
                           file_type=file_type,
                           sort=sort,
                           file_types=file_types)


@app.route('/view/<int:file_id>')
def view_file(file_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
    file_info = cur.fetchone()
    if not file_info:
        flash('Archivo no encontrado', 'error')
        return redirect(url_for('files'))

    cur.execute("SELECT * FROM file_sheets WHERE file_id = %s ORDER BY id", (file_id,))
    sheets = cur.fetchall()
    cur.close()

    for s in sheets:
        s['columns_info'] = json.loads(s['columns_info'])

    return render_template('view.html', file_info=file_info, sheets=sheets)


@app.route('/api/sheet-data/<int:file_id>/<sheet_name>')
def get_sheet_data(file_id, sheet_name):
    cur = mysql.connection.cursor()
    cur.execute("SELECT f.stored_name, fs.columns_types FROM files f "
                "LEFT JOIN file_sheets fs ON f.id = fs.file_id "
                "WHERE f.id = %s AND fs.sheet_name = %s", (file_id, sheet_name))
    row = cur.fetchone()
    # fallback: si no coincide por nombre, tomar la primera hoja
    if not row:
        cur.execute("SELECT f.stored_name, fs.columns_types FROM files f "
                    "LEFT JOIN file_sheets fs ON f.id = fs.file_id "
                    "WHERE f.id = %s ORDER BY fs.id LIMIT 1", (file_id,))
        row = cur.fetchone()
    cur.close()

    if not row:
        return jsonify({'error': 'Archivo no encontrado'}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], row['stored_name'])
    if not os.path.exists(filepath):
        return jsonify({'error': 'Archivo físico no encontrado'}), 404

    # Cargar tipos guardados (puede ser None para archivos subidos antes)
    saved_types = {}
    if row['columns_types']:
        try:
            saved_types = json.loads(row['columns_types'])
        except Exception:
            pass

    try:
        page       = int(request.args.get('page', 1))
        per_page   = int(request.args.get('per_page', 50))
        search_term = request.args.get('search', '')

        ext = filepath.rsplit('.', 1)[1].lower()
        if ext == 'csv':
            df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
        else:
            df = pd.read_excel(filepath, sheet_name=sheet_name)

        # Detectar tipos al vuelo si no están guardados
        col_types = {}
        for c in df.columns:
            key = str(c)
            col_types[key] = saved_types.get(key) or detect_col_type(df[c])

        df = df.fillna('')

        if search_term:
            mask = df.apply(lambda row: row.astype(str).str.contains(
                search_term, case=False, na=False).any(), axis=1)
            df = df[mask]

        total_rows = len(df)
        start = (page - 1) * per_page
        page_df = df.iloc[start:start + per_page]

        col_names = [str(c) for c in df.columns]

        # Formatear valores según tipo
        data = []
        for _, r in page_df.iterrows():
            formatted_row = []
            for c, v in zip(col_names, r.tolist()):
                formatted_row.append(format_value(v, col_types.get(c, 'text')))
            data.append(formatted_row)

        return jsonify({
            'columns':     col_names,
            'col_types':   [col_types.get(c, 'text') for c in col_names],
            'data':        data,
            'total_rows':  total_rows,
            'page':        page,
            'per_page':    per_page,
            'total_pages': max(1, (total_rows + per_page - 1) // per_page)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<int:file_id>')
def download_file(file_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
    file_info = cur.fetchone()
    cur.close()

    if not file_info:
        flash('Archivo no encontrado', 'error')
        return redirect(url_for('files'))

    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        file_info['stored_name'],
        as_attachment=True,
        download_name=file_info['original_name']
    )


@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    import gc
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
    file_info = cur.fetchone()

    if not file_info:
        cur.close()
        return jsonify({'status': 'error', 'message': 'Archivo no encontrado'}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_name'])

    # Primero eliminar registros de la BD
    cur.execute("DELETE FROM file_sheets WHERE file_id = %s", (file_id,))
    cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
    mysql.connection.commit()
    cur.close()

    # Intentar borrar el archivo físico
    file_deleted = False
    if os.path.exists(filepath):
        gc.collect()  # liberar handles de pandas en Windows
        try:
            os.remove(filepath)
            file_deleted = True
        except PermissionError:
            # El archivo está abierto en otro programa (ej. Excel)
            # El registro ya fue borrado de la BD; el archivo queda huérfano
            pass

    # Respuesta según Accept header (fetch o form normal)
    if request.headers.get('Accept', '').startswith('application/json') or \
       request.headers.get('Content-Type', '') == 'application/x-www-form-urlencoded':
        if file_deleted or not os.path.exists(filepath):
            return jsonify({'status': 'ok', 'message': 'Archivo eliminado correctamente'})
        else:
            return jsonify({
                'status': 'warning',
                'message': 'Registro eliminado, pero el archivo físico está en uso por otro programa. '
                           'Cierra el archivo en Excel y bórralo manualmente de la carpeta uploads.'
            })

    # Fallback redirect
    flash('✅ Archivo eliminado correctamente', 'success')
    return redirect(url_for('files'))


@app.route('/api/stats')
def api_stats():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) as total FROM files")
    total_files = cur.fetchone()['total']
    cur.execute("SELECT SUM(file_size) as s FROM files")
    total_size = cur.fetchone()['s'] or 0
    cur.execute("SELECT SUM(total_rows) as r FROM file_sheets")
    total_rows = cur.fetchone()['r'] or 0
    cur.execute("""
        SELECT DATE(uploaded_at) as day, COUNT(*) as cnt
        FROM files
        WHERE uploaded_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        GROUP BY DATE(uploaded_at)
        ORDER BY day
    """)
    uploads_by_day = cur.fetchall()
    for row in uploads_by_day:
        row['day'] = str(row['day'])
    cur.close()
    return jsonify({
        'total_files': total_files,
        'total_size': total_size,
        'total_rows': total_rows,
        'uploads_by_day': uploads_by_day
    })


def parse_input_value(raw_value, col_type):
    """Convierte el valor ingresado por el usuario al tipo correcto (formato español)."""
    if raw_value is None or str(raw_value).strip() == '':
        return None
    v = str(raw_value).strip()
    if col_type == 'integer':
        try:
            return int(v.replace('.', '').replace(',', ''))
        except ValueError:
            return v
    if col_type == 'float':
        try:
            return float(v.replace('.', '').replace(',', '.'))
        except ValueError:
            return v
    if col_type == 'date':
        try:
            parsed = pd.to_datetime(v, dayfirst=True, errors='coerce')
            if not pd.isnull(parsed):
                return parsed.to_pydatetime()
        except Exception:
            pass
        return v
    if col_type == 'boolean':
        return v.lower() in ('sí', 'si', 'yes', 'true', '1')
    return v


def _save_excel_all_sheets(filepath, sheet_name, modified_df):
    """Lee todas las hojas del archivo Excel, reemplaza la hoja indicada y guarda."""
    xl = pd.ExcelFile(filepath)
    sheet_names_list = xl.sheet_names
    all_data = {}
    for sn in sheet_names_list:
        all_data[sn] = modified_df if sn == sheet_name else xl.parse(sn)
    xl.close()
    gc.collect()
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        for sn in sheet_names_list:
            all_data[sn].to_excel(writer, sheet_name=sn, index=False)
    return sheet_names_list


@app.route('/api/edit-cell/<int:file_id>', methods=['POST'])
def edit_cell(file_id):
    body = request.get_json()
    sheet_name = body.get('sheet_name')
    row_index  = int(body.get('row_index', 0))
    col_name   = body.get('col_name')
    col_type   = body.get('col_type', 'text')
    raw_value  = body.get('value', '')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
    file_info = cur.fetchone()
    cur.close()
    if not file_info:
        return jsonify({'error': 'Archivo no encontrado'}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_name'])
    ext = filepath.rsplit('.', 1)[1].lower()
    parsed = parse_input_value(raw_value, col_type)

    try:
        if ext == 'csv':
            df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
            if col_name not in df.columns or row_index >= len(df):
                return jsonify({'error': 'Fila o columna inválida'}), 400
            df.at[row_index, col_name] = parsed
            df.to_csv(filepath, index=False, encoding='utf-8')
        else:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            if col_name not in df.columns or row_index >= len(df):
                return jsonify({'error': 'Fila o columna inválida'}), 400
            df.at[row_index, col_name] = parsed
            _save_excel_all_sheets(filepath, sheet_name, df)

        display = format_value(parsed, col_type) if parsed is not None else ''
        return jsonify({'status': 'ok', 'formatted': display})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/add-row/<int:file_id>', methods=['POST'])
def add_row(file_id):
    body = request.get_json()
    sheet_name = body.get('sheet_name')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
    file_info = cur.fetchone()
    if not file_info:
        cur.close()
        return jsonify({'error': 'Archivo no encontrado'}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_name'])
    ext = filepath.rsplit('.', 1)[1].lower()
    try:
        if ext == 'csv':
            df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
            empty = pd.DataFrame([[None] * len(df.columns)], columns=df.columns)
            df = pd.concat([df, empty], ignore_index=True)
            df.to_csv(filepath, index=False, encoding='utf-8')
        else:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            empty = pd.DataFrame([[None] * len(df.columns)], columns=df.columns)
            df = pd.concat([df, empty], ignore_index=True)
            _save_excel_all_sheets(filepath, sheet_name, df)

        new_total = len(df)
        cur.execute("UPDATE file_sheets SET total_rows=%s WHERE file_id=%s AND sheet_name=%s",
                    (new_total, file_id, sheet_name))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'ok', 'new_total': new_total})
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@app.route('/api/delete-row/<int:file_id>', methods=['POST'])
def delete_row(file_id):
    body = request.get_json()
    sheet_name = body.get('sheet_name')
    row_index  = int(body.get('row_index', -1))

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", (file_id,))
    file_info = cur.fetchone()
    if not file_info:
        cur.close()
        return jsonify({'error': 'Archivo no encontrado'}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_name'])
    ext = filepath.rsplit('.', 1)[1].lower()
    try:
        if ext == 'csv':
            df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
            if row_index < 0 or row_index >= len(df):
                cur.close()
                return jsonify({'error': 'Fila fuera de rango'}), 400
            df = df.drop(index=row_index).reset_index(drop=True)
            df.to_csv(filepath, index=False, encoding='utf-8')
        else:
            df = pd.read_excel(filepath, sheet_name=sheet_name)
            if row_index < 0 or row_index >= len(df):
                cur.close()
                return jsonify({'error': 'Fila fuera de rango'}), 400
            df = df.drop(index=row_index).reset_index(drop=True)
            _save_excel_all_sheets(filepath, sheet_name, df)

        new_total = len(df)
        cur.execute("UPDATE file_sheets SET total_rows=%s WHERE file_id=%s AND sheet_name=%s",
                    (new_total, file_id, sheet_name))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'ok', 'new_total': new_total})
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


# ─── CATÁLOGO GEOGRÁFICO ────────────────────────────────────────────

@app.route('/geo')
def geo():
    cur = mysql.connection.cursor()
    cur.execute("SELECT e.id, e.nombre, COUNT(m.id) as mun_count FROM estados e LEFT JOIN municipios m ON e.id=m.estado_id GROUP BY e.id ORDER BY e.nombre")
    estados = cur.fetchall()
    cur.execute("SELECT COUNT(*) as c FROM municipios")
    total_mun = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM parroquias")
    total_parr = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) as c FROM asics")
    total_asic = cur.fetchone()['c']
    cur.close()
    return render_template('geo.html', estados=estados,
                           total_mun=total_mun, total_parr=total_parr, total_asic=total_asic)


@app.route('/jefes')
def jefes_page():
    cur = mysql.connection.cursor()
    cur.execute("SELECT COUNT(*) as c FROM jefes_asic")
    total_jefes = cur.fetchone()['c']
    cur.execute("SELECT * FROM estados ORDER BY nombre")
    estados = cur.fetchall()
    cur.close()
    return render_template('jefes.html', total_jefes=total_jefes, estados=estados)


# ── API GET ──────────────────────────────────────────────────────────

@app.route('/api/geo/estados')
def api_geo_estados():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM estados ORDER BY nombre")
    data = cur.fetchall()
    cur.close()
    return jsonify(data)


@app.route('/api/geo/municipios')
def api_geo_municipios():
    estado_id = request.args.get('estado_id')
    cur = mysql.connection.cursor()
    if estado_id:
        cur.execute("SELECT * FROM municipios WHERE estado_id=%s ORDER BY nombre", (estado_id,))
    else:
        cur.execute("SELECT m.*, e.nombre as estado_nombre FROM municipios m JOIN estados e ON m.estado_id=e.id ORDER BY e.nombre, m.nombre")
    data = cur.fetchall()
    cur.close()
    return jsonify(data)


@app.route('/api/geo/parroquias')
def api_geo_parroquias():
    municipio_id = request.args.get('municipio_id')
    cur = mysql.connection.cursor()
    if municipio_id:
        cur.execute("SELECT * FROM parroquias WHERE municipio_id=%s ORDER BY nombre", (municipio_id,))
    else:
        cur.execute("SELECT p.*, m.nombre as municipio_nombre FROM parroquias p JOIN municipios m ON p.municipio_id=m.id ORDER BY m.nombre, p.nombre")
    data = cur.fetchall()
    cur.close()
    return jsonify(data)


@app.route('/api/geo/asics')
def api_geo_asics():
    parroquia_id = request.args.get('parroquia_id')
    cur = mysql.connection.cursor()
    if parroquia_id:
        cur.execute("SELECT * FROM asics WHERE parroquia_id=%s ORDER BY nombre", (parroquia_id,))
    else:
        cur.execute("""
            SELECT a.*, p.nombre as parroquia_nombre,
                   m.nombre as municipio_nombre, e.nombre as estado_nombre
            FROM asics a
            LEFT JOIN parroquias p ON a.parroquia_id=p.id
            LEFT JOIN municipios m ON p.municipio_id=m.id
            LEFT JOIN estados e ON m.estado_id=e.id
            ORDER BY a.nombre
        """)
    data = cur.fetchall()
    cur.close()
    return jsonify(data)


# ── API POST (agregar) ────────────────────────────────────────────────

@app.route('/api/geo/estado', methods=['POST'])
def api_add_estado():
    nombre = (request.json or {}).get('nombre', '').strip()
    if not nombre:
        return jsonify({'error': 'Nombre requerido'}), 400
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO estados (nombre) VALUES (%s)", (nombre,))
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()
        return jsonify({'status': 'ok', 'id': new_id, 'nombre': nombre})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/geo/municipio', methods=['POST'])
def api_add_municipio():
    body = request.json or {}
    nombre = body.get('nombre', '').strip()
    estado_id = body.get('estado_id')
    if not nombre or not estado_id:
        return jsonify({'error': 'Nombre y estado requeridos'}), 400
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO municipios (estado_id, nombre) VALUES (%s,%s)", (estado_id, nombre))
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()
        return jsonify({'status': 'ok', 'id': new_id, 'nombre': nombre})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/geo/parroquia', methods=['POST'])
def api_add_parroquia():
    body = request.json or {}
    nombre = body.get('nombre', '').strip()
    municipio_id = body.get('municipio_id')
    if not nombre or not municipio_id:
        return jsonify({'error': 'Nombre y municipio requeridos'}), 400
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO parroquias (municipio_id, nombre) VALUES (%s,%s)", (municipio_id, nombre))
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()
        return jsonify({'status': 'ok', 'id': new_id, 'nombre': nombre})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/geo/asic', methods=['POST'])
def api_add_asic():
    body = request.json or {}
    nombre = body.get('nombre', '').strip()
    parroquia_id = body.get('parroquia_id') or None
    if not nombre:
        return jsonify({'error': 'Nombre requerido'}), 400
    try:
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO asics (nombre, parroquia_id) VALUES (%s,%s)", (nombre, parroquia_id))
        mysql.connection.commit()
        new_id = cur.lastrowid
        cur.close()
        return jsonify({'status': 'ok', 'id': new_id, 'nombre': nombre})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API DELETE ────────────────────────────────────────────────────────

@app.route('/api/geo/estado/<int:item_id>', methods=['DELETE'])
def api_del_estado(item_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM estados WHERE id=%s", (item_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/api/geo/municipio/<int:item_id>', methods=['DELETE'])
def api_del_municipio(item_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM municipios WHERE id=%s", (item_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/api/geo/parroquia/<int:item_id>', methods=['DELETE'])
def api_del_parroquia(item_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM parroquias WHERE id=%s", (item_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/api/geo/asic/<int:item_id>', methods=['DELETE'])
def api_del_asic(item_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM asics WHERE id=%s", (item_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


@app.route('/api/jefes', methods=['GET', 'POST'])
def api_jefes():
    if request.method == 'GET':
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT j.*, 
                   a.nombre as asic_nombre,
                   p.nombre as parroquia_nombre,
                   m.nombre as municipio_nombre, 
                   e.nombre as estado_nombre
            FROM jefes_asic j
            LEFT JOIN asics a ON j.asic_id = a.id
            LEFT JOIN parroquias p ON j.parroquia_id = p.id
            LEFT JOIN municipios m ON j.municipio_id = m.id
            LEFT JOIN estados e ON j.estado_id = e.id
            ORDER BY j.id DESC
        """)
        data = cur.fetchall()
        cur.close()
        return jsonify(data)
    
    if request.method == 'POST':
        body = request.json or {}
        nombre = body.get('nombre', '').strip()
        apellido = body.get('apellido', '').strip()
        telefono = body.get('telefono', '').strip()
        asic_id = body.get('asic_id') or None
        cdi = body.get('cdi', '').strip()
        estado_id = body.get('estado_id') or None
        municipio_id = body.get('municipio_id') or None
        parroquia_id = body.get('parroquia_id') or None

        if not nombre or not apellido or not cdi:
            return jsonify({'error': 'Nombre, Apellido y CDI son requeridos'}), 400

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO jefes_asic (nombre, apellido, telefono, asic_id, cdi, estado_id, municipio_id, parroquia_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (nombre, apellido, telefono, asic_id, cdi, estado_id, municipio_id, parroquia_id))
            mysql.connection.commit()
            new_id = cur.lastrowid
            cur.close()
            return jsonify({'status': 'ok', 'id': new_id})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


@app.route('/api/jefes/<int:item_id>', methods=['DELETE', 'PUT'])
def api_jefe_item(item_id):
    if request.method == 'DELETE':
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM jefes_asic WHERE id=%s", (item_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'ok'})
    elif request.method == 'PUT':
        body = request.json or {}
        nombre = body.get('nombre', '').strip()
        apellido = body.get('apellido', '').strip()
        telefono = body.get('telefono', '').strip()
        asic_id = body.get('asic_id') or None
        cdi = body.get('cdi', '').strip()
        estado_id = body.get('estado_id') or None
        municipio_id = body.get('municipio_id') or None
        parroquia_id = body.get('parroquia_id') or None

        if not nombre or not apellido or not cdi:
            return jsonify({'error': 'Nombre, Apellido y CDI son requeridos'}), 400

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                UPDATE jefes_asic 
                SET nombre=%s, apellido=%s, telefono=%s, asic_id=%s, cdi=%s, estado_id=%s, municipio_id=%s, parroquia_id=%s
                WHERE id=%s
            """, (nombre, apellido, telefono, asic_id, cdi, estado_id, municipio_id, parroquia_id, item_id))
            mysql.connection.commit()
            cur.close()
            return jsonify({'status': 'ok'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500


# ── TEMPLATE MANAGEMENT ────────────────────────────────────────

@app.route('/templates')
def templates_page():
    return render_template('plantillas.html')

# API: list templates
@app.route('/api/templates')
def api_list_templates():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name FROM excel_templates ORDER BY name")
    data = cur.fetchall()
    cur.close()
    return jsonify(data)

# API: create template
@app.route('/api/template', methods=['POST'])
def api_create_template():
    body = request.get_json() or {}
    name = body.get('name', '').strip()
    mappings = body.get('mappings', {})  # dict column->value
    if not name:
        return jsonify({'error': 'Nombre requerido'}), 400
    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO excel_templates (name) VALUES (%s)", (name,))
    tmpl_id = cur.lastrowid
    for col, val in mappings.items():
        cur.execute("INSERT INTO excel_template_mappings (template_id, column_name, value) VALUES (%s,%s,%s)", (tmpl_id, col, val))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok', 'id': tmpl_id})

# API: get template mappings
@app.route('/api/template/<int:tid>')
def api_get_template(tid):
    cur = mysql.connection.cursor()
    cur.execute("SELECT column_name, value FROM excel_template_mappings WHERE template_id=%s", (tid,))
    rows = cur.fetchall()
    cur.close()
    mapping = {r['column_name']: r['value'] for r in rows}
    return jsonify({'id': tid, 'mappings': mapping})

# API: delete template
@app.route('/api/template/<int:tid>', methods=['DELETE'])
def api_del_template(tid):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM excel_templates WHERE id=%s", (tid,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'status': 'ok'})


# ── Rellenar columnas Excel con catálogo ─────────────────────────────

@app.route('/api/fill-columns/<int:file_id>', methods=['POST'])
def fill_columns(file_id):
    body       = request.get_json()
    sheet_name = body.get('sheet_name')
    mappings   = body.get('mappings', {})   # {col_name: value}
    row_from   = int(body.get('row_from', 0))
    row_to     = body.get('row_to')         # None = all

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id=%s", (file_id,))
    file_info = cur.fetchone()
    cur.close()
    if not file_info:
        return jsonify({'error': 'Archivo no encontrado'}), 404

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_info['stored_name'])
    ext = filepath.rsplit('.', 1)[1].lower()
    try:
        if ext == 'csv':
            df = pd.read_csv(filepath, encoding='utf-8', on_bad_lines='skip')
        else:
            df = pd.read_excel(filepath, sheet_name=sheet_name)

        end_idx = int(row_to) if row_to is not None else len(df)
        for col_name, value in mappings.items():
            if col_name in df.columns and value:
                df.loc[row_from:end_idx - 1, col_name] = value

        if ext == 'csv':
            df.to_csv(filepath, index=False, encoding='utf-8')
        else:
            _save_excel_all_sheets(filepath, sheet_name, df)

        return jsonify({'status': 'ok', 'rows_updated': end_idx - row_from})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

