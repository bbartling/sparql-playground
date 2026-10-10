# Lesson SPARQL files (`.rq`)

Plain-text SPARQL — same queries as the strings in `scripts/lesson_0*.py`.
Copy these from your local clone (they are not served by the API).

## Run one in Swagger

1. Wake the server: `GET /health` until `"ready": true`
2. **POST** `/api/sparql/upload` → Try it out → Choose File → pick e.g. `02_fc1_points.rq`
3. Execute

Or paste the file contents into **POST** `/api/sparql`.
