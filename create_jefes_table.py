from flask import Flask
from flask_mysqldb import MySQL

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'excel_manager'

mysql = MySQL(app)

with app.app_context():
    cur = mysql.connection.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS jefes_asic (
            id           INT AUTO_INCREMENT PRIMARY KEY,
            nombre       VARCHAR(100) NOT NULL,
            apellido     VARCHAR(100) NOT NULL,
            asic_id      INT,
            cdi          VARCHAR(200) NOT NULL,
            estado_id    INT,
            municipio_id INT,
            parroquia_id INT,
            FOREIGN KEY (asic_id) REFERENCES asics(id) ON DELETE SET NULL,
            FOREIGN KEY (estado_id) REFERENCES estados(id) ON DELETE SET NULL,
            FOREIGN KEY (municipio_id) REFERENCES municipios(id) ON DELETE SET NULL,
            FOREIGN KEY (parroquia_id) REFERENCES parroquias(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
    """)
    mysql.connection.commit()
    cur.close()
    print("Table jefes_asic created successfully.")
