from app import app

if __name__ == "__main__":
    # Default to 0.0.0.0 for containerized execution
    app.run(host="0.0.0.0", port=3001, debug=False)
