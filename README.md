# Rx Validator

A small FastAPI app that validates eyeglass prescription (SPH / CYL / Axis) values for both eyes. Enter values in the browser, or `POST /validate` with a JSON body; the API returns whether the Rx is valid plus normalized values and any field errors.

## Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

## Tests

```bash
pytest -q
```

## Docs

See [docs/](docs/) for the contract, assumptions, and a plain-language explainer of SPH/CYL/Axis.
