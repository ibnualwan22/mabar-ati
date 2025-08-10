from flask import Blueprint

# Baris ini mendefinisikan blueprint 'main'
main_bp = Blueprint('main', __name__, template_folder='templates')

# Baris ini mengimpor routes yang akan menggunakan blueprint di atas
from . import routes