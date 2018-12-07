FROM python:3
ADD xfailflake-grabber.py /
ENTRYPOINT ["python", "./xfailflake-grabber.py"]
CMD ["80"]
