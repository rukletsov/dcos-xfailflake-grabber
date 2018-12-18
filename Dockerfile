FROM python:3
MAINTAINER AlexR <alex@mesosphere.io>

COPY json_formats.py /
COPY postgres_redshift.py /
COPY repo_utils.py /
COPY xfailflake_grabber.py /

pip install psycopg2-binary

ENTRYPOINT ["python", "./xfailflake-grabber.py"]
CMD ["80"]
