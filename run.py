from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5002) # Use a different port, e.g., 5002 for this new backend