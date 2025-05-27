# Maga Player

This repository contains a simple video player GUI based on PyQt5.

## Setup

Run `setup.sh` to install the required dependencies:

```bash
./setup.sh
```

This script should install all Python dependencies (e.g. with `pip install -r requirements.txt`).

## Running the tests

After installing the dependencies you can run the tests with [`pytest`](https://docs.pytest.org/en/latest/):

```bash
pytest
```

During headless runs (for example in CI) you may need to export `QT_QPA_PLATFORM=offscreen`:

```bash
export QT_QPA_PLATFORM=offscreen
```

The test suite can be executed both locally and inside the continuous integration pipeline.


