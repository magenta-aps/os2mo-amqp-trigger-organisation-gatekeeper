# SPDX-FileCopyrightText: Magenta ApS
#
# SPDX-License-Identifier: MPL-2.0

# Builder
FROM python:3.10

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1
RUN pip install --no-cache-dir poetry==1.1.13

WORKDIR /opt
COPY .git ./
COPY poetry.lock pyproject.toml ./

RUN poetry version --short > VERSION
RUN git rev-parse --verify HEAD > HASH
RUN cat VERSION HASH

RUN poetry install --no-dev

WORKDIR /app
RUN cp /opt/VERSION .
RUN cp /opt/HASH .
COPY orggatekeeper .
CMD [ "python", "./main.py" ]
