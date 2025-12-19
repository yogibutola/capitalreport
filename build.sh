poetry lock
poetry export -f requirements.txt --without-hashes > requirements.txt
docker build -t capitalreport:v1.0.0 .
docker compose -f docker-compose.yml up