Running the Playwright tests locally
====================================

Run all commands from the repository root.

1. Copy `.env.example` to `.env` (see `README.md`) and fill in the values. At
   minimum you need `SECRET_KEY`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
   and `DB_USER`.

2. Create a virtual environment and install the packages and the Playwright
   browsers:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-test.txt
   python -m playwright install chromium firefox webkit
   ```

   `DEBUG` defaults to `False`. With `DEBUG=True`, the packages in
   `requirements-dev.txt` might be required too.

3. If you use the database in Docker, start it:

   ```bash
   docker compose up -d db
   ```

4. Export the `.env` variables configured in step 1 to the current terminal
   session and run the tests:

   ```bash
   set -a; source .env; set +a
   ```

   Alternatively, export only the required variables:

   ```bash
   export SECRET_KEY=<value>
   export DB_PASSWORD=<value>
   export DB_HOST=<value>
   export DB_PORT=<value>
   export DB_NAME=<value>
   export DB_USER=<value>
   ```

   Then run the tests:

   ```bash
   pytest app/editor/playwright_tests.py
   ```

   The tests run in Chromium by default. To run them in another browser, specify
   it, e.g. `--browser firefox`. Valid options are `chromium`, `firefox` and
   `webkit`.

When a test fails, pytest lists it as `FAILED` and shows the failed assertion
and Playwright's call log.

Useful [options](https://playwright.dev/python/docs/test-runners#cli-arguments)
to add to the pytest command:

- `--headed`: show the browser while the tests run.
- `--slowmo 500`: slow steps by 500 ms, so tests can be followed.
- `--screenshot on`: save a screenshot of each test in `test-results/`.
- `--screenshot only-on-failure`: save a screenshot of each failed test in
  `test-results/`.
- `--tracing retain-on-failure`: save a trace of each failed test in
  `test-results/`. Open it with `playwright show-trace <path to trace.zip>` to
  step through the test.

GitHub Actions runs the tests in Chromium, Firefox and WebKit. Each is a
separate job. WebKit is used instead of Safari. Playwright doesn't work with the
branded version of [Safari](https://playwright.dev/python/docs/browsers#webkit)
since it relies on patches.
