import os
import uvicorn
from app.config import HOST, PORT

if __name__ == "__main__":
    reload = os.getenv("UVICORN_RELOAD", "false").lower() in ("true", "1")
    print(f"Starting TubeVault on http://{HOST}:{PORT} (Local access: http://localhost:{PORT}) [reload={reload}]")
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=reload)

