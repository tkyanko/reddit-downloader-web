# From https://stackoverflow.com/a/72465422

FROM python:3.10-slim as python-base

# https://python-poetry.org/docs#ci-recommendations
ENV POETRY_VERSION=1.4.1
ENV POETRY_HOME=/opt/poetry
ENV POETRY_VENV=/opt/poetry-venv

# Tell Poetry where to place its cache and virtual environment
ENV POETRY_CACHE_DIR=/opt/.cache

# Create stage for Poetry installation
FROM python-base as poetry-base

RUN apt-get -y update
RUN apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libgtk-3-0 && rm -rf /var/lib/apt/lists/*

# Creating a virtual environment just for poetry and install it with pip
RUN python3 -m venv $POETRY_VENV \
    && $POETRY_VENV/bin/pip install -U pip setuptools \
    && $POETRY_VENV/bin/pip install poetry==${POETRY_VERSION}

# Create a new stage from the base python image
FROM python-base as redditdownloader-app

# Copy Poetry to app image
COPY --from=poetry-base ${POETRY_VENV} ${POETRY_VENV}

# Add Poetry to PATH
ENV PATH="${PATH}:${POETRY_VENV}/bin"

WORKDIR /reddit-downloader-web

# Copy Dependencies
COPY poetry.lock pyproject.toml ./

# [OPTIONAL] Validate the project is properly configured
RUN poetry check

# Install Dependencies
RUN poetry install --no-interaction --no-cache --without dev

# Copy Application
COPY . /reddit-downloader-web

# Run Application
EXPOSE 5000
CMD [ "poetry", "run", "python", "-m", "flask", "run", "--host=0.0.0.0" ]