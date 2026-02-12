# .PHONY: default

docker-build:
	docker-compose up --build -d

docker-down:
	docker-compose down

docker-start:
	docker start agents-mini-course
	docker exec -it agents-mini-course /bin/bash

docker-n8n-build:
	docker-compose -f docker-compose.n8n.yml up --build -d

docker-n8n-down:
	docker-compose -f docker-compose.n8n.yml down

