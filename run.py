import os
from app import create_app

# Ambil nama config dari environment variable 'FLASK_ENV'.
# Jika tidak ada, default ke 'development'.
config_name = os.getenv('FLASK_ENV', 'development')

app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])