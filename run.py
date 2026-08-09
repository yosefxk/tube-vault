import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"Starting TubeVault on http://{HOST}:{PORT} (Local access: http://localhost:{PORT})")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)

