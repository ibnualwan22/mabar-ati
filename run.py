import os
from app import create_app
from seed import seed_data # <-- 1. Import fungsi seed_data


# Ambil nama config dari environment variable 'FLASK_ENV'.
# Jika tidak ada, default ke 'development'.
config_name = os.getenv('FLASK_ENV', 'development')

app = create_app(config_name)
@app.cli.command("seed")
def seed():
    """Membuat data awal untuk database."""
    seed_data()

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])