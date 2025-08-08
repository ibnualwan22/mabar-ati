from flask import Blueprint

lapangan_bp = Blueprint('lapangan', __name__, template_folder='templates')

from . import routes