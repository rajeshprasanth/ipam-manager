"""Local development entry point:  python run.py"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8076, reload=True)