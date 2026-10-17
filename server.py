from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers import chart, simulator, portfolio, lines, screen

app = FastAPI(title="Finance Analysis Tool", version="0.1.0")

app.include_router(chart.router)
app.include_router(simulator.router)
app.include_router(portfolio.router)
app.include_router(lines.router)
app.include_router(screen.router)

app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/")
def root():
    return FileResponse("web/index.html")


@app.get("/dashboard")
def dashboard():
    return FileResponse("web/dashboard.html")


@app.get("/screen")
def screen_page():
    return FileResponse("web/screen.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
