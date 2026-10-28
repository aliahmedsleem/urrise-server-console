from app import create_app

app = create_app()

if __name__ == "__main__":
    # Development only. Production uses Gunicorn behind Nginx.
    app.run(host="127.0.0.1", port=8000, debug=False)
