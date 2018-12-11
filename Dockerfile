FROM python:3

pip install psycopg2-binary

ADD xfailflake_grabber.py /
ENTRYPOINT ["python", "./xfailflake-grabber.py"]
CMD ["80"]
