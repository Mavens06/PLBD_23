from fastapi import FastAPI

app = FastAPI(title="Agribotics API")


@app.get("/")
def read_root():
    return {"message": "Agribotics backend is running"}
