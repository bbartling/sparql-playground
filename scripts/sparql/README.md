# Lesson SPARQL files (`.rq`)

Same queries as the strings in `scripts/lesson_0*.py`, as plain text files.

## Easiest way to run one on the live API

1. Open <https://sparql-playground.onrender.com/docs>
2. **POST** `/api/sparql/upload` → Try it out → **Choose File**
3. Pick e.g. `02_fc1_points.rq` from this folder → Execute

No JSON, no newline escaping.

You can also download a file from the server with **GET** `/api/sparql/files/{name}` then re-upload it, or run the Python lessons as usual.
