import sys
import os

here = os.path.dirname(os.path.abspath(__file__))

# backend/ dir → resolves app.main correctly regardless of CWD
sys.path.insert(0, here)
# project root → resolves modules/ package
sys.path.insert(0, os.path.dirname(here))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
