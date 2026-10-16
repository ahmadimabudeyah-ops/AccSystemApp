from waitress import serve
from wsgi import app

serve(app, host="127.0.0.1", port=5001, threads=2)
